# Runbook - Add A New City

[Runbooks](./README.md)

Objective:
- extend the platform to support a new operating city cleanly

## Steps

1. Add the city and zones in the generator or city profile source of truth.
2. Add demand and trip-distribution assumptions for that city.
3. Add dashboard labels for the new zones if needed.
4. Rebuild simulator or sample datasets that depend on the city list.
5. Verify:
   - scoring still runs
   - demand forecast still runs
   - manager and map views render correctly

## Files Usually Touched

- `generator/cities.py`
- `ingestion/city_profiles.py`
- dashboard components that display zone labels

## Verification

Run:

```bash
PYTHONPATH=$(pwd) ./venv/bin/pytest tests -q
cd dashboard-ui && npm run build
```
