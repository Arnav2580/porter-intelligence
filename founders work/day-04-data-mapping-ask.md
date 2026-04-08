# Day 04 - Data Mapping Ask

[Index](./README.md) | [Prev](./day-03-digital-twin-story.md) | [Next](./day-05-shadow-mode-story.md)

Objective:
- make the integration ask feel small, safe, and immediate
- move the conversation from theory to proof in one step

---

## 1. The Ask

Use this exact line:

"Give us 20 masked trip events and we will map them into the platform live, right now."

Why this works:
- the ask is tiny (20 records, not a database export)
- it requires no production access, no API credentials, no security review
- it creates a real-time proof moment in the meeting
- it shifts the dynamic from "evaluating a pitch" to "testing a system"
- it puts Shruti's team in a position to validate, not just listen

---

## 2. Sample Data Request Template

### Email/Message Version

Subject: Porter Intelligence Platform - Masked Sample Data Request

"We do not need live credentials or production access to demonstrate data compatibility.

Could your team share 20 masked trip-completion events in CSV or JSON format? These should include stable field names from your trip events pipeline.

We will map them into the platform live during our session and show the complete path: ingestion, schema mapping, fraud scoring, case creation, and analyst queue output.

The data should be masked (hashed driver IDs, anonymized coordinates, randomized trip IDs). We do not need or want PII. The purpose is to demonstrate field-level mapping compatibility, not to access real identities."

### Verbal Version (For The Meeting)

"Before we move to shadow mode, I want to show you something practical. If your team can share 20 masked trip events - just completion records with stable field names, no PII needed - I can map them into the platform right now and show you the full path from raw event to scored case. It takes about 90 seconds."

---

## 3. Field List To Request

### Required Fields (Minimum Viable Mapping)

| Field | Purpose | Example |
|---|---|---|
| trip_id | unique identifier | "TRP-2026-04-08-XXXXX" |
| driver_id | driver identifier (masked) | "DRV-HASH-A1B2C3" |
| pickup_time or completion_time | temporal context | "2026-04-08T09:30:00" |
| pickup_zone or pickup_lat/lng | geographic origin | "Koramangala" or 12.9352, 77.6245 |
| dropoff_zone or dropoff_lat/lng | geographic destination | "Whitefield" or 12.9698, 77.7500 |
| fare | trip fare amount (Rs) | 450.00 |
| distance_km | trip distance | 12.3 |
| duration_minutes | trip duration | 38 |
| payment_mode | cash, online, wallet | "cash" |
| vehicle_category | mini truck, two-wheeler, tempo | "mini_truck" |
| trip_status | completed, cancelled, disputed | "completed" |

### Nice-To-Have Fields (Richer Scoring)

| Field | Purpose |
|---|---|
| cancellation_flag | whether driver or customer cancelled |
| dispute_indicator | whether trip was disputed |
| customer_rating | post-trip customer rating |
| surge_multiplier | dynamic pricing factor |
| driver_acceptance_time | time between dispatch and driver acceptance |
| estimated_fare | platform-estimated fare before trip |
| actual_route_distance | GPS-measured actual distance |

### Porter-Specific Fields We Expect

Based on Porter's public API documentation and enterprise integration features:
- Porter already offers API integrations with webhook updates and live tracking
- Porter provides digital proof of delivery
- Porter supports real-time tracking across multiple deliveries

This means their trip events likely include:
- webhook event types (trip_created, trip_started, trip_completed, trip_cancelled)
- driver location pings during transit
- proof-of-delivery metadata
- estimated vs actual fare comparison

The schema mapper can handle any of these field structures. The demo shows this.

---

## 4. Demo Script For Live Mapping

### Step-By-Step (90 Seconds)

Step 1 (15 seconds):
- Show the sample file on screen
- "Here are 20 masked trip events. These are the kind of records Porter's trip pipeline would emit."

Step 2 (15 seconds):
- Show the schema mapping layer (`GET /ingest/schema-map/default`)
- "This is the field mapping. It translates your field names to our internal schema. If your fields are named differently, we adjust the mapping, not the code."

Step 3 (20 seconds):
- Upload the sample via `POST /ingest/batch-csv`
- "Uploading now. These records enter the ingestion pipeline, get mapped, and go into the scoring queue."

Step 4 (15 seconds):
- Show the queue status (`GET /ingest/queue-status`)
- "All 20 records accepted. Zero failed. The schema mapper handled the field translation."

Step 5 (25 seconds):
- Show the resulting flagged cases in the analyst queue
- Show the fraud heatmap updating with new zone data
- "Out of 20 trips, the model flagged 3 as action-tier and 5 as watchlist. Here they are in the analyst queue with evidence, signals, and recommended actions."

### Closing Line After Demo

"That is the complete path from raw trip event to analyst-reviewable case. The same path works with your actual masked data. The question is whether you want to see it on your feed next."

---

## 5. Objection Handling

### "We cannot share data before security approval."

"Completely understood. We are not asking for production access or API credentials. We are asking for 20 masked records with hashed IDs and anonymized coordinates. No PII, no production coupling. This is a compatibility demonstration, not a data integration. If even that requires approval, we can run the demo entirely on our synthetic data and do the real mapping during the shadow-mode phase."

### "Our field names are different."

"That is expected and normal. The schema mapper exists precisely for this reason. If your trip ID field is called `booking_ref` instead of `trip_id`, we change one line in the mapping config, not the codebase. I can show you this live: give me your field name and I will remap it in real time."

### "Our data format is different (not CSV/JSON)."

"The ingestion layer supports CSV, JSON, and webhook payloads. If your pipeline emits Protobuf, Avro, or a custom format, the adapter layer can be extended during the deployment phase. For this demo, CSV or JSON is sufficient."

### "Why only 20 records?"

"Because 20 records is enough to prove field-level compatibility, the mapping path, and the scoring pipeline. It is not enough to validate model accuracy - that is what shadow mode is for. The 20-record demo is about trust in the integration path, not trust in the model. We separate those concerns deliberately."

### "What if the mapping does not work?"

"Then you will see it fail in real time, and we will debug it together on screen. That is more honest than a slide that says 'integration is easy.' Either the mapper handles your fields or it does not. If it does not, we fix it live or we document it as a deployment task."

---

## 6. What This Demo Accomplishes Strategically

For Shruti (CPTO):
- proves the integration is a mapping exercise, not a re-architecture
- shows that the API contract is clean and the pipeline is real

For Uttam (CEO):
- moves from "interesting pitch" to "this actually connected to something real"
- creates forward momentum toward shadow-mode commitment

For the fraud/risk head:
- shows that trip events become analyst-reviewable cases in under 2 minutes
- makes the workflow feel tangible, not theoretical

---

## 7. Day 04 Founder Output

By the end of Day 04, you should have:
- one sample-data request template (email and verbal versions)
- one 90-second demo script for live mapping
- one answer for every likely data-sharing objection
- confidence that the "20 masked events" ask is small enough to say yes to in the room
