# AP Command Center — 5-Minute Video Recording Checklist
## Comprehensive Preflight, Recording & Submission Protocol

Follow this checklist step-by-step to record a clean, confident, professional demonstration video that strictly meets the Zamp Case Study evaluation standards.

---

## 1. System & Environment Setup Checklist

### A. Display & Browser Configuration
- [ ] **Resolution:** Set monitor or capture window to **1920x1080** (1080p) or **1440x900**.
- [ ] **Browser:** Google Chrome, Microsoft Edge, or Brave.
- [ ] **Zoom Level:** Set browser zoom strictly to **100%** (`Ctrl + 0`).
- [ ] **Tabs:** Close all unrelated tabs. Keep only:
  - Tab 1: `http://localhost:5173/` (The live AP Command Center application)
  - Tab 2: (Optional on second monitor / phone) Script & Shotlist timer
- [ ] **Bookmarks & UI Cleanliness:** Press `Ctrl + Shift + B` to hide the bookmarks bar. Clean browser chrome ensures maximum focus on the application.

### B. Audio, Mic & Recording Tool
- [ ] **Microphone:** Use a dedicated headset or directional desktop microphone positioned 6–8 inches from your mouth.
- [ ] **Background Noise:** Turn off air conditioning / fans / loud appliances.
- [ ] **Notification Suppression:** Turn ON Windows Focus Assist / Do Not Disturb:
  - Press `Win + N` $\to$ Set Focus Assist to **"Priority only"** or **"Alarms only"** to prevent Slack/WhatsApp popups.
- [ ] **Recording Software:**
  - **Option 1 (Recommended):** **Loom** (Chrome extension or desktop app). High quality, automatic link generation.
  - **Option 2:** **OBS Studio** (Window Capture or Display Capture at 1080p, 60fps, 6000 kbps).
  - **Option 3:** **Windows Game Bar** (`Win + Alt + R` to start/stop capture).
- [ ] **Mouse Cursor:** Ensure the recorder records the mouse cursor (with gentle click halo or highlighting if supported).
- [ ] **Webcam:** Optional per candidate guide (`"Just you, your screen, and your process running"`). If using Loom, a small circular camera in the bottom-left or bottom-right corner is standard and adds human connection, but screen-only is 100% acceptable.

---

## 2. Application Runtime Preflight Checks

### A. Verify Local Daemons
Confirm both the backend API and frontend dev server are healthy before recording:

1. **Backend Health Check:**
   - Open terminal: `curl http://127.0.0.1:8000/api/v1/liveness`
   - Expected response: `{"status":"ALIVE", ...}`
2. **Frontend Accessibility:**
   - Open `http://localhost:5173/` in your browser.
   - The login screen or dashboard should load in under 1 second.

### B. Pre-Set Authentication Persona
1. Navigate to `http://localhost:5173/`.
2. Under **"Instant Evaluation Access"**, click **"SME AP Lead"** (`sme_lead@company.internal`).
3. You will land immediately on **"Today's AP Operations"** (Dashboard).
4. Verify that the user avatar in the top-right header shows `SME AP Lead (AP_LEAD)`.

### C. Reset Demo Records to Baseline (Before Recording Take)
If you previously clicked *Approve* or *Raise Debit Note* during testing, run this one-second command in PowerShell to restore the baseline state:

```powershell
python scratch/reset_demo_data.py
```

Expected output:
```text
Reset inv_d76401c096d0 (AP-26-009) -> PENDING_APPROVAL
Reset inv_dbfcaf77ba9b (AP-26-011) -> ACTION_REQUIRED
Demo records successfully reset to baseline state.
```

---

## 3. Pre-Recording 10-Second Test Flight

Before recording the full 5-minute take:
1. Hit **Record** on your recording software.
2. Speak the first two sentences of Segment 1:
   *"Every month, a growing company receives hundreds of vendor invoices as messy PDF attachments..."*
3. Move your mouse smoothly across the KPI cards.
4. Stop recording and play it back immediately:
   - Is your voice loud, crisp, and free of background hum?
   - Is the screen text razor-sharp without blur or downscaling artifacts?
   - Does the mouse pointer track smoothly?
5. If yes, you are 100% ready for Take 1.

---

## 4. Live Recording Execution Protocol

Keep a stopwatch or timer running on your phone beside your keyboard:

| Target Time | Shot / Action | Visual Verification |
| :---: | :--- | :--- |
| **0:00 – 0:25** | Dashboard (Problem & Stakes) | Mouse glides across 4 KPI cards. Do not click yet. |
| **0:25 – 0:55** | Invoices Inbox (Solution Architecture) | Click *"Invoices"* in sidebar. Table shows 8 invoices. Hover on row `AP-26-009`. |
| **0:55 – 2:20** | Happy Path Workspace (`AP-26-009`) | Click `AP-26-009`. Point to PDF on left, 4-node lineage on right. Click *"Policy Checks (7/7)"*. Click *"Approve Review"*. Point to safety guarantees. Click *"Cancel"*. |
| **2:20 – 3:30** | Edge Case Workspace (`AP-26-011`) | Click *"Showcase Tour"* in header $\to$ Select Scenario #2. Point to +18.9% markup. Click *"Policy Checks (5/7)"*. Show locked *"Approval Blocked"* button. Click *"Raise Debit Note"*. Click *"Cancel"*. |
| **3:30 – 4:15** | Immutable Audit Ledger (`/audit`) | Click *"Audit"* in sidebar. Point to events with timestamps, user emails, SHA-256 hashes. Click top row to open forensic slide-over drawer with visual diff. |
| **4:15 – 4:40** | Dashboard & Closing Statement | Close drawer, click *"Dashboard"*. Rest cursor over KPI strip. Deliver concluding sentence. Pause 2 seconds. |
| **4:40** | **STOP RECORDING** | End video cleanly between 4:35 and 4:45. |

---

## 5. Post-Recording Submission Verification

Before emailing your submission to the Zamp hiring coordinator:

- [ ] **Duration Check:** Is the final video duration **between 4:20 and 4:55**? (Must be strictly under 5:00).
- [ ] **Content Check:** Did you show the real live application without slides?
- [ ] **Happy Path Check:** Did you demonstrate clean invoice extraction, 4-stage lineage, 7 passing gates, and consequence-aware approval?
- [ ] **Edge Case Check:** Did you demonstrate the +18.9% rate discrepancy, failed QC inspection, and strict failed-gate override prevention?
- [ ] **Tone & Clarity:** Was your delivery confident, clear, and easy for a non-technical Finance Director to understand?
- [ ] **Video Link:** Upload to Loom (or unlisted Google Drive/YouTube) and verify permissions:
  - Set permissions to: **"Anyone with the link can view"**.
  - Test opening the link in an incognito / private browser window.
- [ ] **Repository Link:** Ensure git commits are pushed to your GitHub repository branch:
  - Branch: `handoff/ap-command-center`
- [ ] **Email Format:** Subject: `"ASA Case Study — [Your Name] — PS-1"` containing both links.
