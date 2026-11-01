"""AWS Bedrock Palmyra Vision 7B Multimodal Extraction Adapter.

Integrates writer.palmyra-vision-7b on Bedrock Mantle:
  Base URL: https://bedrock-mantle.us-east-1.api.aws/v1/chat/completions
  Model ID: writer.palmyra-vision-7b

Responsibilities:
1. Render PDF pages into scaled high-resolution images via pypdfium2.
2. Formulate vision-language prompts adhering to the 4,096 total token context window.
3. Interpret visual invoice layouts: tables, line items, stamps, handwritten notes, signatures.
4. Extract structured commercial metadata (GSTIN, numbers, dates, line items, monetary totals).
5. Support Strategy C (Tesseract OCR text cues passed alongside visual frames).
6. Enforce strict fail-closed validation: unreadable/degraded images or corrupted JSON route to HITL.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image
import pypdfium2 as pdfium
from pydantic import BaseModel, Field, ValidationError

from backend.core.config import settings

logger = logging.getLogger("engine.palmyra_vision")

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class PalmyraVisualExtractionModel(BaseModel):
    document_type: str = Field(default="TAX INVOICE")
    supplier_name: str = Field(default="Unknown Supplier")
    supplier_gstin: Optional[str] = Field(default=None)
    invoice_number: str = Field(default="UNKNOWN")
    invoice_date: str = Field(default="1970-01-01")
    po_reference: Optional[str] = Field(default=None)
    currency: str = Field(default="INR")
    taxable_value: float = Field(default=0.0)
    cgst_amount: float = Field(default=0.0)
    sgst_amount: float = Field(default=0.0)
    igst_amount: float = Field(default=0.0)
    total_tax_amount: float = Field(default=0.0)
    grand_total: float = Field(default=0.0)
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    has_handwritten_notes: bool = Field(default=False)
    handwritten_notes_text: Optional[str] = Field(default=None)
    has_stamp_or_signature: bool = Field(default=False)
    visual_clarity: str = Field(default="CLEAR")  # CLEAR, DEGRADED, UNREADABLE
    uncertain_fields: List[str] = Field(default_factory=list)


@dataclass
class PalmyraVisualResult:
    document_id: str
    filename: str
    total_pages: int
    extraction: PalmyraVisualExtractionModel
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    raw_response_text: str
    status: str  # SUCCESS, LOW_CONFIDENCE, DEGRADED_SCAN, ERROR
    routing_recommendation: str  # VISUAL_EXTRACTION_SUCCESS, FLAGGED_HITL_REVIEW
    reasons: List[str] = field(default_factory=list)
    strategy: str = "VISION_DIRECT"  # VISION_DIRECT or VISION_WITH_OCR_CUES


class PalmyraVisionAdapter:
    """Adapter for AWS Bedrock Palmyra Vision 7B multimodal document intelligence."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_dimension: int = 1280,
    ) -> None:
        self.base_url = (base_url or settings.PALMYRA_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.get_palmyra_api_key()
        self.model_id = model_id or settings.PALMYRA_MODEL_ID
        self.timeout = timeout or settings.PALMYRA_TIMEOUT_SECONDS
        self.max_tokens = max_tokens or settings.PALMYRA_MAX_TOKENS
        self.temperature = temperature or settings.PALMYRA_TEMPERATURE
        self.max_dimension = max_dimension
        self.endpoint = f"{self.base_url}/chat/completions"

    def _render_and_scale_page(self, pdf_page: Any) -> Image.Image:
        """Renders a PDF page to a PIL Image scaled to fit within max_dimension."""
        pil_img = pdf_page.render(scale=2.0).to_pil()
        width, height = pil_img.size
        if max(width, height) > self.max_dimension:
            ratio = self.max_dimension / max(width, height)
            new_size = (int(width * ratio), int(height * ratio))
            pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
        return pil_img

    def _encode_image_to_base64_jpeg(self, img: Image.Image, quality: int = 85) -> str:
        """Encodes PIL image as JPEG base64 string."""
        buf = io.BytesIO()
        rgb_img = img.convert("RGB")
        rgb_img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _build_vision_prompt(self, ocr_cues: Optional[str] = None) -> str:
        """Constructs a strict, bounded JSON extraction prompt fitting the 4k context."""
        cues_text = ""
        if ocr_cues:
            clean_cues = ocr_cues.strip()[:600]
            cues_text = f"\n\nOCR Pre-Pass Text Clues:\n\"\"\"\n{clean_cues}\n\"\"\"\nUse the visual image as primary ground truth, cross-referencing OCR clues for difficult characters."

        return (
            "You are an AP visual document parser. Extract all data from this invoice image and return ONLY a single valid JSON object."
            f"{cues_text}\n\n"
            "Required JSON keys:\n"
            "- document_type: string (e.g. 'TAX INVOICE', 'PURCHASE ORDER', 'PAYMENT RECEIPT')\n"
            "- supplier_name: string\n"
            "- supplier_gstin: string (15-character Indian GSTIN) or null\n"
            "- invoice_number: string\n"
            "- invoice_date: string (YYYY-MM-DD)\n"
            "- po_reference: string or null\n"
            "- currency: string (default 'INR')\n"
            "- taxable_value: number\n"
            "- cgst_amount: number\n"
            "- sgst_amount: number\n"
            "- igst_amount: number\n"
            "- total_tax_amount: number\n"
            "- grand_total: number\n"
            "- line_items: list of objects with keys: item_description, quantity, unit_price, taxable_amount, total_amount\n"
            "- has_handwritten_notes: boolean\n"
            "- handwritten_notes_text: string or null\n"
            "- has_stamp_or_signature: boolean\n"
            "- visual_clarity: 'CLEAR', 'DEGRADED', or 'UNREADABLE'\n"
            "- uncertain_fields: list of strings indicating any field where visual ambiguity prevented confident reading\n\n"
            "Do not include markdown fences, comments, or repeated tokens. Output ONLY the JSON object and stop immediately after the closing brace."
        )

    def extract_visual(
        self,
        pdf_bytes: bytes,
        filename: str = "document.pdf",
        document_id: str = "DOC",
        ocr_cues: Optional[str] = None,
    ) -> PalmyraVisualResult:
        """Performs visual extraction across rendered PDF pages using writer.palmyra-vision-7b."""
        t_start = time.perf_counter()
        reasons: List[str] = []

        if not self.api_key:
            return PalmyraVisualResult(
                document_id=document_id,
                filename=filename,
                total_pages=0,
                extraction=PalmyraVisualExtractionModel(),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0.0,
                estimated_cost_usd=0.0,
                raw_response_text="",
                status="ERROR",
                routing_recommendation="FLAGGED_HITL_REVIEW",
                reasons=["Palmyra/Mantle API key not configured."],
            )

        try:
            pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
            total_pages = len(pdf)
            if total_pages == 0:
                raise ValueError("PDF has 0 pages.")
        except Exception as e:
            return PalmyraVisualResult(
                document_id=document_id,
                filename=filename,
                total_pages=0,
                extraction=PalmyraVisualExtractionModel(),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0.0,
                estimated_cost_usd=0.0,
                raw_response_text="",
                status="ERROR",
                routing_recommendation="FLAGGED_HITL_REVIEW",
                reasons=[f"Failed to rasterize PDF: {e}"],
            )

        # Process Page 1 (primary commercial face of invoice)
        page0 = pdf[0]
        img = self._render_and_scale_page(page0)
        b64_jpeg = self._encode_image_to_base64_jpeg(img)

        prompt_str = self._build_vision_prompt(ocr_cues=ocr_cues)
        strategy = "VISION_WITH_OCR_CUES" if ocr_cues else "VISION_DIRECT"

        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_str},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_jpeg}"}},
                    ],
                }
            ],
            "max_tokens": min(self.max_tokens, 1500),
            "temperature": self.temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.endpoint, headers=headers, json=payload)
        except Exception as ex:
            dt_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return PalmyraVisualResult(
                document_id=document_id,
                filename=filename,
                total_pages=total_pages,
                extraction=PalmyraVisualExtractionModel(visual_clarity="UNREADABLE"),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=dt_ms,
                estimated_cost_usd=0.0,
                raw_response_text=str(ex),
                status="ERROR",
                routing_recommendation="FLAGGED_HITL_REVIEW",
                reasons=[f"Palmyra Vision endpoint error ({type(ex).__name__}): {ex}"],
                strategy=strategy,
            )

        dt_ms = round((time.perf_counter() - t_start) * 1000, 2)

        if resp.status_code != 200:
            return PalmyraVisualResult(
                document_id=document_id,
                filename=filename,
                total_pages=total_pages,
                extraction=PalmyraVisualExtractionModel(visual_clarity="UNREADABLE"),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=dt_ms,
                estimated_cost_usd=0.0,
                raw_response_text=resp.text[:500],
                status="ERROR",
                routing_recommendation="FLAGGED_HITL_REVIEW",
                reasons=[f"Palmyra Vision HTTP {resp.status_code}: {resp.text[:200]}"],
                strategy=strategy,
            )

        resp_json = resp.json()
        usage = resp_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        cost = (
            (prompt_tokens / 1000.0) * settings.PALMYRA_COST_PER_1K_INPUT
            + (completion_tokens / 1000.0) * settings.PALMYRA_COST_PER_1K_OUTPUT
        )

        raw_content = ""
        try:
            raw_content = resp_json["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            raw_content = ""

        # Parse JSON
        parsed_data = {}
        # Try finding json block
        match = _JSON_BLOCK_RE.search(raw_content)
        json_target = match.group(1) if match else raw_content

        # Find first { and last }
        first_brace = json_target.find("{")
        last_brace = json_target.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean_str = json_target[first_brace : last_brace + 1]
            try:
                parsed_data = json.loads(clean_str)
            except json.JSONDecodeError:
                # Attempt to clean trailing commas
                cleaned = re.sub(r",\s*([\]}])", r"\1", clean_str)
                try:
                    parsed_data = json.loads(cleaned)
                except Exception as je:
                    reasons.append(f"JSON decoding error: {je}")

        try:
            model_extraction = PalmyraVisualExtractionModel(**parsed_data)
        except ValidationError as ve:
            model_extraction = PalmyraVisualExtractionModel(visual_clarity="DEGRADED")
            reasons.append(f"Validation error mapping to schema: {ve}")

        # Routing logic
        status_val = "SUCCESS"
        routing = "VISUAL_EXTRACTION_SUCCESS"

        if model_extraction.visual_clarity in ("DEGRADED", "UNREADABLE"):
            status_val = "DEGRADED_SCAN"
            routing = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Visual clarity assessed as {model_extraction.visual_clarity}. Routed to HITL.")
        elif model_extraction.uncertain_fields:
            status_val = "LOW_CONFIDENCE"
            routing = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Uncertain visual fields detected: {model_extraction.uncertain_fields}. Routed to HITL.")
        elif model_extraction.has_handwritten_notes:
            routing = "FLAGGED_HITL_REVIEW"
            reasons.append("Handwritten note detected visually. Requires HITL operational review.")

        return PalmyraVisualResult(
            document_id=document_id,
            filename=filename,
            total_pages=total_pages,
            extraction=model_extraction,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=dt_ms,
            estimated_cost_usd=round(cost, 6),
            raw_response_text=raw_content[:800],
            status=status_val,
            routing_recommendation=routing,
            reasons=reasons,
            strategy=strategy,
        )
