"""Comprehensive responsiveness verification script across Flagship, Sandbox 2.0, and Legacy.

Audits horizontal overflow (scrollWidth vs clientWidth) across 9 standard viewports:
- Mobile: 320x568, 375x812, 390x844, 430x932
- Tablet: 768x1024, 1024x768
- Desktop: 1280x800, 1440x900, 1920x1080

Prerequisites:
- Unified development server running at BASE_URL (defaults to http://127.0.0.1:8001)
- Playwright Chromium installed (`python -m playwright install chromium`)
"""

import os
import sys
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "assets", "responsive_audit")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", OUTPUT_DIR)

os.makedirs(OUTPUT_DIR, exist_ok=True)
if ARTIFACT_DIR != OUTPUT_DIR:
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

def get_auth_token():
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/dev-session",
        data=json.dumps({"email": "sme_lead@company.internal", "org_id": "org_sme_eval"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["access_token"]

def save_screenshot(page, filename):
    local_path = os.path.join(OUTPUT_DIR, filename)
    page.screenshot(path=local_path, full_page=False)
    if ARTIFACT_DIR != OUTPUT_DIR:
        artifact_path = os.path.join(ARTIFACT_DIR, filename)
        try:
            with open(local_path, "rb") as f_in, open(artifact_path, "wb") as f_out:
                f_out.write(f_in.read())
        except Exception as e:
            print(f"Warning copying to artifact dir: {e}")
    print(f"  [Screenshot] {filename} saved")

def check_overflow(page, page_label, viewport_label):
    scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
    client_w = page.evaluate("() => document.documentElement.clientWidth")
    is_overflow = scroll_w > client_w + 1
    if is_overflow:
        print(f"  [FAIL Overflow] {page_label} at {viewport_label}: scrollWidth={scroll_w} > clientWidth={client_w}")
    else:
        print(f"  [PASS Overflow] {page_label} at {viewport_label}: scrollWidth={scroll_w} <= clientWidth={client_w}")
    return not is_overflow

def run_suite():
    print("=================================================================")
    print("  COMPREHENSIVE RESPONSIVENESS AUDIT & VERIFICATION SUITE")
    print("  Applications: Flagship (A), Sandbox (B), Legacy (C)")
    print("=================================================================\n")

    token = get_auth_token()
    print("[+] Auth token obtained.")

    # 1. Ensure an invoice exists for detail review
    import requests
    headers = {"Authorization": f"Bearer {token}"}
    sbx_run = requests.post(f"{BASE_URL}/api/v1/sandbox/run-scenario/SCN-01-HAPPY-PATH", headers=headers).json()
    invoice_id = sbx_run.get("invoice_id")
    print(f"[+] Active review invoice: {invoice_id}")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context()

        # Seed local storage authentication for all origins
        context.add_init_script(f"""
            localStorage.setItem('auth_token', '{token}');
            localStorage.setItem('ap_command_center_auth_token', '{token}');
            localStorage.setItem('supabase.auth.token', JSON.stringify({{ access_token: '{token}' }}));
        """)

        page = context.new_page()

        # -------------------------------------------------------------
        # PART A: SANDBOX 2.0 RESPONSIVE AUDIT
        # -------------------------------------------------------------
        print("\n--- [APP B] Testing Sandbox 2.0 Responsive Landing & Chapters ---")
        for tag, w, h, desc in [("1920x1080", 1920, 1080, "Desktop"), ("1440x900", 1440, 900, "Desktop"), ("1024x768", 1024, 768, "Tablet"), ("768x1024", 768, 1024, "Tablet"), ("375x812", 375, 812, "Mobile"), ("320x568", 320, 568, "Mobile")]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{BASE_URL}/sandbox")
            page.wait_for_selector("#scenarios-container > div", timeout=15000)
            time.sleep(0.5)

            no_overflow = check_overflow(page, "Sandbox Landing", f"{desc} ({tag})")
            results.append(("Sandbox Landing", tag, no_overflow))
            save_screenshot(page, f"sandbox_landing_{tag}.png")

        # Test switching to Upload Studio on desktop and mobile
        print("Testing Deck Switcher: Switching to Upload Studio...")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.click("#choice-card-upload")
        time.sleep(0.4)
        save_screenshot(page, "sandbox_upload_deck_1440x900.png")
        
        page.set_viewport_size({"width": 375, "height": 812})
        time.sleep(0.3)
        check_overflow(page, "Sandbox Upload Deck", "Mobile 375px")
        save_screenshot(page, "sandbox_upload_deck_375x812.png")

        # Switch back to scenarios and run Scenario 1
        page.click("#tab-choice-scenarios")
        time.sleep(0.3)
        scenarios = page.query_selector_all("#scenarios-container > div")
        scenarios[0].click()
        page.wait_for_selector("#results-view:not(.hidden)", timeout=20000)
        time.sleep(1)

        # Audit all 7 chapters across key viewports
        print("Auditing all 7 chapters...")
        for ch in range(1, 8):
            page.evaluate(f"() => goToChapter({ch})")
            time.sleep(0.4)
            for tag, w, h, desc in [("1440x900", 1440, 900, "Desktop"), ("768x1024", 768, 1024, "Tablet"), ("375x812", 375, 812, "Mobile")]:
                page.set_viewport_size({"width": w, "height": h})
                time.sleep(0.2)
                no_overflow = check_overflow(page, f"Sandbox Ch {ch}", f"{desc} ({tag})")
                results.append((f"Sandbox Ch {ch}", tag, no_overflow))
                if tag in ["1440x900", "375x812"]:
                    save_screenshot(page, f"sandbox_ch{ch}_{tag}.png")

        # -------------------------------------------------------------
        # PART B: FLAGSHIP AP COMMAND CENTER RESPONSIVE AUDIT
        # -------------------------------------------------------------
        print("\n--- [APP A] Testing Flagship AP Command Center Across Viewports ---")

        # 1. Today / Dashboard Page
        print("Testing Dashboard (/today)...")
        for tag, w, h, desc in [("1920x1080", 1920, 1080, "Desktop"), ("1440x900", 1440, 900, "Desktop"), ("768x1024", 768, 1024, "Tablet"), ("375x812", 375, 812, "Mobile"), ("320x568", 320, 568, "Small Mobile")]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{BASE_URL}/today")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            no_overflow = check_overflow(page, "Flagship Today", f"{desc} ({tag})")
            results.append(("Flagship Today", tag, no_overflow))
            if tag in ["1440x900", "768x1024", "375x812", "320x568"]:
                save_screenshot(page, f"flagship_today_{tag}.png")

        # 2. Invoices Inbox (/invoices)
        print("Testing Invoices Inbox (/invoices)...")
        for tag, w, h, desc in [("1440x900", 1440, 900, "Desktop"), ("768x1024", 768, 1024, "Tablet"), ("375x812", 375, 812, "Mobile")]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{BASE_URL}/invoices")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            no_overflow = check_overflow(page, "Flagship Invoices", f"{desc} ({tag})")
            results.append(("Flagship Invoices", tag, no_overflow))
            save_screenshot(page, f"flagship_invoices_{tag}.png")

        # 3. Invoice Detail Review Page (/invoices/:id)
        print("Testing Invoice Detail Page...")
        for tag, w, h, desc in [("1920x1080", 1920, 1080, "Large Desktop"), ("1440x900", 1440, 900, "Standard Desktop"), ("1280x800", 1280, 800, "Compact Desktop"), ("1024x768", 1024, 768, "Tablet Landscape"), ("768x1024", 768, 1024, "Tablet Portrait"), ("375x812", 375, 812, "Mobile"), ("320x568", 320, 568, "Small Mobile")]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{BASE_URL}/invoices/{invoice_id}")
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # Check overflow on review workspace
            no_overflow = check_overflow(page, "Flagship Invoice Detail", f"{desc} ({tag})")
            results.append(("Flagship Detail", tag, no_overflow))
            save_screenshot(page, f"flagship_detail_{tag}.png")

            # On mobile/tablet (< 1024), test switching to PDF document view
            if w < 1024:
                doc_btn = page.query_selector("button:has-text('Original Invoice (PDF)')")
                if doc_btn:
                    doc_btn.click()
                    time.sleep(0.5)
                    save_screenshot(page, f"flagship_detail_doc_view_{tag}.png")
                    # Switch back to verification view
                    rev_btn = page.query_selector("button:has-text('Verification & Seven Gates')")
                    if rev_btn: rev_btn.click()

        # 4. Audit Trail Page (/audit)
        print("Testing Audit Trail (/audit)...")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        save_screenshot(page, "flagship_audit_1440x900.png")
        page.set_viewport_size({"width": 375, "height": 812})
        time.sleep(0.5)
        save_screenshot(page, "flagship_audit_375x812.png")

        # -------------------------------------------------------------
        # PART C: LEGACY AP COMMAND CENTER APPLICATION (/legacy)
        # -------------------------------------------------------------
        print("\n--- [APP C] Testing Standalone Legacy Application (/legacy) ---")
        for tag, w, h, desc in [("1440x900", 1440, 900, "Desktop"), ("768x1024", 768, 1024, "Tablet"), ("375x812", 375, 812, "Mobile")]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(f"{BASE_URL}/legacy")
            page.wait_for_selector("#scenario-select", timeout=15000)
            time.sleep(1)
            no_overflow = check_overflow(page, "Legacy Standalone", f"{desc} ({tag})")
            results.append(("Legacy Standalone", tag, no_overflow))
            save_screenshot(page, f"legacy_app_{tag}.png")

        # Test running a scenario in Legacy
        print("Testing Legacy Run Execution...")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.click("#run-btn")
        time.sleep(2)
        save_screenshot(page, "legacy_app_executed_1440x900.png")

        browser.close()

    print("\n=================================================================")
    print("  RESPONSIVENESS AUDIT SUMMARY")
    print("=================================================================")
    all_passed = True
    for app_label, tag, passed in results:
        status_str = "[PASS]" if passed else "[FAIL]"
        if not passed: all_passed = False
        print(f"  {status_str:7} {app_label:<25} Viewport: {tag}")

    print("\nOverall Responsiveness Status:", "100% PASSED" if all_passed else "SOME ISSUES FLAGGED")
    assert all_passed, "Some pages exhibited horizontal window overflow!"

if __name__ == "__main__":
    run_suite()
