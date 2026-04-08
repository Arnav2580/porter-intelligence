# Day 14 - Meeting Day Runbook

[Index](./README.md) | [Prev](./day-13-war-game.md)

Objective:
- run the meeting as a same-day decision process, not a feedback session
- leave with signature, commitment, or a named next step with a date

---

## 1. Pre-Meeting Checklist (Morning Of)

### Technical Readiness (1 Hour Before)

- [ ] Demo environment is running and accessible
- [ ] Login works for admin, analyst, and manager roles
- [ ] Digital twin is generating cases (queue is not empty)
- [ ] Heatmap is rendering correctly
- [ ] ROI calculator loads with Porter's numbers pre-filled
- [ ] Schema mapper endpoint returns default mapping
- [ ] Shadow status endpoint returns `shadow_mode: true`
- [ ] Board pack PDF downloads successfully
- [ ] Demo reset endpoint works (in case you need to restart mid-demo)
- [ ] Backup demo path tested: if live scoring fails, preloaded scenarios work

### Documents Readiness (Before Leaving For Meeting)

- [ ] 2 printed copies of NDA
- [ ] 2 printed copies of commercial schedule
- [ ] 2 printed copies of MSA
- [ ] Tranche 1 invoice (pre-filled with bank details, GST)
- [ ] Board pack (printed, 3 copies for circulation)
- [ ] Finance memo (printed, 2 copies)
- [ ] USB drive with all PDFs and editable DOCX versions
- [ ] Business cards

### Personal Readiness

- [ ] Opening script rehearsed (say it out loud once more)
- [ ] Price statement rehearsed with silence (say it, count to 10)
- [ ] Each CXO's one-sentence priority memorized
- [ ] Top 3 objection responses rehearsed
- [ ] Water and notepad packed (you will need to take notes during objections)

---

## 2. Mental Framework

### You Are Not There To Ask

- "What do you think?"
- "Does this look interesting?"
- "Would you be open to exploring this?"

### You Are There To Ask

- "Is this sufficient to begin the commercial process today?"
- "Can we sign the schedule and start shadow-mode setup this week?"
- "If not today, who makes the decision and by when?"

### The Mindset

You are a vendor presenting a working product with a clear commercial structure. You are not a startup founder begging for validation. The product either solves Porter's problem or it does not. Your job is to demonstrate that clearly and ask for a decision.

---

## 3. Minute-By-Minute Meeting Script

### Minute 0-2: Arrival And Opening

Walk in, shake hands, settle. Then:

"Thank you for your time. I want to be respectful of it, so let me tell you exactly what this meeting is about and what I am going to ask for at the end.

We are not here to show a dashboard. We are here to show a leakage-control operating layer built for Porter's scale.

I will show you the detection engine, the integration path, the shadow-mode safety boundary, and the analyst workflow. At the end, I am going to ask whether we can sign a commercial schedule today and begin shadow-mode setup this week.

If at any point you want to skip ahead, dig deeper, or challenge something, please do."

### Minute 2-5: Digital Twin And Scale Story

Show the dashboard. Show the 22-city heatmap. Show the KPI surface.

"This is the platform running at Porter-like scale. 22 cities, realistic trip volumes, city-specific fraud patterns. The digital twin lets you see the operating model before any live integration."

If Uttam is watching closely:
"Uttam, this is the control center view. Queue pressure by city, fraud rate trends, and intervention speed — the things your ops team needs to see every morning."

### Minute 5-7: Ingestion And Data Mapping

Show the schema mapper. Show the sample file. Run the 20-record ingestion.

"This is the integration path. Your trip events come in through a webhook or batch upload. The schema mapper translates your field names to the internal format. No code changes required."

Show the 3 flagged cases in the queue.

"Out of 20 trips, 3 were flagged as action-tier. Here they are with evidence and signals."

### Minute 7-9: Shadow Mode

Show the shadow status endpoint. Show the `/health` response with `shadow_mode: true`.

"Shadow mode means everything you just saw happens in isolation. No writeback to your systems. No driver actions. No enforcement webhooks. Your team reviews the output and decides whether the signals are real. This is the validation phase."

### Minute 9-13: Analyst Workflow

Switch to the analyst workspace. Open a case. Show the evidence.

"This is what your fraud analyst's morning looks like. Open the queue, review the top case, check the signals, make a decision, record the action. Every decision is logged with timestamp, analyst ID, and reason."

Make a decision on the case. Show the audit trail.

"The model surfaces. The analyst decides. The audit trail records. Management has visibility."

### Minute 13-15: Manager Dashboard And ROI

Show the manager KPI view. Show the ROI calculator.

"And this is what leadership sees. Queue pressure, case age, city comparison, and the ROI calculator with Porter's own revenue numbers."

Walk through the realistic scenario:
"At Porter's Rs 4,306 crore revenue, even a 3% leakage rate is Rs 129 crore annually. The platform needs to recover Rs 3.25 crore to break even. That is 2.5% of the leakage. The realistic scenario shows a 6-week payback."

