# Porter Intelligence Documentation

This file is retained for compatibility with older links.

The current technical documentation has moved to [documentation.md](documentation.md). Use that file and [README.md](README.md) as the source of truth for the present codebase.

Why this redirect exists:

- Older versions of this file described a 31-feature model. The current model uses 44 features.
- Older versions described fixed Vercel/ngrok proxy rewrites. Hardcoded tunnel URLs have been removed.
- Older versions mentioned stale env vars such as `SECRET_KEY` and `ALLOWED_ORIGINS`. The current env vars are `JWT_SECRET_KEY` and `API_ALLOWED_ORIGINS`.
- Older versions referenced stale tier thresholds. The current thresholds are `action >= 0.80`, `watchlist >= 0.50`, and `clear < 0.50`.

Read the maintained documentation here: [documentation.md](documentation.md).
