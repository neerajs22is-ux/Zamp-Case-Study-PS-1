# AP Command Center: Comprehension and Demo-Readiness UX Audit

Repository: neerajs22is-ux/Zamp-Case-Study-PS-1-, branch handoff/ap-command-center. Audit date: 2 November 2026. This is an audit and recommendation document. No code was changed.

## How to read this audit (evidence base and limits)

Every claim that matters carries a tag:

- **\[V\]** Verified. I read it directly in a file listed below.
- **\[S\]** Reported by the repo's own FRONTEND\_UX\_IMPLEMENTATION\_SPEC.md. I could not verify it independently.
- **\[?\]** Unknown. Someone needs to check before relying on it.

**What I read:** README.md, docs/AP\_BUSINESS\_RULES.md, docs/KNOWN\_LIMITATIONS.md, the first half of FRONTEND\_UX\_IMPLEMENTATION\_SPEC.md (it was cut off after its Invoices page section, so its demo-workspace section is unread), frontend/src/pages/InvoiceDetailPage.tsx (about the first 1,000 of 1,255 lines: header, tour, verdict banner, document pane, and the Matching, Gates and Extracted Fields tabs), and frontend/src/pages/InboxPage.tsx.

**What I could not do:** run the application, read backend or engine code, or open the Dashboard, Connections, Audit, Team, Source Records pages, StatusBadge, fixtures or the phase reports. GitHub's tree and raw views block automated access. Findings about the Invoice Detail and Inbox screens are strong. Findings about other screens rest on the repo's own spec and are tagged \[S\].

**Documents disagree with the code.** The repo's UX spec was written against commit cda5c44 (1 Nov 2026). It says the review workspace has no PDF viewer, no keyboard handlers, no reject action and no inbox paging. The branch I read has an embedded PDF iframe \[V\], keyboard shortcuts \[V\], a REJECT\_INVOICE action in the UI \[V\], reason templates \[V\] and Prev/Next paging \[V\]. Either the frontend moved after the spec, or the spec describes another build. I trust code over documents. Spec findings about the backend (ingestion not wired, seeded decisions, empty ERP tables) are load-bearing for the demo and I flag them as \[S\] throughout. The builder should confirm them first (see section 11).

This audit does not repeat the existing spec's layout, onboarding and navigation redesign. It adds what the spec lacks: the explanation layer, consequence-aware actions, a copy-truth pass, and a demo narrative. Where the spec already has the right answer I endorse it by section number.

## 1. Executive UX diagnosis

**Can someone who has never worked in AP open this app, understand what it is doing and why, and explain it to someone else? Not today.**

A newcomer can follow the screens. The verdict banner on the invoice page is genuinely good: it says what state the invoice is in and what to do. After ten minutes they could say "there are seven checks and I should fix whatever failed." They could not say the sentence that makes the product make sense: **"We only approve when what the supplier billed, what we ordered, what actually arrived and whether it passed inspection all agree."** The cause is not visual design. It is five specific problems.

1. **The UI explains procedure, not purpose.** getRequiredNextAction() says "Obtain QC release certificate from warehouse" \[V\]. Nothing says what a QC certificate is or why an invoice waits for one. humanGateName() translates gate names but keeps the acronyms inside the translation: "Goods receipt (GRN) confirmed in ERP" \[V\].
2. **The central relationship is never drawn.** The tab called "Matching & Lines" shows supplier facts, billed lines (qty, rate, total) and a two-line payable waterfall. It shows no PO, GRN or QC data at all \[V\]. The product's core idea, comparing the invoice against three of the company's own records, has no visual and no side-by-side. The README says Pane 2 compares billed lines to PO contracted rates \[V\]; the code does not.
3. **The copy contradicts itself and the product's real boundaries.** This is the largest trust and demo risk (table below).
4. **Development-process language leaks into the product.** "Gate Overrides Disabled (D-04 Deferred)" is a banner badge. "Tier 2 gate overrides (D-04) are deferred and disabled" is an error message. "In accordance with production truth rules, zero fake records exist" is an empty state. These are builder governance decisions. A newcomer learns nothing from them, and a demo audience learns the product is unfinished.
5. **The tour teaches the layout, not the workflow.** Its six steps are pane names plus implementation detail ("300s presigned URL", "AWS Bedrock Mantle") \[V\]. It runs on whatever invoice is open, which may be a clean one, so the exception path is never shown. It starts only from a button that is hidden below the sm breakpoint (hidden sm:inline-flex) or a ?tour=true URL parameter \[V\].

### Contradictions between UI copy and source of truth

| # | Where | UI says | Source of truth says | Risk |
| --- | --- | --- | --- | --- |
| C1 | Tour step 3 \[V\] | "...from SAP S/4HANA with strict 0.00% quantity and 2.50% price variance thresholds" | Gate 6 is 1.50% price tolerance (AP\_BUSINESS\_RULES; the same file labels the gate "±1.5%"). README: no live SAP, evaluation tenant | Wrong number, and implies live SAP |
| C2 | Tour step 5 \[V\] | "Invoices exceeding ₹1,00,000 enforce dual approval" | Threshold is ₹5,00,000 (rules doc; spec cites the config default) | Narrator quotes the wrong control threshold |
| C3 | Verdict banner title \[V\] | "Invoice Approved for Payment Run" | The banner's own body says no payment or ERP posting happened; no export code exists \[S\] | The headline alone implies payment |
| C4 | Matching tab footnote \[V\] | "computed strictly against synchronized SAP S/4HANA ERP records... displays unavailable rather than zero" | The tab renders no comparison at all \[V\]. No code populates PO/GRN/QC tables and there is no ERP sync endpoint \[S\] | Promises a comparison and a live source the tab does not show |
| C5 | Extracted Fields tab \[V\] | Header "Mantle Bedrock OCR" plus a Confidence column | Extraction is LLM-based (README). Seeded confidences are fixed constants, 0.99 and 0.95 \[S\] | Confidence reads as a measurement; "OCR" mislabels the method |
| C6 | Duplicate handling \[V\] | Gate 7 next action: "execute Set Aside (Quarantine)"; Reject template: "Duplicate invoice submission..." | State machine: Gate 7 failure goes to REJECTED | Three different dispositions for one case |
| C7 | Reject action \[V\] | Button and R shortcut send REJECT\_INVOICE | Spec: backend has no such action; unknown action strings fall into an else branch and are accepted \[S\] | May silently record the wrong state \[?\] |
| C8 | Second approver \[V\] | "A distinct Financial Controller or System Admin must render secondary sign-off" | Rules doc says Controller; spec says the server only requires a different user \[S\] | Narrator claims a control the server may not enforce |
| C9 | Tour step 5, README | "complete cryptographic audit trail" | Append-only table protected by a DB trigger (README). No hash chain seen | A technical interviewer asks where the chain is. The SHA-256 is of the document and is real |
| C10 | KNOWN\_LIMITATIONS, README | "no keyboard shortcuts"; "no pre-populated reasons"; asks reviewers to add hotkeys | Code has both \[V\] | Docs misdirect reviewers and undermine trust |

