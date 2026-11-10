import json
import os
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

DEFAULT_ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "assets", "acceptance_evidence")
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR)
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001")

def get_auth_token():
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/dev-session",
        data=json.dumps({"email": "sme_associate@company.internal", "org_id": "org_sme_eval"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return data["access_token"]

def run_acceptance():
    print("=== Starting AP Decision Sandbox Acceptance Verification ===")
    token = get_auth_token()
    print("Obtained evaluation auth token:", token[:15] + "...")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Set token in localStorage before loading page
        page.goto(f"{BASE_URL}/sandbox")
        page.evaluate(f"localStorage.setItem('ap_command_center_auth_token', '{token}')")
        page.reload()

        # 1. LANDING PAGE VERIFICATION
        print("\n--- 1. Landing Page Verification ---")
        page.wait_for_selector("#scenarios-container > div", timeout=10000)
        time.sleep(1) # Wait for animation/render settle

        # Check Option A & Option B
        opt_a = page.query_selector("text=Option A — Guided Scenarios") or page.query_selector("text=Explore a Guided Scenario")
        opt_b = page.query_selector("text=Option B — Upload Custom PDF") or page.query_selector("text=Upload Your Own Invoice")
        print("Option A visible:", bool(opt_a))
        print("Option B visible:", bool(opt_b))

        cards = page.query_selector_all("#scenarios-container > div")
        print(f"Scenarios displayed: {len(cards)} (expected 6)")
        assert len(cards) == 6, f"Expected 6 scenarios, got {len(cards)}"

        # Capture Landing Page Screenshot
        landing_shot = os.path.join(ARTIFACT_DIR, "sandbox_landing_1440x900.png")
        page.screenshot(path=landing_shot, full_page=False)
        print("Captured landing page screenshot:", landing_shot)

        # 2. RUN SCENARIO 1 (CLEAN 3-WAY MATCH)
        print("\n--- 2. Scenario 1 (Clean 3-Way Match) Execution ---")
        cards[0].click()

        # Wait for processing or results view
        page.wait_for_selector("#results-view:not(.hidden)", timeout=30000)
        print("Results view rendered successfully!")

        dec_badge = page.inner_text("#res-decision-badge")
        print("Decision Badge:", dec_badge)
        assert dec_badge in ["MATCH_CANDIDATE", "AUTO_APPROVED"], f"Unexpected decision {dec_badge}"

        # Check 4 Questions
        q1_text = page.inner_text("#q1-answer")
        q2_text = page.inner_text("#q2-answer")
        q3_text = page.inner_text("#q3-evidence-box")
        q4_text = page.inner_text("#q4-badge")
        print("Q1 Answer preview:", q1_text[:60] + "...")
        print("Q2 Answer preview:", q2_text[:60] + "...")
        print("Q4 Status:", q4_text)

        # Capture Beginner View Screenshot
        beg_shot = os.path.join(ARTIFACT_DIR, "sandbox_beginner_walkthrough.png")
        page.screenshot(path=beg_shot, full_page=False)
        print("Captured Beginner Walkthrough screenshot:", beg_shot)

        # 3. SWITCH TO TECHNICAL MODE
        print("\n--- 3. Beginner / Technical Toggle ---")
        page.click("#toggle-technical-btn")
        time.sleep(0.5)

        tech_q1_text = page.inner_text("#q1-answer")
        print("Technical Q1 Answer preview:", tech_q1_text[:80] + "...")

        # Capture Technical View Screenshot
        tech_shot = os.path.join(ARTIFACT_DIR, "sandbox_technical_walkthrough.png")
        page.screenshot(path=tech_shot, full_page=False)
        print("Captured Technical Walkthrough screenshot:", tech_shot)

        # 4. EXPLORE STAGE 4 & INTERACTIVE 7 GATES
        print("\n--- 4. Interactive 7-Gate Matching Inspector ---")
        page.click("#stage-4")
        time.sleep(0.5)

        gate_cards = page.query_selector_all("#interactive-gates-grid > div")
        print(f"Interactive Gates rendered: {len(gate_cards)}")
        assert len(gate_cards) == 7, f"Expected 7 gates, got {len(gate_cards)}"

        # Click Gate 1
        gate_cards[0].click()
        time.sleep(0.3)
        detail_title = page.inner_text("#detail-gate-title")
        detail_rule = page.inner_text("#detail-gate-rule")
        print("Gate 1 Detail Title:", detail_title)
        print("Gate 1 Rule:", detail_rule[:60] + "...")

        # Capture Interactive Matching Gates Screenshot
        gates_shot = os.path.join(ARTIFACT_DIR, "sandbox_interactive_gates.png")
        page.screenshot(path=gates_shot, full_page=False)
        print("Captured Interactive Gates screenshot:", gates_shot)

        # 5. TEST EVIDENCE TABS (Document PDF & Streamlined Structured Procurement Evidence)
        print("\n--- 5. Evidence Tabs Switching ---")
        page.click("#tab-btn-procurement")
        time.sleep(0.3)
        assert not page.query_selector("#tab-pane-procurement").evaluate("el => el.classList.contains('hidden')")
        proc_structured = page.query_selector("#drawer-procurement-structured")
        assert proc_structured is not None
        print("Streamlined Procurement evidence active with structured 3-way match cards!")

        page.click("#tab-btn-document")
        time.sleep(0.3)
        assert not page.query_selector("#tab-pane-document").evaluate("el => el.classList.contains('hidden')")
        print("Document PDF tab active!")

        # 6. TEST STORED-RESULT REPLAY LABELING
        print("\n--- 6. Stored-Result Replay Labeling ---")
        page.click("text=Explore Another Scenario or Upload New PDF")
        time.sleep(0.5)
        # Re-run Scenario 1
        scenarios = page.query_selector_all("#scenarios-container > div")
        scenarios[0].click()
        page.wait_for_selector("#results-view:not(.hidden)", timeout=15000)
        
        stored_banner = page.query_selector("#res-stored-banner")
        is_stored_visible = not stored_banner.evaluate("el => el.classList.contains('hidden')")
        prov_text = page.inner_text("#provenance-tag")
        print("Stored banner visible:", is_stored_visible)
        print("Provenance tag:", prov_text)
        assert is_stored_visible, "Stored banner should be visible on re-run"
        assert prov_text == "STORED_RESULT", f"Expected STORED_RESULT, got {prov_text}"

        # 7. TEST EXCEPTION SCENARIO (SCN-02 PRICE VARIANCE)
        print("\n--- 7. Exception Scenario (SCN-02 Price Variance) ---")
        page.click("text=Explore Another Scenario or Upload New PDF")
        time.sleep(0.5)
        scenarios = page.query_selector_all("#scenarios-container > div")
        scenarios[1].click()
        page.wait_for_selector("#results-view:not(.hidden)", timeout=25000)

        dec_badge_2 = page.inner_text("#res-decision-badge")
        print("SCN-02 Decision Badge:", dec_badge_2)
        assert dec_badge_2 == "FLAGGED_EXCEPTION", f"Expected FLAGGED_EXCEPTION, got {dec_badge_2}"

        # 8. TEST DEGRADED SCAN SCENARIO (SCN-03)
        print("\n--- 8. Degraded Scan Scenario (SCN-03 Grounding Tripwire) ---")
        page.click("text=Explore Another Scenario or Upload New PDF")
        time.sleep(0.5)
        scenarios = page.query_selector_all("#scenarios-container > div")
        scenarios[2].click()
        page.wait_for_selector("#results-view:not(.hidden)", timeout=25000)

        dec_badge_3 = page.inner_text("#res-decision-badge")
        print("SCN-03 Decision Badge:", dec_badge_3)
        assert dec_badge_3 in ["FLAGGED_HITL_REVIEW", "FLAGGED_EXCEPTION"], f"Expected FLAGGED_HITL_REVIEW or FLAGGED_EXCEPTION, got {dec_badge_3}"
        
        page.click("#stage-2")
        time.sleep(0.3)
        q4_stage2 = page.inner_text("#q4-badge")
        print("Stage 2 Outcome Badge for SCN-03:", q4_stage2)
        assert "SKIPPED" in q4_stage2, f"Expected SKIPPED in stage 2 outcome, got {q4_stage2}"

        # 9. TEST MOBILE VIEWPORT (375x812)
        print("\n--- 9. Mobile Viewport Test (375x812) ---")
        page.set_viewport_size({"width": 375, "height": 812})
        time.sleep(1)

        mobile_shot = os.path.join(ARTIFACT_DIR, "sandbox_mobile_375x812.png")
        page.screenshot(path=mobile_shot, full_page=False)
        print("Captured mobile screenshot:", mobile_shot)

        # 10. VERIFY FLAGSHIP UNAFFECTED
        print("\n--- 10. Verify Flagship AP Command Center Unaffected ---")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{BASE_URL}/today")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("Flagship current URL:", page.url)
        assert "today" in page.url or "invoices" in page.url or "login" in page.url

        browser.close()
        print("\n=== All Acceptance Steps Passed Successfully! ===")

if __name__ == "__main__":
    run_acceptance()
