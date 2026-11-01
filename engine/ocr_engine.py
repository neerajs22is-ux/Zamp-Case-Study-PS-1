"""OCR Engine for Scanned Invoices (pypdfium2 + pytesseract).

Core Invariants:
1. Low-cost open source: zero paid cloud vision API dependencies.
2. Page-level provenance: retains page number, bounding boxes, and word-level confidence.
3. Quality pre-screening: computes image contrast and dark-pixel distribution to detect degraded scans.
4. Strict fail-closed routing: missing OCR binary, degraded image, or confidence < 75.0%
   routes strictly to FLAGGED_HITL_REVIEW, never permitting automated approval.
"""

from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageStat
import pypdfium2 as pdfium

try:
    import pytesseract
    from pytesseract import Output
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    Output = None

logger = logging.getLogger("engine.ocr")


@dataclass
class OCRWord:
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # left, top, width, height


@dataclass
class OCRPageResult:
    page_number: int
    text: str
    mean_luminance: float
    contrast_stddev: float
    dark_pixel_ratio: float
    is_degraded_contrast: bool
    word_count: int
    mean_confidence: float
    words: List[OCRWord] = field(default_factory=list)


@dataclass
class OCRDocumentResult:
    document_id: str
    filename: str
    total_pages: int
    full_text: str
    mean_confidence: float
    is_degraded: bool
    ocr_available: bool
    status: str  # SUCCESS, LOW_CONFIDENCE, DEGRADED_SCAN, TESSERACT_NOT_AVAILABLE, ERROR
    routing_recommendation: str  # FLAGGED_HITL_REVIEW, OCR_PARSING_CANDIDATE
    reasons: List[str] = field(default_factory=list)
    pages: List[OCRPageResult] = field(default_factory=list)


class OCREngine:
    """Orchestrates image pre-processing, rasterization, and local OCR execution."""

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        min_contrast_stddev: float = 10.0,
        min_confidence_threshold: float = 75.0,
        raster_scale: float = 2.5,
    ) -> None:
        self.min_contrast = min_contrast_stddev
        self.min_confidence = min_confidence_threshold
        self.raster_scale = raster_scale

        if tesseract_cmd and PYTESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def analyze_image_quality(self, pil_image: Image.Image) -> Tuple[float, float, float, bool]:
        """Analyzes mean luminance, contrast (stddev), and dark-pixel ratio."""
        gray = pil_image.convert("L")
        stat = ImageStat.Stat(gray)
        mean_lum = stat.mean[0]
        stddev_lum = stat.stddev[0]

        # Calculate dark pixel ratio (< 128)
        histogram = gray.histogram()
        total_pixels = sum(histogram)
        dark_pixels = sum(histogram[:128])
        dark_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0.0

        is_degraded = (stddev_lum < self.min_contrast) or (dark_ratio < 0.0005)
        return mean_lum, stddev_lum, dark_ratio, is_degraded

    def process_pdf_bytes(
        self,
        pdf_bytes: bytes,
        filename: str = "scanned_invoice.pdf",
        document_id: str = "DOC",
    ) -> OCRDocumentResult:
        """Rasterizes PDF pages and performs OCR with strict fail-closed fallback."""
        reasons: List[str] = []
        try:
            pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
            total_pages = len(pdf)
        except Exception as e:
            logger.error(f"Failed to open PDF with pdfium: {e}")
            return OCRDocumentResult(
                document_id=document_id,
                filename=filename,
                total_pages=0,
                full_text="",
                mean_confidence=0.0,
                is_degraded=True,
                ocr_available=False,
                status="CORRUPTED_PDF",
                routing_recommendation="FLAGGED_HITL_REVIEW",
                reasons=[f"Corrupted PDF byte stream: {str(e)}"],
            )

        page_results: List[OCRPageResult] = []
        full_text_parts: List[str] = []
        all_confidences: List[float] = []
        doc_is_degraded = False

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = pdf[page_idx]
            pil_image = page.render(scale=self.raster_scale).to_pil()

            mean_lum, stddev_lum, dark_ratio, is_degraded = self.analyze_image_quality(pil_image)
            if is_degraded:
                doc_is_degraded = True

            page_words: List[OCRWord] = []
            page_text = ""
            page_mean_conf = 0.0

            if not PYTESSERACT_AVAILABLE:
                reasons.append("pytesseract library not available in Python environment.")
                ocr_available = False
            else:
                try:
                    data = pytesseract.image_to_data(pil_image, output_type=Output.DICT)
                    ocr_available = True

                    n_boxes = len(data["text"])
                    word_confs = []
                    text_words = []

                    for i in range(n_boxes):
                        txt = data["text"][i].strip()
                        conf = float(data["conf"][i])
                        if txt and conf > 0:
                            word_confs.append(conf)
                            text_words.append(txt)
                            page_words.append(
                                OCRWord(
                                    text=txt,
                                    confidence=conf,
                                    bbox=(data["left"][i], data["top"][i], data["width"][i], data["height"][i]),
                                )
                            )

                    page_text = " ".join(text_words)
                    page_mean_conf = sum(word_confs) / len(word_confs) if word_confs else 0.0
                    all_confidences.extend(word_confs)

                except pytesseract.TesseractNotFoundError:
                    ocr_available = False
                    if "Tesseract binary not installed on host" not in reasons:
                        reasons.append("Tesseract binary not installed on host system (requires apt-get install tesseract-ocr on Linux or Tesseract-OCR on Windows).")
                except Exception as ex:
                    ocr_available = False
                    reasons.append(f"OCR execution error: {str(ex)}")

            page_results.append(
                OCRPageResult(
                    page_number=page_num,
                    text=page_text,
                    mean_luminance=round(mean_lum, 2),
                    contrast_stddev=round(stddev_lum, 2),
                    dark_pixel_ratio=round(dark_ratio, 4),
                    is_degraded_contrast=is_degraded,
                    word_count=len(page_words),
                    mean_confidence=round(page_mean_conf, 2),
                    words=page_words,
                )
            )
            if page_text:
                full_text_parts.append(f"--- Page {page_num} ---\n{page_text}")

        full_doc_text = "\n\n".join(full_text_parts)
        doc_mean_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        # Determine Status and Routing
        if not ocr_available:
            status = "TESSERACT_NOT_AVAILABLE"
            recommendation = "FLAGGED_HITL_REVIEW"
            reasons.append("Scanned image cannot be parsed automatically due to absent OCR binary. Routed to HITL.")
        elif doc_is_degraded:
            status = "DEGRADED_SCAN_POOR_CONTRAST"
            recommendation = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Degraded scan detected: contrast stddev below threshold ({self.min_contrast}). Routed to HITL.")
        elif doc_mean_conf < self.min_confidence:
            status = "LOW_CONFIDENCE_SCAN"
            recommendation = "FLAGGED_HITL_REVIEW"
            reasons.append(f"Average OCR confidence {doc_mean_conf:.1f}% is below acceptable threshold {self.min_confidence:.1f}%. Routed to HITL.")
        else:
            status = "SUCCESS"
            recommendation = "OCR_PARSING_CANDIDATE"
            reasons.append(f"OCR completed successfully with {doc_mean_conf:.1f}% confidence across {len(all_confidences)} words.")

        return OCRDocumentResult(
            document_id=document_id,
            filename=filename,
            total_pages=total_pages,
            full_text=full_doc_text,
            mean_confidence=round(doc_mean_conf, 2),
            is_degraded=doc_is_degraded,
            ocr_available=ocr_available,
            status=status,
            routing_recommendation=recommendation,
            reasons=reasons,
            pages=page_results,
        )
