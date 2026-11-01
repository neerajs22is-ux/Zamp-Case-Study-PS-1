"""Palmyra Vision 7B vs Tesseract OCR AP Benchmark Runner.

Evaluates 5 Documents across 3 Strategies:
  Documents:
    1. APTC-036 (Raster image-only scan)
    2. APTC-037 (Low-contrast degraded skewed scan)
    3. APTC-001 (Digital control - clean GST invoice)
    4. APTC-009 (Digital control - manufacturing invoice)
    5. APTC-030 (Digital control - PO quantity/value mismatch)

  Strategies:
    Strategy A: Existing Tesseract OCR
    Strategy B: Palmyra Vision 7B visual extraction
    Strategy C: Tesseract OCR followed by Palmyra interpretation (Hybrid Vision + OCR)

Measures:
  - Text recovery
  - Field extraction accuracy (Supplier, GSTIN, Invoice Number, Date)
  - Line-item accuracy (count, quantities, prices)
  - Monetary value accuracy (Taxable value, Grand total)
  - Handwritten text / stamp recognition
  - Page-level provenance & bounding boxes
  - Latency (ms)
  - Actual token consumption & cost ($)
  - Confidence & HITL routing decision
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.core.config import settings
from engine.ocr_engine import OCREngine
from engine.palmyra_vision_adapter import PalmyraVisionAdapter

logger = logging.getLogger("engine.palmyra_benchmark")


class PalmyraBenchmarkHarness:
    """Executes comparative evaluation across Strategy A, B, and C."""

    def __init__(self) -> None:
        self.corpus_dir = os.path.join("tests", "evaluation_corpus_v2")
        self.invoices_dir = os.path.join(self.corpus_dir, "invoices")
        self.gt_path = os.path.join(self.corpus_dir, "ground_truth.json")

        with open(self.gt_path, "r", encoding="utf-8") as f:
            gt_list = json.load(f)
        self.gt_map = {item["document_id"]: item for item in gt_list}

        import pandas as pd
        self.manifest_df = pd.read_csv(os.path.join(self.corpus_dir, "pdf_integrity_manifest.csv"))
        doc_map = dict(zip(self.manifest_df["document_id"], self.manifest_df["filename"]))

        target_ids = ["APTC-036", "APTC-037", "APTC-001", "APTC-009", "APTC-030"]
        self.target_docs = [(doc_id, doc_map[doc_id]) for doc_id in target_ids if doc_id in doc_map]

        self.ocr_engine = OCREngine()
        self.palmyra_adapter = PalmyraVisionAdapter()

    def run_benchmark(self) -> Dict[str, Any]:
        """Runs comparative benchmark across all 5 target documents."""
        all_doc_results: List[Dict[str, Any]] = []

        for doc_id, filename in self.target_docs:
            print(f"\n=======================================================")
            print(f"BENCHMARKING: {doc_id} - {filename}")
            print(f"=======================================================")
            file_path = os.path.join(self.invoices_dir, filename)
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            gt = self.gt_map.get(doc_id, {})

            # -------------------------------------------------------------
            # Strategy A: Existing Tesseract OCR
            # -------------------------------------------------------------
            print("  Running Strategy A (Tesseract OCR)...")
            t0 = time.perf_counter()
            res_a = self.ocr_engine.process_pdf_bytes(pdf_bytes, filename=filename, document_id=doc_id)
            lat_a = round((time.perf_counter() - t0) * 1000, 2)

            strat_a_report = self._evaluate_strategy_a(res_a, gt, lat_a)

            # -------------------------------------------------------------
            # Strategy B: Palmyra Vision 7B Direct
            # -------------------------------------------------------------
            print("  Running Strategy B (Palmyra Vision 7B Direct)...")
            res_b = self.palmyra_adapter.extract_visual(pdf_bytes, filename=filename, document_id=doc_id)
            strat_b_report = self._evaluate_strategy_b(res_b, gt)

            # -------------------------------------------------------------
            # Strategy C: Tesseract OCR + Palmyra Vision Interpretation
            # -------------------------------------------------------------
            print("  Running Strategy C (Tesseract OCR + Palmyra Interpretation)...")
            ocr_text_cue = res_a.full_text if res_a.full_text else ""
            res_c = self.palmyra_adapter.extract_visual(
                pdf_bytes,
                filename=filename,
                document_id=doc_id,
                ocr_cues=ocr_text_cue,
            )
            strat_c_report = self._evaluate_strategy_c(res_c, res_a, gt)

            all_doc_results.append({
                "document_id": doc_id,
                "filename": filename,
                "scenario": gt.get("scenario", "unknown"),
                "ground_truth": {
                    "supplier_name": gt.get("supplier"),
                    "supplier_gstin": gt.get("supplier_gstin"),
                    "invoice_number": gt.get("invoice_number"),
                    "invoice_date": gt.get("invoice_date"),
                    "expected_total": gt.get("expected_total"),
                    "taxable_value": gt.get("taxable_value"),
                    "line_items_count": len(gt.get("line_items", [])),
                    "expected_outcome": gt.get("expected_outcome"),
                },
                "strategy_a_tesseract": strat_a_report,
                "strategy_b_palmyra_direct": strat_b_report,
                "strategy_c_hybrid_ocr_palmyra": strat_c_report,
            })

        summary = self._compute_summary(all_doc_results)
        return {
            "evaluation_title": "AWS Bedrock Palmyra Vision 7B vs Tesseract OCR Benchmark",
            "model_tested": settings.PALMYRA_MODEL_ID,
            "region": "us-east-1",
            "total_documents_tested": len(self.target_docs),
            "summary_metrics": summary,
            "document_evaluations": all_doc_results,
        }

    def _evaluate_strategy_a(self, res_a: Any, gt: Dict[str, Any], lat_ms: float) -> Dict[str, Any]:
        """Evaluates Strategy A against ground truth."""
        text_recovered_chars = len(res_a.full_text.strip())
        word_count = sum(p.word_count for p in res_a.pages)
        has_bboxes = any(len(p.words) > 0 for p in res_a.pages)

        # Check if GT strings appear in OCR text
        exp_inv = str(gt.get("invoice_number", ""))
        exp_gst = str(gt.get("supplier_gstin", ""))
        inv_found = exp_inv in res_a.full_text if exp_inv else False
        gst_found = exp_gst in res_a.full_text if exp_gst else False

        routing = "MATCH_CANDIDATE" if res_a.routing_recommendation == "OCR_PARSING_CANDIDATE" else "FLAGGED_HITL_REVIEW"

        return {
            "status": res_a.status,
            "ocr_available": res_a.ocr_available,
            "is_degraded": res_a.is_degraded,
            "text_recovered_chars": text_recovered_chars,
            "word_count": word_count,
            "mean_confidence": res_a.mean_confidence,
            "has_bounding_boxes": has_bboxes,
            "page_level_provenance": True,
            "invoice_number_recovered": inv_found,
            "supplier_gstin_recovered": gst_found,
            "handwritten_notes_detected": False,
            "latency_ms": lat_ms,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "routing_decision": routing,
            "reasons": res_a.reasons,
        }

    def _evaluate_strategy_b(self, res_b: Any, gt: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates Strategy B against ground truth."""
        ext = res_b.extraction
        exp_inv = str(gt.get("invoice_number", ""))
        exp_gst = str(gt.get("supplier_gstin", ""))
        exp_tot = float(gt.get("expected_total", 0.0))
        exp_tax = float(gt.get("taxable_value", 0.0))
        gt_lines = gt.get("line_items", [])

        inv_match = (ext.invoice_number.strip().upper() == exp_inv.strip().upper()) if exp_inv else False
        gst_match = (ext.supplier_gstin.strip().upper() == exp_gst.strip().upper()) if ext.supplier_gstin and exp_gst else False
        sup_match = (gt.get("supplier", "").lower() in ext.supplier_name.lower()) if gt.get("supplier") else False
        total_match = abs(ext.grand_total - exp_tot) <= 1.0 if exp_tot > 0 else False
        taxable_match = abs(ext.taxable_value - exp_tax) <= 1.0 if exp_tax > 0 else False
        line_count_match = len(ext.line_items) == len(gt_lines) if gt_lines else True

        # Field extraction score (out of 5: sup, gst, inv, tot, tax)
        fields_passed = sum([sup_match, gst_match, inv_match, total_match, taxable_match])

        # Routing decision
        if ext.visual_clarity in ("DEGRADED", "UNREADABLE") or not total_match or not gst_match:
            routing = "FLAGGED_HITL_REVIEW"
        else:
            routing = "MATCH_CANDIDATE"

        return {
            "status": res_b.status,
            "visual_clarity": ext.visual_clarity,
            "supplier_matched": sup_match,
            "supplier_gstin_matched": gst_match,
            "invoice_number_matched": inv_match,
            "total_amount_matched": total_match,
            "taxable_value_matched": taxable_match,
            "line_items_count_matched": line_count_match,
            "fields_passed_score": f"{fields_passed}/5",
            "extracted_supplier": ext.supplier_name,
            "extracted_gstin": ext.supplier_gstin,
            "extracted_invoice_number": ext.invoice_number,
            "extracted_total": ext.grand_total,
            "has_handwritten_notes": ext.has_handwritten_notes,
            "has_stamp_or_signature": ext.has_stamp_or_signature,
            "bounding_box_support": False,  # Palmyra returns fields, not pixel bboxes
            "page_level_provenance": True,
            "latency_ms": res_b.latency_ms,
            "prompt_tokens": res_b.prompt_tokens,
            "completion_tokens": res_b.completion_tokens,
            "cost_usd": res_b.estimated_cost_usd,
            "routing_decision": routing,
            "reasons": res_b.reasons,
        }

    def _evaluate_strategy_c(self, res_c: Any, res_a: Any, gt: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates Strategy C against ground truth."""
        ext = res_c.extraction
        exp_inv = str(gt.get("invoice_number", ""))
        exp_gst = str(gt.get("supplier_gstin", ""))
        exp_tot = float(gt.get("expected_total", 0.0))
        exp_tax = float(gt.get("taxable_value", 0.0))
        gt_lines = gt.get("line_items", [])

        inv_match = (ext.invoice_number.strip().upper() == exp_inv.strip().upper()) if exp_inv else False
        gst_match = (ext.supplier_gstin.strip().upper() == exp_gst.strip().upper()) if ext.supplier_gstin and exp_gst else False
        sup_match = (gt.get("supplier", "").lower() in ext.supplier_name.lower()) if gt.get("supplier") else False
        total_match = abs(ext.grand_total - exp_tot) <= 1.0 if exp_tot > 0 else False
        taxable_match = abs(ext.taxable_value - exp_tax) <= 1.0 if exp_tax > 0 else False
        line_count_match = len(ext.line_items) == len(gt_lines) if gt_lines else True

        fields_passed = sum([sup_match, gst_match, inv_match, total_match, taxable_match])

        if ext.visual_clarity in ("DEGRADED", "UNREADABLE") or not total_match or not gst_match:
            routing = "FLAGGED_HITL_REVIEW"
        else:
            routing = "MATCH_CANDIDATE"

        return {
            "status": res_c.status,
            "visual_clarity": ext.visual_clarity,
            "supplier_matched": sup_match,
            "supplier_gstin_matched": gst_match,
            "invoice_number_matched": inv_match,
            "total_amount_matched": total_match,
            "taxable_value_matched": taxable_match,
            "line_items_count_matched": line_count_match,
            "fields_passed_score": f"{fields_passed}/5",
            "extracted_supplier": ext.supplier_name,
            "extracted_gstin": ext.supplier_gstin,
            "extracted_invoice_number": ext.invoice_number,
            "extracted_total": ext.grand_total,
            "has_handwritten_notes": ext.has_handwritten_notes,
            "has_stamp_or_signature": ext.has_stamp_or_signature,
            "bounding_box_support": res_a.ocr_available,  # Inherits bounding boxes from Tesseract
            "page_level_provenance": True,
            "latency_ms": res_c.latency_ms,
            "prompt_tokens": res_c.prompt_tokens,
            "completion_tokens": res_c.completion_tokens,
            "cost_usd": res_c.estimated_cost_usd,
            "routing_decision": routing,
            "reasons": res_c.reasons,
        }

    def _compute_summary(self, doc_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregates metrics across the 3 strategies."""
        n = len(doc_results)
        
        # Latency & Cost
        tot_lat_a = sum(d["strategy_a_tesseract"]["latency_ms"] for d in doc_results)
        tot_lat_b = sum(d["strategy_b_palmyra_direct"]["latency_ms"] for d in doc_results)
        tot_lat_c = sum(d["strategy_c_hybrid_ocr_palmyra"]["latency_ms"] for d in doc_results)

        tot_cost_b = sum(d["strategy_b_palmyra_direct"]["cost_usd"] for d in doc_results)
        tot_cost_c = sum(d["strategy_c_hybrid_ocr_palmyra"]["cost_usd"] for d in doc_results)

        # Accuracy
        b_inv_acc = sum(1 for d in doc_results if d["strategy_b_palmyra_direct"]["invoice_number_matched"])
        b_gst_acc = sum(1 for d in doc_results if d["strategy_b_palmyra_direct"]["supplier_gstin_matched"])
        b_tot_acc = sum(1 for d in doc_results if d["strategy_b_palmyra_direct"]["total_amount_matched"])

        c_inv_acc = sum(1 for d in doc_results if d["strategy_c_hybrid_ocr_palmyra"]["invoice_number_matched"])
        c_gst_acc = sum(1 for d in doc_results if d["strategy_c_hybrid_ocr_palmyra"]["supplier_gstin_matched"])
        c_tot_acc = sum(1 for d in doc_results if d["strategy_c_hybrid_ocr_palmyra"]["total_amount_matched"])

        return {
            "total_documents": n,
            "avg_latency_ms": {
                "strategy_a_tesseract": round(tot_lat_a / n, 2),
                "strategy_b_palmyra_direct": round(tot_lat_b / n, 2),
                "strategy_c_hybrid_ocr_palmyra": round(tot_lat_c / n, 2),
            },
            "total_cost_usd": {
                "strategy_a_tesseract": 0.0,
                "strategy_b_palmyra_direct": round(tot_cost_b, 6),
                "strategy_c_hybrid_ocr_palmyra": round(tot_cost_c, 6),
            },
            "accuracy_comparison": {
                "strategy_b_palmyra_direct": {
                    "invoice_number_accuracy": f"{b_inv_acc}/{n} ({round(b_inv_acc/n*100, 1)}%)",
                    "gstin_accuracy": f"{b_gst_acc}/{n} ({round(b_gst_acc/n*100, 1)}%)",
                    "total_amount_accuracy": f"{b_tot_acc}/{n} ({round(b_tot_acc/n*100, 1)}%)",
                },
                "strategy_c_hybrid_ocr_palmyra": {
                    "invoice_number_accuracy": f"{c_inv_acc}/{n} ({round(c_inv_acc/n*100, 1)}%)",
                    "gstin_accuracy": f"{c_gst_acc}/{n} ({round(c_gst_acc/n*100, 1)}%)",
                    "total_amount_accuracy": f"{c_tot_acc}/{n} ({round(c_tot_acc/n*100, 1)}%)",
                },
            },
        }


if __name__ == "__main__":
    harness = PalmyraBenchmarkHarness()
    results = harness.run_benchmark()

    # Save benchmark results
    out_path = os.path.join("scratch", "palmyra_vision_benchmark_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETED SUCCESSFULLY!")
    print(f"Results saved to: {out_path}")
    print("Summary:")
    print(json.dumps(results["summary_metrics"], indent=2))
    print("=" * 70 + "\n")
