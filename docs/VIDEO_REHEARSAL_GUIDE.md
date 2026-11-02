# AP Command Center — 5-Minute Video Rehearsal & Interview Defense Guide
## Master Speaking Cues, Anticipated Interview Questions & Live Demo Defense

This guide prepares you for both recording your 5-minute video and defending your engineering decisions during the live follow-up interview with Zamp.

---

## 1. Speech Muscle Memory & Pronunciation Cues

Practice saying these domain and technical terms smoothly before hitting record:

| Term | Phonetic / Spoken Guide | Context / Meaning |
| :--- | :--- | :--- |
| **GSTIN** | *"G-S-T-I-N"* (spell letters) or *"GST-Number"* | Goods & Services Tax Identification Number (15-character Indian tax ID) |
| **MSMED Act** | *"M-S-M-E Act"* or *"M-S-M-E-D Act"* | Micro, Small and Medium Enterprises Development Act, 2006 (Section 15/16) |
| **GRN** | *"G-R-N"* or *"Goods Receipt Note"* | Warehouse delivery confirmation receipt |
| **3-Way Match** | *"Three-way match"* | Reconciling Invoice vs Purchase Order vs Warehouse Goods Receipt |
| **Deterministic** | *duh-TER-mih-nis-tik* | Rule-based code that always yields the identical mathematical result |
| **Probabilistic** | *prah-buh-buh-LIS-tik* | Statistical prediction (how generative AI / LLMs output text) |
| **SHA-256** | *"S-H-A two-fifty-six"* | 64-character cryptographic hash verifying document immutability |
| **Debit Note** | *"Debit note"* | Commercial deduction notice offsetting an overbilled supplier invoice |
| **Pre-accounting** | *"Pre-accounting checkpoint"* | Verifying data BEFORE posting liabilities into ERP or general ledgers |

---

## 2. Common Recording Traps & How to Avoid Them

### Trap 1: Frantic Mouse Jiggling
- **Problem:** Many presenters unconsciously shake or circle the mouse rapidly when speaking, creating distracting visual noise.
- **Fix:** Move the mouse deliberately. Place the cursor on an element, let it rest stationary while you speak, then glide it smoothly to the next interaction.

### Trap 2: Rushing to Beat the Clock
- **Problem:** When trying to fit within 5:00, candidates often speak at 170+ words per minute, sounding anxious and hard to follow.
- **Fix:** Our script is precisely 632 words. At a natural conversational pace of 138 words per minute, it takes **4 minutes 38 seconds**. You have a comfortable 22-second buffer. Take calm, steady breaths.

### Trap 3: Talking Over Screen Loads
- **Problem:** Clicking a button and speaking immediately before the screen finishes loading.
- **Fix:** Click, let the page or modal settle for 0.5 seconds, then deliver the narration line. The visual must lead the audio.

### Trap 4: Making False Claims Under Pressure
- **Problem:** Saying *"This pays the vendor"* or *"This updates SAP"*.
- **Fix:** Keep the boundary clear in your mind: *"This is internal pre-accounting verification and review sign-off. It approves the invoice for external payment batching, but never touches bank rails."*

---

## 3. Verbal Slip Recovery Techniques (During Recording)

If you stumble over a word at minute 3:
- **Do NOT panic or restart from scratch immediately.**
- Simply pause for 2 full seconds in silence, smile, restate the sentence clearly, and keep going.
- Because Loom and screen recordings do not require studio perfection, an authentic, poised recovery demonstrates composure under pressure—a core trait evaluated for Solutions Associates.
- However, if the stumble occurs in the first 45 seconds, simply restart the take. Most candidates nail the final recording on Take 2 or Take 3.

---

## 4. Anticipated Interviewer Follow-Up Questions & Model Answers

In the live follow-up interview, the Zamp evaluators will watch your process run live and grill you on your design decisions. Here is how to defend your architectural choices:

### Question 1: *"Why didn't you just prompt Claude or GPT-4 with all the data and ask it to decide whether to approve the invoice?"*
> **Model Answer:**  
> *"Because LLMs are probabilistic prediction engines, whereas financial liabilities and statutory compliance require deterministic guarantees. If an LLM hallucinates a tax total or misses a 1% price variance on a high-value invoice, the company suffers direct financial leakage.*  
> *In the AP Command Center, we use AI where it shines: perception and unstructured document extraction (reading messy tables and messy formats). But once data is extracted, we transition immediately to deterministic Python logic for 3-way matching, tax arithmetic, and statutory MSMED deadlines. LLMs extract; rules validate; humans decide."*

### Question 2: *"How do you prevent a rogue or tired AP clerk from overriding broken checks and approving an invalid invoice?"*
> **Model Answer:**  
> *"Through Design Invariant D-04: Failed-Gate Override Prevention. If any of the seven validation gates fail—such as an unapproved price variance or a failed QC inspection—the backend API physically rejects approval requests with HTTP 400 Bad Request, and the UI permanently locks the 'Approve Review' button.*  
> *The only permitted path forward is structured triage: raising a debit note, putting the invoice on hold for evidence, or requesting a supplier correction. Financial policy cannot be bypassed with a single click."*

### Question 3: *"Why did you implement dual approval for invoices over ₹5,00,000?"*
> **Model Answer:**  
> *"In enterprise finance, separation of duties is essential to prevent internal collusion and fraud. Invoices below ₹5,00,000 can be signed off by a single AP Lead.*  
> *For invoices equal to or exceeding ₹5,00,000, the system enforces a strict two-step dual control: Step 1 is AP Lead review sign-off, and Step 2 requires executive sign-off from a Financial Controller.*  
> *Crucially, the backend enforces an anti-self-approval invariant: the same user cannot sign both Step 1 and Step 2."*

### Question 4: *"How does the system protect against compliance risks under the Indian MSMED Act?"*
> **Model Answer:**  
> *"Under Section 15 of the MSMED Act, payments to registered Micro and Small enterprises must be settled within 45 days of delivery, or the buyer faces mandatory compounding interest at three times the RBI bank rate under Section 16.*  
> *Our engine automatically calculates the statutory deadline based on invoice receipt date, tracks relative countdowns on the dashboard, and prioritizes expiring invoices. Furthermore, snoozing or holding an exception never resets the statutory countdown."*

### Question 5: *"What are the current limitations of this build, and what would you build next?"*
> **Model Answer:**  
> *"Our current build is an intelligent pre-accounting review checkpoint. Its verified boundaries are clearly defined:*  
> *1. It does not write back to live ERPs like SAP or Oracle; it operates against authoritative ERP reference data snapshots.*  
> *2. It does not wire bank funds; it prepares approved batches for treasury execution.*  
> *If I had two more weeks, I would build:*  
> *First, automated outbound email generation for vendor discrepancy notifications.*  
> *Second, dynamic bounding-box visual highlighting on the PDF viewer canvas so clerks can click an extracted field and jump straight to its coordinates on the original document.*  
> *Third, automated background OCR for degraded scanned PDFs using vision models."*

---

## 5. Rehearsal Routine (Do This Twice Before Recording)

1. **Dry Run (No Recording):** Open `docs/VIDEO_WORD_FOR_WORD_SCRIPT.md` on your phone. Walk through the application with your mouse and speak the lines out loud without recording. Verify where every button is located.
2. **Timed Run:** Set a stopwatch for 5:00. Deliver the script while performing the clicks. Check your split time at the Happy Path (should reach Happy Path approval around `2:10–2:20`).
3. **Record Take 1:** Hit record. Stay calm, speak with steady energy, and trust your preparation.
