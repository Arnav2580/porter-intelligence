# Fail-Safe Demo Runbook

[Docs Hub](../README.md) | [Runbooks](../runbooks/README.md)

Purpose:
- make the product demo resilient even if live mapping or runtime conditions change mid-meeting

## Primary Demo Path

1. Open the management dashboard.
2. Show runtime mode and data provenance.
3. Use the ROI planner to frame the business case.
4. Run the preset trip scenarios from the live trip scorer:
   - fraud ring walkthrough
   - cash extortion case
   - GPS spoofing style case
5. Switch to the analyst workspace.
6. Show queue, case detail, history, and driver action flow.
7. If needed, reset the demo workspace and rerun the scenario.

## Backup Demo Path

If live scoring or ingestion discussion becomes unstable:

1. Open `/reports/board-pack`.
2. Use the board pack as the leave-behind walkthrough.
3. Show `/demo/scenarios` to prove preset scenario coverage.
4. Show `/ingest/schema-map/default` and the masked CSV template.
5. Explain the shadow-mode onboarding path rather than forcing a live hookup.

## Fast Mapping Proof

Use these assets in order:

- `GET /ingest/schema-map/default`
- `POST /ingest/batch-csv`
- `data/samples/porter_sample_10_trips.csv`

Talk track:
- "Give us 20 masked events in this shape, or your own field names plus a mapping file, and we can normalize them into the scoring schema without changing the model logic."

## Demo Reset

Use:

- `POST /demo/reset`

Guardrails:

- only available to `admin` and `ops_manager`
- disabled in production runtime mode
- clears demo workspace tables only
- does not touch source benchmark data or model artifacts

## Honest Boundaries

- synthetic feed is for demonstration and rehearsal, not finance-proof savings
- reviewed-case metrics become the buyer-safe quality layer only after analysts resolve cases
- live mapping can be shown safely without turning on operational writeback because shadow mode remains available