Other vocabulary leaks \[V\]: "Inspecting document storage, 7-gate validation state & audit events" (loading text), "tenant partition under active enterprise isolation rules" (not-found text), "Server-paginated operational ledger" (inbox subtitle), "Binding Production Engineering Specification" (footer) \[S\].

### What already works and should be kept

Verdict-first banner; failed gates sorted to the top; a plain-language name per gate; a required next action per failed gate; reason templates per action; the explicit "no payment or ERP posting" statement; approval blocked while any gate fails, with an explanation; Auditor read-only handling; SHA-256 chip; en-IN currency formatting. The full list is in section 12.

## 2 and 3. First-time-user walkthrough and screen-by-screen comprehension gaps

The journey and the screens are the same path, so one table serves both deliverables. For each stage it records what the newcomer sees, what they cannot answer, and the evidence.

| Stage | What the newcomer sees now | What they cannot answer | Evidence |
| --- | --- | --- | --- |
| 1. Login and workspace | Google sign-in; dev quick-login by role; "request access" by typing an org ID | What the product is. What a workspace is. What their role may do | \[S\] AuthScreen |
| 2. Today | Four KPI tiles and raw stage and decision lists; copy says "5-way reconciliation" | What to do first. How stage differs from decision. Why 5-way when there are 7 checks | \[S\] DashboardPage |
| 3. Invoice inbox | Table with one "Workflow Status" badge. Filters list raw enums (RECEIVED, VALIDATING, ACTION\_REQUIRED...). MATCH\_CANDIDATE, PENDING\_APPROVAL and INTERNAL\_APPROVAL\_COMPLETE are not offered. "MSME Statutory Due" shows in red for every dated row. Load errors go to console.error only | Which invoices need me. What a status means. What MSME is. Why everything is red | \[V\] InboxPage L52-56, filters, MSME column |
| 4. Opening an invoice | Header chips, verdict banner, a hidden-on-small Tour button | What the case is in one story. Where AI stops and rule-based checks begin | \[V\] InvoiceDetailPage |
| 5. Extracted information | Table: field, value, page, confidence; labelled "Mantle Bedrock OCR" | Which fields feed which checks. Whether low confidence matters. Why extraction matters | \[V\] Details tab |
| 6. PO and GRN matching | "Matching & Lines": supplier facts, billed lines, waterfall. No PO or GRN data | What was ordered, what arrived, how they differ. This is the core question | \[V\] Tab 1 |
| 7. QC verification | Appears only as one gate row: "Quality inspection (QC) accepted" | What QC is, who produces it, why it blocks payment | \[V\] humanGateName |
| 8. Policy gates | "n of 7 checks passed" bar; PASS/FAIL chips; notes; evidence ID; Required Action. Cards have three style branches but only PASS and FAIL are named | Why each check exists. Why some failures are fixable and some fatal. What the amber state means. Tab says "Policy Gates", cards say "Check #" | \[V\] Gates tab |
| 9. Exceptions | Banner lists failing checks with next actions. Exceptions page never empties after actions | The cause in plain words (note text is engine output \[?\]). What each path leads to | \[V\] banner; \[S\] F-05 |
| 10. Hold, correction, quarantine, reject | Action selection, reason template chips, mandatory reason of at least 3 characters | What each action does. What it does not do (e.g. supplier is not emailed). Who is next. Whether it can be undone | \[V\] templates and shortcuts; action panel markup not seen |
| 11. Approval and dual approval | Banner states; "Dual Control Active" chip | What approving means. Why two people. The threshold (₹1L in tour vs ₹5L in rules). Who the second person is | \[V\] C2, C3, C8 |
| 12. Audit trail | History tab with count. Audit page shows raw user IDs and hides before/after state | What it proves. Who did what in human terms | \[S\] F-12 |
| 13. Gmail and ERP | Connections page holds upload, files, four cards and quarantine. ERP "CONNECTED" means configuration present, not data synced. Gmail card reads server-level status | Whether data is flowing. What the ERP supplies to matching. That import is manual, not automatic | \[S\] F-08, F-10 |
| 14. Reference data and team | Source Records are empty by construction. Team page has invite but no member list | Where PO/GRN/QC records come from. Who has access | \[S\] F-10, F-11 |

**Newcomer test result:** after this journey a person can name the screens but cannot answer "why does this check exist", "what happens if I click Hold" or "what does approved mean" without asking the builder. That is the gap the rest of this audit closes.

## 4. Terminology and business-concept education audit

### Concepts that appear without adequate explanation

| Concept | Where it appears | What a newcomer needs (definition, then why it matters) |
| --- | --- | --- |
| Purchase order (PO) | Header chips, gate 2, line context | The company's own written order to a supplier: what to buy, how many, at what price. *An invoice with no valid PO may be unauthorised spending.* |
| GRN (goods receipt note) | Gate 3 text | The warehouse's record of what physically arrived. *Stops payment for goods that never came or came short.* |
| QC certificate | Gate 4 text | The inspection result for delivered goods. *Stops payment for goods that failed quality checks.* |
| Three-way match | README, tour | Compare what was billed (invoice) with what was ordered (PO) and what was received (GRN). This product also requires quality acceptance (QC). *Precision matters in interviews: the textbook version is invoice, PO, receipt; QC is this product's addition.* |
| Tolerance | Gate 6 label, Gate 5 | Small allowed differences (1.5% on price, ₹20 on tax rounding) so trivial gaps do not create work. Values should come from configuration, not typed copy |
| IGST vs CGST+SGST | Gate 5, extracted fields | India's tax split. Same-state supply is split equally into CGST and SGST. Different-state supply uses IGST. The first two digits of the GSTIN give the state. *A wrong split usually means asking the supplier to reissue.* |
| MSME statutory due | Inbox column, header chip | A legal payment deadline for small suppliers (45 days, per the rules doc). *Edge cases are deferred (R-01), so the UI must not read as legal advice.* |
| Dual control | Banner chip, tour | Large invoices need two different approvers so one person cannot push through a mistake or fraud. Threshold ₹5,00,000 |
| Approve | Banner, action | AP's internal review is complete. Nothing is paid, posted or exported by this system |
| Hold pending evidence | Action | Pause while waiting for a document (e.g. receipt). The invoice stays unresolved |
| Request supplier correction | Action | Records that the supplier must send a corrected invoice. The system does not contact the supplier |
| Debit note, Escalate | Actions | Debit note: a document reducing what the company owes. Escalate: asks someone senior to decide. Whether either produces a document or routing is \[?\] |
| Quarantine ("Set aside") | Action, tab | Not a payable invoice (receipt, statement, unreadable file). No liability is recorded |
| Duplicate check | Gate 7 | Same file hash, or same supplier GSTIN, invoice number and financial year |
| Extraction confidence | Fields tab | How sure the reading was. Seeded values are constants \[S\], so do not present them as measured |
| Stage vs decision | Inbox, Today | Two internal fields. A newcomer should see one status |
| HITL | Docs, status | "Needs a person to check" |

