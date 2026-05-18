"""FastAPI app. Routes are ordered so that literal paths like /places/stale
are matched before the /places/{place_id} catch-all.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query

from src.database import (
    clear_conflicts,
    fetch_place,
    fetch_source_records,
    get_conn,
    init_db,
    insert_conflict,
    list_all_places,
    list_places,
    list_places_in_bbox,
)
from src.dedup import find_duplicate_groups
from src.geo import bounding_box, haversine_km
from src.models import (
    DedupRequest,
    DedupResponse,
    DuplicateGroup,
    HealthResponse,
    NearbyQuery,
    NearbyResponse,
    NearbyResult,
    Place,
    ReconcileResponse,
    StalePlace,
    StaleResponse,
)
from src.reconcile import reconcile_with_fallback
from src.staleness import rank_by_staleness


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Place Data Service",
    description="Geospatial API serving verified, fresh place data to AI agents.",
    version="0.1.0",
    lifespan=lifespan,
)


def _to_place_model(row: dict) -> Place:
    return Place(
        id=row["id"],
        canonical_name=row["canonical_name"],
        lat=row["lat"],
        lng=row["lng"],
        address=row.get("address"),
        category=row.get("category"),
        confidence=row.get("confidence", "MEDIUM"),
        last_verified=row["last_verified"],
        sources=row.get("sources", []),
        conflicts=row.get("conflicts", []),
    )


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", timestamp=datetime.now(timezone.utc))


# --- /places routes ---------------------------------------------------------
# Order matters: literal paths declared before /places/{place_id}.

@app.get("/places", response_model=list[Place])
def get_places(
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
):
    with get_conn() as conn:
        rows = list_places(conn, limit=limit, offset=offset)
    return [_to_place_model(r) for r in rows]


@app.get("/places/stale", response_model=StaleResponse)
def get_stale_places(limit: int = Query(50, gt=0, le=500)):
    with get_conn() as conn:
        rows = list_all_places(conn)
    ranked = rank_by_staleness(rows)
    # Only return places with non-zero staleness
    stale = [r for r in ranked if r["staleness_score"] > 0][:limit]
    return StaleResponse(
        stale_places=[
            StalePlace(
                place=_to_place_model(r["place"]),
                staleness_score=r["staleness_score"],
                reasons=r["reasons"],
            )
            for r in stale
        ]
    )


@app.post("/places/nearby", response_model=NearbyResponse)
def post_nearby(query: NearbyQuery):
    min_lat, max_lat, min_lng, max_lng = bounding_box(query.lat, query.lng, query.radius_km)
    with get_conn() as conn:
        candidates = list_places_in_bbox(
            conn, min_lat, max_lat, min_lng, max_lng, category=query.category,
        )

    results: list[NearbyResult] = []
    for row in candidates:
        d = haversine_km(query.lat, query.lng, row["lat"], row["lng"])
        if d <= query.radius_km:
            results.append(NearbyResult(place=_to_place_model(row), distance_km=d))

    results.sort(key=lambda r: r.distance_km)
    results = results[: query.limit]
    return NearbyResponse(query=query, results=results, total=len(results))


@app.post("/places/deduplicate", response_model=DedupResponse)
def post_deduplicate(req: DedupRequest):
    with get_conn() as conn:
        rows = list_all_places(conn)
    groups = find_duplicate_groups(
        rows,
        distance_threshold_m=req.distance_threshold_m,
        name_similarity_threshold=req.name_similarity_threshold,
    )
    return DedupResponse(
        duplicate_groups=[
            DuplicateGroup(
                places=[_to_place_model(p) for p in g["places"]],
                confidence=g["confidence"],
                reason=g["reason"],
            )
            for g in groups
        ],
        total_groups=len(groups),
    )


@app.post("/places/reconcile/{place_id}", response_model=ReconcileResponse)
def post_reconcile(place_id: str):
    with get_conn() as conn:
        place = fetch_place(conn, place_id)
        if not place:
            raise HTTPException(status_code=404, detail=f"Place {place_id} not found")
        sources = fetch_source_records(conn, place_id)
        result = reconcile_with_fallback(sources)

        # Persist refreshed conflicts so /places/{id} reflects current state
        clear_conflicts(conn, place_id)
        for c in result.get("conflicts", []):
            insert_conflict(conn, place_id, c)
        conn.execute(
            "UPDATE places SET confidence = ? WHERE id = ?",
            (result["confidence"], place_id),
        )

    return ReconcileResponse(
        place_id=place_id,
        canonical=result["canonical"],
        conflicts=result["conflicts"],
        confidence=result["confidence"],
        needs_escalation=result["needs_escalation"],
        fallback_reason=result.get("fallback_reason"),
    )


@app.get("/places/{place_id}", response_model=Place)
def get_place(place_id: str):
    with get_conn() as conn:
        row = fetch_place(conn, place_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Place {place_id} not found")
    return _to_place_model(row)