### Minute 15-16: Transition To Commercial

"Let me step back from the demo for a moment.

If this were only a model, it would not be worth buying. What makes this buyable is the full operating package: detection, ingestion, shadow-mode safety, analyst workflow, documentation, deployment, and handover.

The question is whether this solves a real enough problem at a fast enough speed to justify a same-day commercial decision."

### Minute 16-18: The Ask

"Here is what I am proposing.

Rs 3.25 crore. Structured as:
- Rs 1 crore on signing. You get source access, deployment package, and documentation.
- Rs 1 crore on shadow-mode validation success within 60 days.
- Rs 1.25 crore on live rollout and handover completion within 90 days.

Porter bears zero operational risk until shadow mode proves value. And you only pay the full amount after the platform has earned it on your data."

**Then stop talking. Count to 10. Say nothing.**

### Minute 18-28: Objection Handling

They will respond. Listen carefully. Do not interrupt.

Possible responses and your moves:

| Their Response | Your Move |
|---|---|
| "This is interesting, let us discuss internally" | "Who makes the final decision? Can we schedule that meeting before I leave today?" |
| "We need InfoSec review" | "Agreed. Can we sign the NDA and commercial schedule today with InfoSec review as a condition before Tranche 1 release?" |
| "Rs 3.25 crore is too much" | Hold. Then: "The milestone structure means you pay Rs 1 crore today and the rest only after validation. What specifically concerns you about the structure?" |
| "We want to build internally" | "You can. The question is time. 12-18 months vs. 90 days. Where should engineering time go while you scale to 50 cities?" |
| "Let us do a free pilot first" | "A milestone-gated structure is better. Rs 1 crore for deployment and shadow-mode setup. If it does not validate, you have source code and docs for Rs 1 crore. That is less than the cost of building from scratch." |
| "We need to talk to the board" | "Can I provide a board-ready packet today? The board pack is designed to circulate without me in the room." |
| Positive signal: nodding, discussing amongst themselves | Stay silent. Let them process. Only speak when directly addressed. |

### Minute 28-30: Close

If they are leaning yes:
"Shall we walk through the commercial schedule together right now? I have printed copies and we can finalize any term adjustments on the spot."

If they need more time:
"I understand. Can we agree on three things before I leave?
1. Who specifically will make the decision?
2. By what date?
3. What information do they need from me that they do not already have?"

If they are noncommittal:
"I appreciate your time. The board pack and finance memo will be in your inbox within an hour. Let me leave you with this: every month of delay is Rs 7-11 crore in uncontrolled leakage. Shadow mode can start within a week with zero operational risk. The question is not whether to act. It is when."

---

## 4. After The Meeting

### Within 2 Hours

- Send a follow-up email with:
  - one-paragraph summary of what was shown
  - attached: board pack PDF, finance memo, commercial schedule
  - the exact next step discussed in the meeting
  - your contact details

### Email Template

Subject: Porter Intelligence Platform - Follow-Up And Next Steps

"[Name],

Thank you for the meeting today. As discussed, the Porter Intelligence Platform is a leakage-control operating system designed to detect, route, and recover operational leakage at Porter's scale.

Attached:
- Board pack (executive summary, architecture, KPIs, ROI, rollout plan)
- Finance memo (leakage-to-savings translation, three-scenario ROI)
- Commercial schedule (asset description, payment structure, acceptance criteria)

Next step: [as agreed in the meeting — e.g., "InfoSec review completion by April 25, followed by commercial schedule sign-off."]

I am available for any follow-up questions or to present to additional stakeholders.

Best regards,
[Your name]"

### Within 48 Hours

- If no response, follow up with a single line: "Just checking if you need anything from me to move forward on the next step we discussed."
- Do not send multiple follow-ups. One is enough. After that, the ball is in their court.

---

## 5. Outcome Tree

| Outcome | What It Means | Your Next Action |
|---|---|---|
| Signed same-day | Best case. Begin shadow-mode deployment immediately. | Send Tranche 1 invoice. Schedule Day 1 kickoff. |
| Verbal commitment pending board approval | Strong signal. They want it but need governance. | Send board pack within 2 hours. Get the approver's name and date. |
| Commitment to paid shadow validation | They want proof before full commitment. | Accept if Tranche 1 (Rs 1 Cr) is paid. Deploy shadow mode within 1 week. |
| "Let us think about it" with named owner and date | Decent. Real but delayed. | Follow up on the named date. Do not chase before that. |
| "Let us think about it" with no specifics | Weak. They are politely declining. | Follow up once in 48 hours. If no response, move on. |
| Hard no | Rare if you got to Day 14. | Ask what specifically does not work. Use the answer to improve. |

---

## 6. Day 14 Founder Output

By the end of Day 14, success means one of:
- signed commercial agreement
- paid shadow-validation commitment (Rs 1 crore minimum)
- formal written next-step commitment with named decision-maker and decision date

Anything less is a lesson, not a failure. But the preparation in Days 1-13 is designed to make anything less unlikely.
