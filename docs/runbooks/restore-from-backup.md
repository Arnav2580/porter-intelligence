# Runbook - Restore From Backup

[Runbooks](./README.md)

Objective:
- restore the platform after a database or environment failure

## Scope

This runbook covers:
- PostgreSQL restore
- Redis cache rebuild expectations
- API restart checks

## Restore Sequence

1. Restore PostgreSQL from the latest clean snapshot or dump.
2. Bring Redis back online.
3. Restart API services.
4. Rebuild volatile cache layers by allowing normal startup to warm them.
5. Verify:
   - `/health`
   - `/cases/`
   - `/kpi/live`

## Notes

- Redis is operationally useful but not the system of record.
- PostgreSQL is the critical recovery target for cases, audit logs, and reviewed outcomes.

## Post-Restore Checks

- can operators log in
- are cases visible
- are shadow-mode boundaries still correct if enabled
- do manager summaries match the restored database state
