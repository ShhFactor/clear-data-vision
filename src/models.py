from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


Confidence = Literal["HIGH", "MEDIUM", "LOW"]


class Conflict(BaseModel):
    field_name: str
    source_a: str
    value_a: str
    source_b: str
    value_b: str


class PlaceIn(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: Optional[str] = None
    category: Optional[str] = None
    source: str


class Place(BaseModel):
    id: str
    canonical_name: str
    lat: float
    lng: float
    address: Optional[str] = None
    category: Optional[str] = None
    confidence: Confidence
    last_verified: datetime
    sources: list[str] = []
    conflicts: list[Conflict] = []


class NearbyQuery(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=100, default=1.0)
    category: Optional[str] = None
    limit: int = Field(gt=0, le=100, default=20)


class NearbyResult(BaseModel):
    place: Place
    distance_km: float


class NearbyResponse(BaseModel):
    query: NearbyQuery
    results: list[NearbyResult]
    total: int


class DedupRequest(BaseModel):
    distance_threshold_m: float = Field(gt=0, le=10000, default=100)
    name_similarity_threshold: int = Field(ge=0, le=100, default=80)


class DuplicateGroup(BaseModel):
    places: list[Place]
    confidence: Confidence
    reason: str


class DedupResponse(BaseModel):
    duplicate_groups: list[DuplicateGroup]
    total_groups: int


class ReconcileResponse(BaseModel):
    place_id: str
    canonical: dict
    conflicts: list[Conflict]
    confidence: Confidence
    needs_escalation: bool
    fallback_reason: Optional[str] = None


class StalePlace(BaseModel):
    place: Place
    staleness_score: float
    reasons: list[str]


class StaleResponse(BaseModel):
    stale_places: list[StalePlace]


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
