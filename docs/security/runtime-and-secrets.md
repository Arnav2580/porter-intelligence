# Security And Runtime Notes

[Docs Hub](../README.md) | [Secrets Rotation Runbook](../runbooks/rotate-secrets.md)

Purpose:
- summarize the buyer-visible security and runtime posture of the platform

## Runtime Modes

- `prod`
  - intended for production-like behavior
  - synthetic feed disabled
  - security validation enforced
- `demo`
  - controlled demonstration mode
  - synthetic behavior only when explicitly enabled
- `shadow`
  - read-only operating validation mode
  - enforcement disabled

## Core Controls

- JWT-based auth
- role-based access control
- AES-256-GCM for PII encryption when configured
- rate limiting on auth, scoring, and ingestion endpoints
- audit logs for case and driver actions
- webhook signature verification support

## Current Secret Inputs

- `JWT_SECRET_KEY`
- `WEBHOOK_SECRET`
- `ENCRYPTION_KEY`
- seed user passwords through env vars

## Buyer-Safe Security Notes

- runtime secrets should come from a managed secret store in deployed environments
- wildcard CORS is not used in deployable environments
- demo-mode relaxations are explicit and mode-bound
- shadow mode exists specifically to prevent premature operational writeback
