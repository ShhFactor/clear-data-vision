# Contributing to Place Data Service

Thanks for your interest. This document explains how to get set up, the
conventions the codebase follows, and what to include in a pull request.

## Quick setup

```bash
git clone https://github.com/id-fant/place-data-service.git
cd place-data-service

make install   # creates venv and installs deps
make seed      # populates places.db from data/*.json
make test      # runs the full pytest suite
make run       # starts the dev server on :8000
```

Without `make`:

```bash
python -m venv venv
source venv/bin/activate          # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m src.seed
pytest
uvicorn src.main:app --reload
```

## Project layout

```
src/         Application code, one concern per module
  geo.py        Haversine + bounding-box helpers
  dedup.py      Two-stage deduplication (distance → fuzzy name)
  reconcile.py  Multi-source canonicalisation + conflict logging
  staleness.py  Category-aware freshness scoring
  database.py   SQLite schema and queries
  models.py     Pydantic request/response schemas
  main.py       FastAPI app and routes
  seed.py      Loads data/*.json into the DB
tests/       Mirrors src/, one test file per module
data/        JSON seed files
scripts/     Standalone utilities (e.g. try_api.py)
```

## Conventions

### Code

- **Type hints are required** on function signatures. Use `dict`/`list`
  built-ins (not `Dict`/`List`) — minimum Python is 3.11.
- **One public concept per module.** New algorithms get their own file
  with focused tests in `tests/test_<module>.py`.
- **Comments explain *why*, not *what*.** Skip them if the code is
  self-evident. Don't reference issue numbers or "added for X" — that
  belongs in PR descriptions and rots in source.
- **No external network calls in `src/`.** If you wire up a real source
  ingestion path, it goes behind an interface that can be faked in tests.

### Tests

- Every test file uses the `isolated_db` fixture from `tests/conftest.py`
  automatically — your test gets a fresh empty SQLite database.
- Use the `seed_minimal` fixture when you need realistic content.
- Aim for tests that exercise behaviour through the public surface (API
  or top-level functions) rather than internal helpers.

### Commits

- Imperative, present tense subject line, ≤ 72 chars:
  - `Add staleness threshold for bookstores`
  - `Fix N+1 query in /places/stale`
- Body explains the *why* in 1–3 short paragraphs. Reference issues with
  `Fixes #123`.
- Small, focused commits are easier to review than one mega-commit.

## Pull request checklist

- [ ] `pytest` is green
- [ ] New behaviour has a test
- [ ] README is updated if the public API or run instructions change
- [ ] No secrets, credentials, or binary blobs committed
- [ ] Breaking changes called out in the PR summary

CI runs the full suite on Python 3.11, 3.12, and 3.13 against every PR.
A green CI badge is required before merge.

## Design principles

These are the patterns the codebase commits to. Proposals that fight
them aren't blocked, but they need a justification.

1. **Confidence on every response.** Consumers (AI agents) get to decide
   whether to trust the data. Silent "best guess" is not acceptable.
2. **Log every conflict.** Source disagreements are signal, not noise.
   They go in `conflicts` so downstream code can surface them.
3. **Graceful degradation.** Every external dependency has a fallback
   path that still returns a usable (if lower-confidence) response.
4. **Validation at the boundary.** Pydantic enforces input constraints
   at the edge. Internal code trusts validated objects.
5. **No premature abstractions.** Three similar lines beats a clever
   helper used once.

## Reporting bugs / requesting features

Use the issue templates under `.github/ISSUE_TEMPLATE/`. Bugs especially
benefit from a minimal reproducible request.

## Questions

Open a discussion or an issue — happy to help.
