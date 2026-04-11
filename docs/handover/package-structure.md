# Handover Package Structure

[Handover Hub](./README.md)

Objective:
- define the exact structure of the transfer package for a buyer or internal platform team

## Package Sections

1. Source package
- application code
- dashboard code
- infrastructure code

2. Deployment package
- environment reference
- deployment guide
- infrastructure notes

3. Operations package
- runbooks
- health checks
- rollback and restore instructions

4. Model package
- model weights
- threshold configuration
- evaluation artifacts
- model card or equivalent explanation

5. Buyer review package
- security summary
- architecture docs
- KPI definition sheet
- board pack

6. Acceptance package
- rollout scope
- support scope
- acceptance checklist

## Minimum Transfer Rule

The package is not handover-ready unless a new technical owner can answer:
- how to start it
- how to verify it
- how to rotate secrets
- how to retrain it
- how to restore it
