"""Validation for map queries (bounding box, nearby point). Pure functions: no database.

Coordinates are WGS84 degrees. A bbox is `min_lon,min_lat,max_lon,max_lat` (GeoJSON order:
longitude first). Distances and radii are metres on the spheroid (PostGIS geography).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Technical limits (not clinical values). Tunable after measurement.
MAX_BBOX_SPAN_DEG = 1.0        # about 110 km: far larger than a worker's area, small enough to stop scans
MAX_NEARBY_RADIUS_M = 5000
DEFAULT_NEARBY_RADIUS_M = 1000
MAX_PAGE_LIMIT = 100
DEFAULT_NEARBY_LIMIT = 20
MAX_SEARCH_LENGTH = 64

_HOUSEHOLD_KEY = re.compile(r"H-[0-9]{3,}")  # ASCII digits only, as in the database CHECK


@dataclass(frozen=True)
class BBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


def _finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))


def valid_lat(lat: float) -> bool:
    return _finite(lat) and -90.0 <= lat <= 90.0


def valid_lon(lon: float) -> bool:
    return _finite(lon) and -180.0 <= lon <= 180.0


def parse_bbox(raw: str) -> BBox:
    """Parse `min_lon,min_lat,max_lon,max_lat`. Raises ValueError with a safe message."""
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise ValueError("bbox values must be numbers") from None
    if not (valid_lon(min_lon) and valid_lon(max_lon)):
        raise ValueError("bbox longitude must be between -180 and 180")
    if not (valid_lat(min_lat) and valid_lat(max_lat)):
        raise ValueError("bbox latitude must be between -90 and 90")
    if not (min_lon < max_lon and min_lat < max_lat):
        raise ValueError("bbox minimum must be less than maximum (antimeridian boxes are not supported)")
    if max_lon - min_lon > MAX_BBOX_SPAN_DEG or max_lat - min_lat > MAX_BBOX_SPAN_DEG:
        raise ValueError(f"bbox may span at most {MAX_BBOX_SPAN_DEG} degrees in each direction")
    return BBox(min_lon, min_lat, max_lon, max_lat)


def normalise_search(raw: str) -> str:
    """Trimmed search text. Raises ValueError if blank or too long."""
    text = raw.strip()
    if not text:
        raise ValueError("search text must not be blank")
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError("search text must not contain control characters")
    if len(text) > MAX_SEARCH_LENGTH:
        raise ValueError(f"search text may be at most {MAX_SEARCH_LENGTH} characters")
    return text


def normalise_household_cursor(raw: str) -> str:
    """Keyset cursor for household pages: the last `H-###` of the previous page."""
    key = raw.strip().upper()
    if not _HOUSEHOLD_KEY.fullmatch(key):
        raise ValueError("after must be a household ID such as H-006")
    return key