### Inconsistent terms that must be unified

| Concept | Variants in use \[V\] | Recommended single term |
| --- | --- | --- |
| Counterparty | Supplier (UI), Vendor (Gate 1, rules, vendor\_gstin) | Supplier |
| The checks | Policy gates, Checks, Check #, Validation gates, Match gates | Checks ("automatic checks") |
| Amount | Total Billed, Net Payable, Net Authorizable Payable | One name, and only call it "net" if something is deducted (the waterfall deducts nothing) |
| Set aside | Quarantine, Set Aside, QUARANTINE | Set aside |
| Ask supplier to fix | Request Supplier Correction, Ask Supplier to Correct | Ask supplier to correct |
| Approved | Approved for Payment Run, Internal approval, MANUALLY\_APPROVED | "Approved by AP" (nothing paid) |
| Receipt | GRN, Goods receipt, Warehouse receipt | Goods receipt (GRN) on first use per screen |

### Meaning of the system states

Gate cards render three style branches (pass, fail, and an amber else-branch) but nothing on screen defines the third state or says what PENDING means \[V\]. The inbox badge merges stage and decision, and the spec confirms several seeded values render as an unknown purple badge \[S\]. The fix (a single status vocabulary and a legend) is in recommendations R5 and R8.

## 5. Workflow and information architecture recommendations

The repo's spec already proposes the right shell: a sidebar of Today, Invoices, Approvals, Audit and Settings; a real URL router; and one status vocabulary driven by a pure statusFor() function (spec sections 3.1 to 3.3 \[S\]). I endorse those and do not repeat them. The additions below address comprehension.

**5.1 Reorder the invoice tabs into the order a person thinks.** Today the tabs are Matching, Policy Gates, Extracted Fields, Audit Trail \[V\], mapped to keys 1 to 4. A newcomer's mental model is Read, Compare, Check, Record. Proposed: **What we read** (extracted fields), **Does it match?** (the three-way card), **Checks** (all seven, grouped), **History**. The decision panel stays visible on every tab. Remap keys 1 to 4 and update the shortcut help.

**5.2 Group the seven checks into three questions.** This is presentation only; the engine order and gate numbers do not change. The grouping carries meaning the flat list hides, because the rules doc routes failures differently \[V\]:

| Question the reviewer is really asking | Checks | If it fails (per AP\_BUSINESS\_RULES) |
| --- | --- | --- |
| Is this a legitimate, new bill? | 1 Supplier registered, 7 Not a duplicate | Rejection path. Not fixable by waiting |
| Does it match what we ordered and received? | 2 PO valid with balance, 3 Goods received, 4 Quality accepted, 6 Price and quantity within tolerance | Exception. Fixable with evidence or a corrected invoice |
| Is the tax right? | 5 GST arithmetic and state split | Exception. Ask the supplier to reissue |

**5.3 Make "AI, rules, human" the spine of the page.** The README's whole architectural pitch is a probabilistic reader plus deterministic guardrails \[V\]. The UI never shows the boundary. Label each region with a small provenance chip: *Read by AI* (extracted fields), *Rule-checked, no AI* (checks), *Human decision* (action panel), *Recorded* (history). Never label confidence as a measured accuracy.

**5.4 Explain at the point of decision, not the point of display.** Priority of explanation surfaces: (1) the action panel, (2) the failing gate card, (3) the verdict banner, (4) the matching tab, (5) glossary popovers. A newcomer rarely reads a definition for something they are not yet deciding about.

**5.5 Fix the missing relationships.** Five links are absent from the screens:

- Invoice to supplier master: gate 1 passes or fails against a supplier record the reviewer never sees.
- Invoice to PO, GRN and QC: the three-way card in section 6.
- Gate to evidence: evidence\_source\_id renders as a raw code \[V\]. Render it as a plain label ("Purchase order PO-1234") with a link where a record exists.
- Action to resulting state: after Hold or Ask-supplier the reviewer should see "Status is now: Waiting for supplier". The spec says all of these collapse into ACTION\_REQUIRED \[S\], which needs B-03 to fix properly.
- First approval to second approval: who signed first, who must sign next, and why.

**5.6 Inbox.** Adopt the spec's status vocabulary and tabs. Additionally: show MSME due dates in red only when due within a stated window (currently every dated row is red \[V\]); rename the row action "Inspect" to "Review"; rename "Sync Mailbox" to "Import from Gmail" and state that import is manual (the spec says no scheduling exists \[S\]); replace the subtitle with one plain sentence; surface load errors in the page instead of console.error \[V\].

**5.7 Connections.** Give each connection a one-sentence job and a consequence of absence. ERP: "Supplies purchase orders, goods receipts and quality records for matching. Without them checks 2 to 4 cannot pass." Gmail: "Imports invoice PDFs when you press Import. It does not run automatically." Show "Configured" for the ERP, not "Connected", because the spec says the flag reflects environment configuration and no sync exists \[S\].

## 6. Proposed contextual education system

**Design rule:** at most three explanation surfaces per screen, all drawing from one content file. Not tooltips everywhere.

1. A **case story strip** at the top of an invoice (what this is, what the system did, what it needs from you).
2. A **consequence-aware action panel** at the decision point.
3. **First-use terms** underlined once per screen, opening a short popover.

Everything else (why-lines on gates, the status legend, the three-way card) is part of those three or sits behind a "Why this matters" disclosure.

**Single source of truth.** Create frontend/src/content/concepts.ts holding every definition, every "why it matters", every action consequence and every threshold. The tour, the glossary, the demo guide and the gate cards all read from it. This is what prevents contradictions C1, C2 and C10 from recurring. Thresholds (dual-approval amount, price tolerance, rounding tolerance) should come from a small read-only policy endpoint backed by the same settings the engine uses (DUAL\_APPROVAL\_THRESHOLD\_INR and ROUNDING\_TOLERANCE\_INR exist per the rules doc \[V\]). A string literal like "₹1,00,000" inside JSX should become impossible.

### 6.1 Case story strip (replaces the verdict banner's second paragraph)

