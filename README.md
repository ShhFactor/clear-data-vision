# Place Data Service

[![CI](https://github.com/id-fant/place-data-service/actions/workflows/ci.yml/badge.svg)](https://github.com/id-fant/place-data-service/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A FastAPI service that serves verified, fresh place data for AI agents — with
geographic search, deduplication, source reconciliation, and graceful
degradation when external sources fail.

## Example response

`POST /places/reconcile/place_009` on a place with 3 disagreeing sources:

```json
{
  "place_id": "place_009",
  "canonical": {
    "name": "UB City Mall",
    "phone": "+91-80-12345678",
    "hours": "11:00-23:00",
    "address": "Vittal Mallya Road, Bangalore"
  },
  "conflicts": [
    {"field_name": "phone", "source_a": "google_places", "value_a": "+91-80-12345678",
     "source_b": "yelp",    "value_b": "+91-80-87654321"},
    {"field_name": "hours", "source_a": "google_places", "value_a": "11:00-23:00",
     "source_b": "yelp",    "value_b": "10:00-22:00"}
  ],
  "confidence": "LOW",
  "needs_escalation": true
}
```

Canonical values picked by source priority (`google_places` > `yelp` > `scraper`).
Every disagreement is logged so consuming agents can hedge their answers.

## The Problem This Solves

AI agents querying real-world location data face three problems:

1. **Multiple sources disagree.** Google Places says one thing, Yelp says
   another, your scraper says a third.
2. **Data goes stale.** Restaurants close, hours change, addresses get
   misreported — and nobody marks the record as outdated.
3. **External APIs fail.** When Google Places is down, your agent can't
   just stop working.

This service provides a unified data layer that handles all three.

## Architecture

The service follows the same reliability pattern across every component:

**Primary system works independently. External data improves the experience
without becoming a hard dependency.**

Specifically:

- **Deduplication** uses geographic proximity (cheap) before name similarity
  (expensive) — keeps records separate when uncertain rather than guessing.
- **Source reconciliation** picks the highest-priority source as canonical
  while logging every conflict explicitly. Coordinates use the priority
  source's value, not an average — averaging pulls the canonical position
  toward the least-trusted source.
- **Staleness detection** uses category-specific thresholds plus signal
  factors (confidence, conflicts) rather than a single time cutoff.
- **All endpoints** return confidence scores so AI agents can decide
  whether to trust the data.

## API Endpoints

| Method | Path                          | Description                              |
| ------ | ----------------------------- | ---------------------------------------- |
| GET    | `/health`                     | Health check                             |
| GET    | `/places`                     | List places (paginated: `limit`, `offset`) |
| GET    | `/places/stale`               | List places by staleness score           |
| GET    | `/places/{id}`                | Get one place with sources and conflicts |
| POST   | `/places/nearby`              | Find places within a radius              |
| POST   | `/places/deduplicate`         | Find duplicate groups across the dataset |
| POST   | `/places/reconcile/{id}`      | Reconcile multi-source data for a place  |

Route ordering matters: `/places/stale` is registered before `/places/{id}`
so it isn't captured as `place_id="stale"`.

See `/docs` (OpenAPI auto-generated) for full request/response schemas.

## Key Design Decisions

### Why two-stage deduplication (geography → name)?

Geographic distance is `O(1)` per comparison. Fuzzy name matching is
significantly more expensive. Filtering on geography first eliminates most
non-duplicate comparisons cheaply before running expensive similarity
calculations.

### Why source priority over majority voting?

In real data, three sources rarely agree. Majority voting only works when
you have many sources. Source priority — derived from historical accuracy
in production — gives a defensible canonical record even with just two
sources.

### Why priority-source coordinates instead of an average?

Averaging `lat`/`lng` across sources pulls the canonical position toward
the least-trusted source. With even a small positional error, downstream
geographic dedup breaks. Picking the highest-priority source's coordinate
keeps canonical position stable.

### Why category-specific staleness thresholds?

Restaurant hours change quarterly. Park boundaries change rarely. A single
"stale after N days" threshold misclassifies both. Category-specific
thresholds match how the world actually changes.

### Why log every conflict instead of resolving silently?

For AI agents consuming this data, knowing that sources disagree is itself
information. An agent can hedge its answer ("according to Yelp this place
closes at 11 PM, but Google says 10 PM"). Silent resolution loses that
signal.

## Reliability Patterns

- **Graceful degradation**: `reconcile_with_fallback` returns a usable
  result even when reconciliation raises, marking the response with a
  `fallback_reason`.
- **Input validation at boundaries**: Pydantic enforces lat/lng/radius/limit
  ranges on every request body.
- **Confidence scoring**: every response carries `HIGH`/`MEDIUM`/`LOW` so
  consumers can decide whether to trust it.
- **Audit logging**: every conflict and staleness reason is stored, never
  silently resolved.
- **Idempotent reads**: `GET` endpoints are safe to retry.

## What I'd Add in Production

This is a portfolio-grade demonstration of the patterns. A production
deployment would need:

- **PostgreSQL with PostGIS** instead of SQLite. The query patterns
  translate cleanly; PostGIS adds GiST spatial indexes that make geographic
  queries fast at scale (`ST_DWithin` over GiST replaces the haversine
  bounding-box pre-filter used here).
- **Redis caching layer** for hot queries — popular places get queried
  many times more than cold ones.
- **Background workers** (Celery / RQ) for expensive operations like full
  deduplication runs on hundreds of thousands of records.
- **CDN cache** in front of the API for read-heavy traffic.
- **Real source ingestion pipelines** — currently the service uses seed
  data; production would have workers polling Google Places, Yelp, and
  other sources continuously.
- **Machine-learned thresholds** instead of hardcoded magic numbers — the
  fuzzy-match threshold (80%) and distance threshold (100 m) should be
  tuned per category from labelled examples.
- **Idempotency keys** on write endpoints so retries don't duplicate
  conflict log entries.

## Tech Stack

- **Python 3.11+**
- **FastAPI** — async, type-safe web framework
- **SQLite** — local persistence (PostgreSQL + PostGIS in production)
- **Pydantic** — request/response validation
- **rapidfuzz** — fuzzy string matching
- **pytest** + **httpx** — testing

## Running Locally

### Option A: with Make (one-liner setup)

```bash
make install   # creates venv, installs deps
make seed      # loads 50 Bangalore places into places.db
make run       # starts the dev server on :8000
make test      # runs the full pytest suite
```

`make help` lists every target.

### Option B: raw commands

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Unix
source venv/bin/activate

pip install -r requirements.txt
python -m src.seed
uvicorn src.main:app --reload
```

### Option C: Docker (no Python needed)

```bash
docker build -t place-data-service .
docker run --rm -p 8000:8000 place-data-service
```

The image seeds the DB on first boot and runs the API on port 8000.

Open <http://localhost:8000/docs> for interactive API docs.

### Reproducible builds

`requirements.txt` uses `>=` for flexibility. For exact reproducibility,
install from the lock file:

```bash
pip install -r requirements.lock.txt
```

### Quick smoke test

For a one-shot walkthrough of every endpoint with formatted output, run the
bundled script (server must be up):

```bash
python scripts/try_api.py
```

Or hit individual endpoints with curl:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/places?limit=5"
curl -X POST http://localhost:8000/places/nearby \
  -H "Content-Type: application/json" \
  -d '{"lat":12.9716,"lng":77.5946,"radius_km":1.0}'
curl -X POST http://localhost:8000/places/reconcile/place_009
```

## Testing

```bash
pytest          # 39 tests, ~1 second
pytest -v       # show every test name
pytest -k geo   # match by substring
```

**39 tests** covering geographic computation, deduplication logic, source
reconciliation, staleness detection, and API contracts. Each test runs
against an isolated SQLite database via the `isolated_db` fixture in
`tests/conftest.py` — tests never touch your real `places.db`.

## Continuous Integration

GitHub Actions runs the full pytest suite on every push and PR across
**Python 3.11, 3.12, and 3.13**. The workflow lives in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml); the green badge
at the top of this README links to the latest run.

## Project Structure

```
place-data-service/
├── data/
│   ├── seed_places.json              50 Bangalore places
│   └── conflicting_sources.json      15 places with multi-source conflicts
├── src/
│   ├── main.py                       FastAPI app + routes
│   ├── models.py                     Pydantic request/response schemas
│   ├── database.py                   SQLite schema + batched queries
│   ├── geo.py                        Haversine + bounding-box helpers
│   ├── dedup.py                      Two-stage deduplication
│   ├── reconcile.py                  Source reconciliation
│   ├── staleness.py                  Staleness scoring
│   └── seed.py                       Loads data/*.json into the DB
├── tests/                            pytest suite (39 tests)
│   ├── conftest.py                   Isolated-DB and seed fixtures
│   └── test_*.py                     One file per src module
├── scripts/
│   └── try_api.py                    Endpoint walk-through script
├── .github/
│   ├── workflows/ci.yml              Test matrix on push/PR
│   ├── ISSUE_TEMPLATE/               Bug + feature templates
│   └── pull_request_template.md
├── Dockerfile + .dockerignore        Multi-stage build, non-root user
├── Makefile                          install / seed / run / test / docker-*
├── pyproject.toml                    Project metadata, pytest + pyright config
├── requirements.txt                  Loose deps for development
├── requirements.lock.txt             Pinned versions for reproducible builds
└── README.md                         This file
```

## Configuration

| Env var          | Default       | Purpose                                  |
| ---------------- | ------------- | ---------------------------------------- |
| `PLACE_DB_PATH`  | `./places.db` | SQLite database path (tests override it) |

## Reporting issues

Bug reports and feature requests use the templates under
`.github/ISSUE_TEMPLATE/`.
