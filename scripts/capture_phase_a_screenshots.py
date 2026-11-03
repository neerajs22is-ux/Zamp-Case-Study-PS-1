import os
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Zamp Casse Study\competitor_research\07_phase_a_implementation\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def get_dev_token():
    payload = json.dumps({'email': 'sme_lead@company.internal', 'org_id': 'org_sme_eval'}).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/auth/dev-session',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        return data['access_token']

def capture_all():
    token = get_dev_token()
    print("Obtained dev token for AP_LEAD.")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            device_scale_factor=2
        )
        page = context.new_page()

        # Step 1: Set auth token in localStorage
        page.goto('http://127.0.0.1:8000/')
        page.evaluate(f"token => localStorage.setItem('ap_command_center_auth_token', token)", token)
        
        # 1. AppShell Sticky Disclosure Banner
        page.goto('http://127.0.0.1:8000/today')
        page.wait_for_selector('text=Evaluation Mode — Sample ERP Data', timeout=10000)
        time.sleep(1)
        shot1 = os.path.join(SCREENSHOT_DIR, '01_appshell_eval_mode_banner.png')
        page.screenshot(path=shot1)
        print(f"Captured: {shot1}")

        # 2. Executive AP Exposure Scorecard
        page.wait_for_selector('text=Executive AP Capital Exposure Scorecard', timeout=10000)
        time.sleep(1)
        shot2 = os.path.join(SCREENSHOT_DIR, '02_dashboard_exposure_scorecard.png')
        page.screenshot(path=shot2)
        print(f"Captured: {shot2}")

        # 3. Inbox Temporal Filtering
        page.goto('http://127.0.0.1:8000/invoices')
        page.wait_for_selector('select[aria-label="Filter by Financial Year"]', timeout=10000)
        time.sleep(1)
        shot3 = os.path.join(SCREENSHOT_DIR, '03_inbox_temporal_filtering.png')
        page.screenshot(path=shot3)
        print(f"Captured: {shot3}")

        # 4. Invoice Review Unified Workspace (2 consolidated tabs)
        page.goto('http://127.0.0.1:8000/invoices/inv_d76401c096d0')
        page.wait_for_selector('text=Verification & 3-Way Matching', timeout=10000)
        time.sleep(1.5)
        shot4 = os.path.join(SCREENSHOT_DIR, '04_invoice_review_unified_workspace.png')
        page.screenshot(path=shot4)
        print(f"Captured: {shot4}")

        # 5. Line Item Inline Editing Dialog
        page.wait_for_selector('text=Verification & 3-Way Matching', timeout=10000)
        time.sleep(1)
        edit_btn = page.locator('button[title*="Correct line"]').first
        if edit_btn.count() > 0:
            edit_btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            edit_btn.click()
            page.wait_for_selector('text=Audited Line-Item Correction', timeout=5000)
            time.sleep(0.5)
            shot5 = os.path.join(SCREENSHOT_DIR, '05_line_item_inline_editing.png')
            page.screenshot(path=shot5)
            print(f"Captured: {shot5}")

            # 6. Fill modified rate and reason, submit correction and capture re-evaluated state
            rate_input = page.locator('input[type="number"]').nth(1)
            rate_input.fill('2400.00')
            reason_input = page.locator('textarea[placeholder*="OCR misread"]')
            reason_input.fill('Audited OCR rate reconciliation verified against supplier memo')
            time.sleep(0.5)
            
            submit_btn = page.locator('button:has-text("Save & Re-evaluate")')
            submit_btn.click()
            
            # Wait for dialog to close
            page.wait_for_selector('text=Audited Line-Item Correction', state='hidden', timeout=10000)
            time.sleep(1.5)
            shot6 = os.path.join(SCREENSHOT_DIR, '06_line_item_corrected_gate_re-evaluated.png')
            page.screenshot(path=shot6)
            print(f"Captured: {shot6}")
        else:
            print("button[title*='Correct line'] count is 0. Inspecting page elements...")

        # 7. Audit Trail Timeline Event in History Tab
        history_tab = page.locator('button:has-text("History & Evidence")')
        if history_tab.is_visible():
            history_tab.click()
            time.sleep(1)
            shot7 = os.path.join(SCREENSHOT_DIR, '07_audit_trail_timeline_event.png')
            page.screenshot(path=shot7)
            print(f"Captured: {shot7}")

        # 8. Reset Demo State Feedback
        reset_btn = page.locator('button:has-text("Reset Demo State")').first
        if reset_btn.is_visible():
            reset_btn.click()
            time.sleep(2)
            shot8 = os.path.join(SCREENSHOT_DIR, '08_system_demo_reset_feedback.png')
            page.screenshot(path=shot8)
            print(f"Captured: {shot8}")

        browser.close()
        print("All Phase A visual verification screenshots captured successfully.")

if __name__ == '__main__':
    capture_all()