Keep the verdict headline and colour. Add a short story built from fields the page already has (invoice, vendor\_name, po\_reference, failed gates' notes). Example for an exception (values illustrative):

> **What this is.** A ₹X invoice from {supplier} against PO {po}. **What the system did.** Read the PDF (AI), then ran 7 rule-based checks. 6 passed. **What is wrong.** {gate note: billed price on line 2 is above the PO price by more than the 1.5% allowed}. **What we need from you.** Decide how to resolve it. Nothing is paid by this system either way.

For a clean invoice: "All 7 checks passed. The invoice agrees with the order, the receipt and the inspection. It needs your approval." For a not-yet-processed invoice, see R10.

### 6.2 Three-way match card (top of the "Does it match?" tab)

The missing relationship. Render only the links the data supports:

```
  SUPPLIER BILLED          WE ORDERED              WE RECEIVED            PASSED INSPECTION
  Invoice INV-001   <->    PO-1234           <->   GRN-5678         <->    QC certificate
  qty 100 @ ₹500         qty 100 @ ₹480          qty 90 received        status: ACCEPTED
  Check 2,6: price +4.2%   Check 3: 10 short       Check 4: passed
  ✗ outside 1.5%          ✗ billed 100, got 90     ✓
```

(Illustrative values.) Each link shows the compared values, the check number and a pass or fail mark, with one "Why this matters" line. Honesty constraints: the spec says the API returns no PO lines and no code fills the PO/GRN/QC tables \[S\]. Until a backend change (spec B-05) exposes line-level records, build the card at **gate level**: use each gate's notes and evidence reference (the API returns them but the UI never renders them \[S\]), and write "No goods-receipt record on file" when the gate says so. Never draw a comparison the data cannot support.

### 6.3 Gate cards that teach

Each card gets a one-line **Why this check exists** (visible) and **What failure usually means** (inside the expander). Content:

| # | Check | Protects against | Fails when \[V rules doc\] |
| --- | --- | --- | --- |
| 1 | Supplier registered and active | Paying unknown or suspended suppliers | GSTIN or PAN does not match an active supplier record, or status is suspended |
| 2 | Purchase order valid | Spending nobody authorised, or beyond the order's value | No PO reference, or remaining PO balance is below the invoice amount |
| 3 | Goods received | Paying for goods that never arrived | No goods receipt, or received quantity is below billed quantity |
| 4 | Quality accepted | Paying for goods that failed inspection | Inspection certificate rejected or still pending |
| 5 | GST adds up | Tax errors that make the invoice wrong to book | Total differs by more than ₹20, or wrong IGST vs CGST+SGST split |
| 6 | Price and quantity within tolerance | Price creep and over-billing | Unit rate above PO by more than 1.5%, or quantity above remaining PO quantity |
| 7 | Not a duplicate | Paying the same bill twice | Same file hash, or same supplier GSTIN, invoice number and financial year |

Define every state in a legend opened from any chip. PASS: the rule was satisfied. FAIL: the rule was not satisfied and approval is blocked. The amber third state: name it or remove the branch. If it does not exist in the data, delete the style branch so the UI cannot show a state with no meaning \[?\].

### 6.4 Consequence-aware action panel

Replace the bare action list with a selection that shows, before the user commits, **what gets recorded, what does not happen, and who acts next**. Copy for items marked \[?\] must stay conditional until the builder confirms the behaviour. Never promise functionality the backend does not have.

| Action | What the system records | What it does NOT do | Who acts next |
| --- | --- | --- | --- |
| Approve | Under the threshold: "Approved by AP". At or above ₹5,00,000: first approval recorded, waits for a different second approver \[V\] | Pay, post to the ERP, export, or email anyone \[V\] | Payment is handled outside this system |
| Hold for evidence | Reason saved; invoice stays open \[V\] | Notify the warehouse or set a reminder \[?\] | You, when the evidence arrives |
| Ask supplier to correct | Reason saved: supplier must send a corrected invoice \[V\] | **Contact the supplier.** No supplier communication exists | You contact the supplier yourself |
| Raise debit note | Reason saved \[S\] | Generate a debit note document \[?\] | You, outside the system |
| Escalate | Reason saved \[S\] | Route or notify a manager \[?\] | You tell the person |
| Set aside | Marked not payable; no liability recorded \[V\] | Delete anything; the file stays in the audit trail | Nobody; closed |
| Reject | Rejection recorded (state machine says terminal) \[V rules\] | Notify the supplier. Backend support itself is unconfirmed \[S, C7\] | Nobody; closed |

Pre-click sentence pattern: **"\[Action\] will \[what is recorded\]. It will not \[what people might assume\]. Next: \[who\]."** Example: "Ask supplier to correct will record that this invoice needs a corrected version. It will not email the supplier; you contact them. The invoice stays open until resolved."

The approval confirmation must read the threshold from configuration: "This is ₹X, above the ₹5,00,000 limit, so a second person must also approve. You will be recorded as the first approver."

### 6.5 First-use terms and the glossary

A single Term component underlines a term the first time it appears on a screen and opens a popover: one-sentence definition, one-sentence "why it matters", and a link to a one-page "AP in five minutes" explainer that reuses the same content. Limit the vocabulary to the 18 concepts in section 4. Terms inside the tour, banners and gate text go through the same component so definitions never diverge.

### 6.6 Progressive disclosure rules

- **Level 1 (always visible):** one sentence, plain words, no acronym without its expansion on first use.
- **Level 2 ("Why this matters"):** the protects-against line and the consequence.
- **Level 3 ("Technical details"):** evidence IDs, SHA-256, signed-URL lifetime, raw stage and decision values, model name.

The current page puts Level 3 material ("300s presigned URL", Bedrock model names, evidence codes) at Level 1 and Level 2 material nowhere.

### 6.7 Interaction, within what the product can really do

Useful: a "See a passing example" link on any failed check (demo workspace only) that opens a clean seeded invoice; a "What happens next" outcome strip after each action. Not recommended: interactive what-if simulations. The engine is not exposed to the UI, and the spec says seeded decisions are labelled by scenario, not computed \[S, F-02\], so a simulator would fabricate behaviour.

## 7. Recommended end-to-end demo experience

### 7.1 Claims envelope (what the narrator may and may not say)

| May say \[source\] | Must not say \[reason\] |
| --- | --- |
| An AI model reads PDF invoices and extracts fields \[README\] | "Connected to SAP" or "live ERP data". No sync exists and PO/GRN tables are seeded \[S F-10\] |
| Seven rule-based checks, written in code, decide pass or fail with no AI involved \[README, rules doc\] | "Upload an invoice and watch it process." Upload creates a Received record; processing is not wired in the web app \[S F-01\] |
| A human decides; the AI never approves anything \[README\] | "99% confidence" as a measured accuracy. Seeded values are constants \[S F-02\] |
| Invoices at or above ₹5,00,000 need two different approvers \[rules doc\] | That the second approver must be a Controller, unless the builder confirms the server enforces it \[S\] |
| Approval means internal AP review is complete; nothing is paid or posted \[V\] | "Payment run", "payment scheduled", or any export to treasury \[S\] |
| The audit log is append-only, enforced by a database trigger \[README\] | "Cryptographic audit trail" unless a hash chain exists \[?\] |
| The uploaded document is hashed with SHA-256 and duplicates are detected by hash or by supplier + invoice number + financial year \[rules doc\] | The system emails suppliers or chases them automatically |
| Auditors are strictly read-only \[README, spec\] | Gmail "automatically ingests". Import runs when pressed \[S\] |

Put the left column in the product as a visible **"What this system does and does not do"** panel (reachable from the sidebar and the demo guide), so the narrator can point at it instead of memorising it.

### 7.2 Narrative arc: one question, five outcomes

The story is a single question a company asks before paying any supplier: **"Should we pay this bill?"** Each case teaches one concept, shows one decision, and states one thing the system deliberately does not do.

| Case | Concept introduced | Decision shown | System boundary stated |
| --- | --- | --- | --- |
| A. A clean invoice | Three-way match: billed = ordered = received = inspected | Approve | Approval is not payment |
| B. A price above the order | Tolerance (1.5%) and why a small gap still stops payment | Ask supplier to correct | The system does not email the supplier |
| C. Goods not received yet (or QC pending) | Why paying before delivery is a loss | Hold for evidence | Nothing is chased automatically |
| D. A duplicate, or a payment receipt | Duplicate detection; documents that are not bills | Reject or Set aside | Receipts create no liability |
| E. A large invoice | Dual control: two different people | First approval, then second approver (different user) | Anti-self-approval is enforced; no payment follows |
| Finale. Auditor view | Audit trail shows who, what, when, why | Read-only inspection | The system records decisions, it does not pay |

### 7.3 Product support needed for the demo

- **Demo guide panel** (collapsible, ?demo=1): case list with progress (Case 2 of 6), a one-sentence talk track per step, and a link to the claims panel. Content lives in one scenarioGuide.ts, reading from concepts.ts. The spec proposes a demo workspace banner and guide panel in its section 7, which I could not read; reconcile this design with it rather than building two.
- **Persistent banner** in the evaluation workspace: "Evaluation workspace: synthetic data. No payments are made and no ERP is connected."
- **Scenario-aware tour** (R11): the tour opens on the case's invoice and highlights what that case teaches.
- **Scenario coverage.** The demo needs at least one seeded invoice per case. Only CLEAN\_3WAY\_MATCH and the payment-receipt quarantine are confirmed by the spec \[S\]. The builder must confirm that a price variance, a missing GRN or pending QC, a duplicate, a bad GST split and a ≥₹5,00,000 invoice exist, or add them to engine/sme\_eval\_setup.py. I did not open the 40-document corpus or the evaluation report. Quote evaluation figures only after reading them.
- **The live-upload trap.** An interviewer will ask to upload a PDF. If processing is still unwired \[S\], the product must show an honest "Received, waiting for extraction" state (R10), and the narrator needs a rehearsed answer. Decide before recording: either wire the ingestion job to the engine (spec B-01) or keep the claim to the seeded evaluation tenant.

## 8. Suggested demo script for a non-AP expert

Target length: 9 minutes. Use roles rather than persona names: the README names Priya Sharma and Rajesh Nair, while the spec says the seed uses display names like "SME AP Lead" \[S\], so confirm which the login screen shows. The script assumes the evaluation workspace, the changes in R1 to R12, and a seeded invoice for each case (section 7.3).

**The one sentence to memorise:** "Before a company pays a supplier's bill, it asks five questions: did we order this, did it arrive, was it any good, is the tax right, and have we already paid it? This tool asks them automatically and hands a person the answer."

| Time | Screen | Say (plain words) | Point at |
| --- | --- | --- | --- |
| 0:00 | Today | "Companies get thousands of supplier bills. Paying them wrongly costs real money: paying twice, paying a higher price than agreed, paying for goods that never arrived, getting tax wrong. This helps an accounts payable team catch that before approving. It supports the decision. It doesn't pay anyone." | The "does and does not do" panel, briefly |
| 0:40 | Invoices list | "Everything that arrives lands here, with a plain status. I'll open one that's ready." | Status chips and the legend |
| 1:10 | Case A, invoice, top | "The system has already done the checking. This banner is its summary." | Case story strip |
| 1:30 | What we read tab | "Step one: an AI model read the PDF and pulled these fields out. The AI only reads. It can't approve anything, and the original document is right here to check." | Provenance chip "Read by AI", PDF pane |
| 1:55 | Does it match? | "This is the heart of it. The supplier says we owe this amount. Our own records say we ordered it, it arrived, and it passed inspection. All four agree, so it's safe to consider." | Three-way card, four boxes |
| 2:20 | Checks | "Seven rules, written as code, no AI, so the answer is the same every time. They answer three questions: is it a legitimate new bill, does it match our records, is the tax right." | The three groups |
| 2:50 | Approve | "I approve. Notice what the screen says: this records that AP reviewed it. Nothing is paid or posted." | Consequence panel text |
| 3:20 | Case B, price variance | "Different story. The supplier billed more than the order allows. The story strip says exactly where." | Failing check, why-line |
| 3:50 | Action panel | "I have options. I choose 'Ask supplier to correct'. The system records that. It does not email the supplier. A person does that, and the reason I type is saved." | "What it does not do" line |
| 4:40 | Case C (optional, 30 s) | "If the goods haven't arrived yet, we hold. Paying before delivery is how companies lose money." | Check 3 or 4, Hold |
| 5:10 | Case D, duplicate or receipt | "The same bill twice is caught by the file's digital fingerprint, or by supplier plus invoice number plus year. A payment receipt isn't a bill at all, so it's set aside." | Check 7, or Set aside |
| 6:00 | Case E, high value, as AP Lead | "This one is above ₹5,00,000. One person can't approve it alone." Approve once. | "Waiting for second approval" status |
| 6:40 | Case E, as the second approver | Switch user. "A different person must sign. The same person can't approve twice." Approve. | Names of first and second approver |
| 7:30 | Auditor | "The auditor can look but not touch. Every action has who, when and why." | History tab, read-only buttons gone |
| 8:15 | Boundaries panel | "What it deliberately doesn't do: pay, post to the accounting system, email suppliers. What I'd build next is connecting live purchase-order data and automating the processing step." Say only what is true of your plans. | Does and does not do panel |

**Rehearsal rules.** Do not demonstrate a live upload unless R10 and the ingestion decision are settled. Do not attempt a self-approval live unless you have rehearsed the exact error message. Never read the confidence number aloud.

### Audience variants

| Audience | Emphasise | Trim |
| --- | --- | --- |
| HR or recruiter | The problem, the human-in-the-loop design, what you personally built and decided | Cases C and D; gate detail |
| Potential customer | Cases B and E, the boundaries panel, honest data-connection status | Architecture |
| Business stakeholder | Control (dual approval, audit trail) and what stays out of scope | Extraction detail |
| Technical interviewer | The AI/rules/human split, deterministic gates, seeded vs computed data (say it before they find it), how you evaluated | Plain-language analogies |

### Likely questions and truthful answers

| Question | Answer that stays inside the evidence |
| --- | --- |
| Does it connect to SAP? | "Not in this build. The evaluation workspace uses seeded purchase-order, receipt and inspection records. Matching logic is real; the live connection is future work." \[S F-10\] |
| Can I upload my own invoice? | Confirm the real behaviour first. If B-01 is unwired: "Upload stores and fingerprints the file. The extraction and matching engine currently runs against the evaluation set." \[S F-01\] |
| What if the AI misreads a number? | "Checks compare the extracted values against records, and the reviewer sees the original PDF beside the fields. A person decides." \[V PDF pane\] |
| How accurate is it? | Cite the 40-document evaluation only after reading its report. Do not cite displayed confidence \[S F-02\] |
| Why not let the AI do the matching? | "For money decisions I want the same input to give the same answer, with a reason a person can read. The AI reads messy documents; fixed rules decide." \[README\] |
| What stops one person approving a big invoice? | "Above ₹5,00,000 two different people must approve, and the system blocks the same person approving twice." Confirm the second approver's role requirement before saying "Controller" \[S\] |
| Does it pay the supplier? | "No. Approval records that AP's review is complete." \[V\] |
| What did you build versus use? | Prepare your own split. The README lists AWS-hosted models as the AI component, and the engine, checks, approval flow, audit log and interface as the built system \[README\] |

## 9. Prioritized implementation roadmap

### 9.1 Recommendation register

Grouped as the brief requires: essential for first-time comprehension, daily AP operations, demonstrations, cosmetic polish. Complexity is relative to the existing frontend. P0 means a first-time user or a demo audience gets a wrong or empty picture without it.

#### A. Essential for first-time comprehension

**R1. Truth pass on copy and policy constants** (P0, Low to Medium)

- *Problem:* UI text contradicts the rules and the product's real boundaries (C1 to C10).
- *Evidence:* InvoiceDetailPage.tsx tour steps 3 and 5; verdict banner title; Matching tab footnote; gate label strings \[V\].
- *User impact:* A newcomer learns a wrong threshold or believes payment or SAP happened.
- *Recommendation:* Fix each string; move thresholds into one config source read by UI and engine; reconcile README and KNOWN\_LIMITATIONS with the code.
- *Example:* Banner title "Approved by AP. Payment not made." Tour step 5 reads the dual-approval amount from the policy source.
- *Implementation:* InvoiceDetailPage.tsx; new content/concepts.ts and a read-only policy endpoint in backend/api/v1; README.md; docs/KNOWN\_LIMITATIONS.md.
- *Priority / Complexity:* P0 / Low-Medium.
- *Acceptance:* A test renders every tour step, banner and gate label and asserts every number equals the policy source; a forbidden-phrase scan ("payment run", "S/4HANA" outside the ERP settings screen, "OCR") passes.

**R2. Remove builder-governance language from the UI** (P0, Low)

- *Problem:* "D-04 Deferred", "Tier 2 gate overrides", "production truth rules", "Binding Production Engineering Specification", "tenant partition" \[V, S\].
- *User impact:* Incomprehensible to a newcomer; signals unfinished work to an audience.
- *Recommendation:* Replace with plain statements; keep behaviour. Example: badge "Approval blocked until the failed checks are resolved"; error "Approval isn't available while a check is failing. Choose Hold, Ask supplier to correct, Escalate, Reject or Set aside."
- *Implementation:* InvoiceDetailPage.tsx banner, error text, loading and not-found states; InboxPage.tsx subtitle and empty state; footer in App.tsx \[S\].
- *Priority / Complexity:* P0 / Low.
- *Acceptance:* No visible string matches D-\\d\\d, "Tier \\d", "production truth" or "tenant partition"; Playwright text scan passes on every page.

**R3. Three-way match card** (P0, Medium)

- *Problem:* Matching tab has no PO, GRN or QC side \[V\]; the product's core relationship is invisible.
- *User impact:* The newcomer cannot see what was ordered, received or inspected, so cannot answer "why did this fail?"
- *Recommendation:* Section 6.2 card, built at gate level first (notes, evidence reference), line-level after B-05.
- *Example:* "Billed 100 units. Goods receipt shows 90 received. Check 3 failed."
- *Implementation:* New ThreeWayMatchCard.tsx used by the Matching tab; backend/api/v1/invoices.py to return PO, GRN and QC summaries (B-05 for lines) \[S\].
- *Priority / Complexity:* P0 / Medium (High for line-level).
- *Acceptance:* On each of cases A to D a tester sees invoice, PO, receipt and inspection values (or "no record on file") without leaving the tab; no comparison is drawn from missing data.

**R4. Consequence-aware action panel** (P0, Medium)

- *Problem:* Actions show a reason box but not what they do or do not do \[V templates only\].
- *User impact:* Newcomers assume Ask-supplier emails the supplier, or that Approve pays.
- *Recommendation:* Section 6.4 table as UI, with the pre-click sentence and the approval confirmation. Copy for \[?\] items stays conditional until verified.
- *Implementation:* New ActionConsequencePanel.tsx; copy in concepts.ts; action panel inside InvoiceDetailPage.tsx; backend action validation in invoices.py (reject unknown action strings) \[S F-04\].
- *Priority / Complexity:* P0 / Medium.
- *Acceptance:* In a 5-person test, 90% or more correctly predict the outcome of each of the seven actions after reading the panel; no copy promises unverified behaviour.

**R5. Gate cards that teach, grouped, with defined states** (P0, Low to Medium)

- *Problem:* Seven flat cards; no reason for existing; undefined third state; "Check" vs "Policy Gate" \[V\].
- *Recommendation:* Sections 5.2 and 6.3: three groups, why-line, failure meaning, state legend, fatal vs fixable labelling.
- *Example:* Group heading "Does it match what we ordered and received?" with fatal/fixable note.
- *Implementation:* Gates tab in InvoiceDetailPage.tsx, extracted to GateGroup.tsx; copy from concepts.ts.
- *Priority / Complexity:* P0 / Low-Medium.
- *Acceptance:* Every state a card can render has a legend entry; a tester can say what each of the seven protects against; the amber branch is defined or deleted.

**R6. First-use terms and glossary** (P1, Low)

- *Problem:* PO, GRN, QC, GSTIN, IGST, MSME, HITL appear unexplained (section 4).
- *Recommendation:* Term component with definition and why-it-matters, first occurrence per screen only; content from concepts.ts.
- *Implementation:* New Term.tsx and a glossary route; used in banner, gates, tour, inbox headers.
- *Priority / Complexity:* P1 / Low.
- *Acceptance:* No acronym from section 4 appears on a screen without an expansion or popover on first use; popover text matches the glossary byte for byte.

**R7. Case story strip and AI/rules/human provenance chips** (P1, Low)

- *Problem:* Newcomers cannot tell what the system did, or where AI stops \[V\].
- *Recommendation:* Section 6.1 strip; section 5.3 chips on each tab. Never show confidence as measured accuracy.
- *Example:* "Read the PDF (AI), then ran 7 rule-based checks. 6 passed."
- *Implementation:* New CaseStory.tsx; chips in tab headers; remove the "Mantle Bedrock OCR" label.
- *Priority / Complexity:* P1 / Low.
- *Acceptance:* In a 5-second test a newcomer states what happened and what is needed; every tab names its actor (AI, rules or person).

#### B. Daily AP operations

**R8. One status vocabulary, legend and honest inbox** (P1, Medium)

- *Problem:* Raw enum filters omit real values; merged stage and decision render as an unknown badge; MSME dates always red; errors swallowed \[V InboxPage; S for seeded values\].
- *Recommendation:* Adopt spec section 3.3 statusFor(); filters by working state; urgency-graded due dates; visible errors; legend popover.
- *Implementation:* StatusBadge.tsx, InboxPage.tsx; backend /inbox status\_group filter (B-09) \[S\].
- *Priority / Complexity:* P1 / Medium.
- *Acceptance:* Every stage and decision value in the data maps to a named status; no unknown purple badge; a forced API failure shows an on-page error with Retry.

**R9. Distinct hold, supplier-correction and escalation statuses plus "what happens next"** (P1, Medium, needs backend)

- *Problem:* Hold, correction, escalation and awaiting-second-approval all become ACTION\_REQUIRED \[S F-07\].
- *Recommendation:* Persist the specific outcome (B-03); show "Waiting for supplier" or "On hold: awaiting receipt" and who owns the next step.
- *Implementation:* backend/api/v1/invoices.py and the status enum; statusFor(); status chip.
- *Priority / Complexity:* P1 / Medium.
- *Acceptance:* After each action the status names that action and owner within 1 second of reload.

**R16. Connections explain themselves** (P1, Low)

- *Problem:* ERP "CONNECTED" means configuration, not synced data; Gmail card reads server status; import is manual \[S F-08, F-10\].
- *Recommendation:* Section 5.7 copy; "Configured" wording; tenant-level Gmail status.
- *Implementation:* ConnectionsPage.tsx, backend /integrations/gmail/status.
- *Priority / Complexity:* P1 / Low.
- *Acceptance:* Each card states its job and consequence of absence; ERP never reads "Connected" when no records have synced.

#### C. Product demonstrations

**R10. Truthful pipeline state and a settled ingestion story** (P0 for demo, Medium to High)

- *Problem:* Upload and Gmail import create Received records that nothing processes \[S F-01\]; seeded decisions are labelled, not computed, and confidences are constants \[S F-02\].
- *User impact:* An audience that uploads a PDF sees an empty record and loses trust.
- *Recommendation:* Decide before recording: wire the ingestion job to the engine (B-01), or show "Received, waiting for extraction" and label seeded data as an evaluation set. Either way, hide or caveat the confidence column.
- *Example:* "Received. Extraction hasn't run on this server, so there are no fields or checks yet."
- *Implementation:* Option 1: backend job consumer calling engine/; Option 2: statusFor() "Received", empty-state copy on the invoice page, demo banner.
- *Priority / Complexity:* P0 / Medium (copy) or High (wiring).
- *Acceptance:* An uploaded PDF never shows an empty page without an explanation; the narrator's answer to "can I upload?" matches observed behaviour.

**R11. Scenario-aware guided case study** (P1, Medium)

- *Problem:* The tour describes layout and runs on whatever invoice is open \[V\].
- *Recommendation:* Rewrite as the five-case arc (section 7.2): each case opens its seeded invoice and highlights what it teaches; every step reads from concepts.ts.
- *Implementation:* Replace tourSteps in InvoiceDetailPage.tsx with tour/scenarioTour.ts and DemoGuide.tsx; confirm seed coverage in engine/sme\_eval\_setup.py.
- *Priority / Complexity:* P1 / Medium.
- *Acceptance:* A non-expert completes the guide in 10 minutes or less and can state each case's concept and boundary; every case resolves to a real seeded invoice.

**R12. Boundaries panel and evaluation-workspace banner** (P1, Low)

- *Problem:* Nothing in the product states what it does not do beyond one banner sentence \[V\].
- *Recommendation:* Section 7.1 left column as a panel; persistent "Evaluation workspace: synthetic data" banner.
- *Implementation:* New Boundaries.tsx; app shell banner when org is the evaluation tenant.
- *Priority / Complexity:* P1 / Low.
- *Acceptance:* Panel reachable in two clicks from any screen; no demo-path screen contradicts it.

#### D. Polish

**R13. Workflow-order tabs and keyboard remap** (P2, Low)

- *Problem:* Tabs are ordered for the engine, not the reader \[V\].
- *Recommendation:* Section 5.1 order; remap keys 1 to 4; update shortcut help.
- *Implementation:* TabType and handleKeyDown in InvoiceDetailPage.tsx.
- *Priority / Complexity:* P2 / Low.
- *Acceptance:* Tabs read What we read, Does it match?, Checks, History; keys 1 to 4 follow that order.

**R14. Readable audit trail** (P2, Low to Medium)

- *Problem:* Raw user IDs, hidden before/after state \[S F-12\]; history tab body unread by me \[?\].
- *Recommendation:* Names, plain-language event labels, before to after status, "what this proves" sentence.
- *Implementation:* History tab, AuditPage.tsx; backend /audit already returns before and after \[S\].
- *Priority / Complexity:* P2 / Low-Medium.
- *Acceptance:* An auditor answers who, what changed, and why for one invoice without opening the database.

**R15. Tour discoverability** (P2, Low)

- *Problem:* Tour button hidden below sm; otherwise only ?tour=true \[V\].
- *Recommendation:* Visible "How this works" button at all widths; offer once on first visit to an invoice.
- *Implementation:* Header block in InvoiceDetailPage.tsx; localStorage flag.
- *Priority / Complexity:* P2 / Low.
- *Acceptance:* Entry visible at 375 px and 1440 px; offered once per user.

### 9.2 Phases

Durations are rough planning estimates, not measurements. Phase 0 comes first because the demo script and every piece of UI copy depend on facts I could not verify.

| Phase | Goal | Contents | Rough size |
| --- | --- | --- | --- |
| 0. Settle the facts | A signed-off claims envelope | Work through the verify-first list in 11.5. Decide the ingestion story (wire B-01, or label the evaluation set). Confirm seed coverage for cases A to E. Confirm the reject action's real behaviour | 1 to 2 days, no UI |
| 1. Truth and plain language | Nothing on screen is wrong or jargon | R1, R2, R5, R7, R13, R15 | 2 to 3 days, frontend |
| 2. Teach at the decision | A newcomer understands what they are choosing | R3 (gate level), R4, R6, R8, R16; policy endpoint; backend action validation | 4 to 6 days, frontend plus small backend |
| 3. Demonstrable | A non-expert can present it | R10, R11, R12; seed additions for missing cases; two full rehearsals | 4 to 6 days |
| 4. Operations and polish | Daily-use depth | R9 (needs B-03), R14, line-level R3 (needs B-05) | Backend-dependent |

**Sequencing rule:** never ship R4 or R11 copy for an action whose behaviour is still \[?\]. A narrator who repeats a wrong consequence line is worse off than one with no line.

## 10. Files and components likely to change

| File | Change | Verified? |
| --- | --- | --- |
| frontend/src/pages/InvoiceDetailPage.tsx | Split the 1,255-line page into CaseStory, tab components, ThreeWayMatchCard, GateGroup, ActionConsequencePanel; replace in-file tourSteps; remove literal thresholds; reorder tabs; rewrite banner and error copy | \[V\] read about 80% |
| frontend/src/pages/InboxPage.tsx | Status vocabulary, filters by working state, visible errors, header and empty-state copy, due-date urgency | \[V\] |
| frontend/src/components/StatusBadge.tsx | Replace with statusFor()-driven chip plus legend | Imported \[V\]; not read |
| frontend/src/content/concepts.ts, scenarioGuide.ts | New single source for definitions, consequences, thresholds, demo talk track | New |
| frontend/src/components/Term.tsx, ThreeWayMatchCard.tsx, GateGroup.tsx, ActionConsequencePanel.tsx, CaseStory.tsx, Boundaries.tsx, DemoGuide.tsx | New components | New |
| frontend/src/tour/scenarioTour.ts | New scenario-aware tour | New |
| DashboardPage.tsx, ConnectionsPage.tsx, AuditPage.tsx, Navigation.tsx, App.tsx | Copy corrections, "Configured" wording, audit readability, footer string | Names from spec \[S\]; not read |
| backend/api/v1/invoices.py | Validate action strings; return PO, GRN and QC summaries; persist distinct outcomes (B-03) | File named in the rules doc \[V\]; not read |
| backend (new) policy endpoint | Read-only thresholds from settings | New |
| engine/sme\_eval\_setup.py | Cover cases A to E with seeded invoices; label confidence honestly | Named in README \[V\]; not read |
| README.md, docs/KNOWN\_LIMITATIONS.md, docs/AP\_BUSINESS\_RULES.md | Reconcile duplicate disposition, thresholds, shortcut and template claims, Pane 2 description | \[V\] |

## 11. Acceptance criteria and testing strategy

Per-recommendation criteria are in 9.1. These are the product-level tests.

### 11.1 Comprehension test (the real measure)

Five people who have never worked in AP. First ten minutes unguided in the evaluation workspace, then four tasks:

1. Explain in your own words what this product does.
2. Open the price-variance invoice; say why it is blocked and what the options are.
3. For each of the seven actions, predict what happens (paper quiz).
4. Define PO, goods receipt and inspection certificate.

**Pass:** at least four of five state the three-way idea correctly; at least 90% of action predictions correct; none believes Approve pays or that Ask-supplier emails the supplier. Re-run after Phase 2 and again after Phase 3.

### 11.2 Demo-readiness test

A non-expert delivers section 8 in nine to ten minutes using only the demo guide panel. An observer logs any statement from the "must not say" column. Target: zero slips across two runs.

### 11.3 Automated checks

- **Claims and jargon lint:** forbidden phrases ("payment run", "S/4HANA" outside the ERP settings screen, "OCR", "cryptographic" unless justified) and regexes for D-\\d\\d, "Tier \\d", "production truth".
- **Constant consistency:** a test that renders tour, banners and gate text and asserts every threshold equals the policy endpoint.
- **Status coverage:** statusFor() unit-tested over every stage and decision value in the data, plus the unknown fallback.
- **State legend coverage:** every gate and invoice state renders a legend entry.
- **Scenario flows:** Playwright (already used by the repo \[V README\]) walking cases A to E and the Auditor view end to end.
- **Accessibility:** Term popovers, consequence panel and tour operable by keyboard with visible focus.

### 11.4 Regression guards

The existing suite (244 passing, 12 skipped \[V README\]) still passes; Auditor mutations still return 403; approval stays blocked while any check fails; anti-self-approval still returns an error; no screen gains a path to payment or ERP posting.

### 11.5 Verify first (things I could not confirm)

1. Does anything consume the QUEUED ingestion job and call the engine? (spec F-01)
2. What does the backend do with REJECT\_INVOICE, and what state results? (C7)
3. What do RAISE\_DEBIT\_NOTE and ESCALATE produce: a document, a notification, or only a recorded reason?
4. Does the server require the CONTROLLER role for the second approval, or only a different user?
5. What is the dual-approval threshold at runtime, and where does the ₹1,00,000 in the tour come from?
6. What values can match\_gates.status take? Is there a real third state behind the amber branch?
7. Which seeded scenarios exist beyond the clean match and the payment receipt?
8. What do the action panel and History tab render (the last \~250 lines of InvoiceDetailPage.tsx)?
9. Is there any hash chain behind "cryptographic audit trail"?
10. Which frontend build did the spec audit, and which is the branch you will record from?
11. What do the 40-document evaluation report and the Phase E report actually say?

## 12. Existing features that should NOT be changed

These are working design decisions and, for several, the product's most credible selling points.

- **Verdict-first banner** with colour and a one-line state. Add to it; do not replace it.
- **Failed checks sorted first**, with a required next action per failure.
- **Plain-language gate names** (humanGateName). Extend with why-lines; keep the idea.
- **Reason templates** per action, and the mandatory reason before submit.
- **Approval blocked while any check fails**, with an explanation (change the words, not the behaviour).
- **Dual control above the threshold with anti-self-approval.**
- **Auditor read-only** (server-enforced 403) and hiding actions for that role.
- **Append-only audit log** and the SHA-256 document fingerprint with copy control.
- **The AI-reads, rules-decide, human-approves split.** It is the pitch; make it visible, never blur it.
- **Strict decoupling from payment and ERP posting.** Say it louder; never soften it.
- **Honest empty and unavailable states** ("unavailable rather than zero"). Keep the principle; fix the one footnote that promises a comparison the tab does not show.
- **Keyboard shortcuts** and en-IN currency with tabular numerals (only the tab-key mapping changes, per R13).
- **The tour's mechanism** of switching tabs per step. Keep the mechanism; replace its content (R11).
- **Evaluation workspace seeding and the synthetic data approach.** Label it; do not hide it.
