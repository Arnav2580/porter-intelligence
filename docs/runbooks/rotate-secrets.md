# Runbook - Rotate Secrets

[Runbooks](./README.md) | [Security Notes](../security/runtime-and-secrets.md)

Objective:
- rotate runtime secrets without leaving the platform in a partially configured state

## Secrets In Scope

- `JWT_SECRET_KEY`
- `WEBHOOK_SECRET`
- `ENCRYPTION_KEY`
- auth seed passwords if those seed accounts are still enabled

## Rotation Sequence

1. Generate replacement secrets.
2. Update secrets in the target secret manager or environment store.
3. Restart backend services in a controlled order.
4. Verify `/health`.
5. Test:
   - auth token issuance
   - webhook signature validation
   - read/write path for encrypted case data

## Warning

- rotating `ENCRYPTION_KEY` requires a migration or re-encryption plan if encrypted historical values must remain readable
- do not rotate encryption blindly in a production-like environment

## Post-Rotation Verification

```bash
curl http://localhost:8000/health
```

And confirm:
- auth login still works
- case retrieval still decrypts stored trip and driver IDs
