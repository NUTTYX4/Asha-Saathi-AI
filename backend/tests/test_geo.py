"""V2 Phase 4: map-query validation, access-log redaction and the request limiter.

Pure unit tests (no database): they run on the host and in Docker.
"""

import logging

import pytest

from app.auth.ratelimit import RequestRateLimiter
from app.core.logging import RedactQueryString, configure_logging
from app.services import geo


# ------------------------------------------------------------------ bounding box
def test_bbox_parses_in_lon_lat_order():
    box = geo.parse_bbox("77.58,12.96,77.61,12.99")
    assert (box.min_lon, box.min_lat, box.max_lon, box.max_lat) == (77.58, 12.96, 77.61, 12.99)


def test_bbox_at_exact_span_limit_is_allowed():
    geo.parse_bbox(f"77.0,12.0,{77.0 + geo.MAX_BBOX_SPAN_DEG},{12.0 + geo.MAX_BBOX_SPAN_DEG}")


@pytest.mark.parametrize("raw", [
    "", "77.5,12.9,77.6", "77.5,12.9,77.6,13.0,1", "a,b,c,d", "77.5,,77.6,13.0",
    "nan,12.9,77.6,13.0", "77.5,12.9,inf,13.0", "-inf,12.9,77.6,13.0", "77.5,12.9,77.6,NaN",
    "180.1,12.9,180.2,13.0", "-180.2,12.9,-180.1,13.0", "77.5,-90.5,77.6,13.0", "77.5,12.9,77.6,90.01",
    "77.6,12.9,77.5,13.0",          # min_lon > max_lon (antimeridian boxes unsupported)
    "77.5,13.0,77.6,12.9",          # min_lat > max_lat
    "77.5,12.9,77.5,13.0",          # zero width
    "77.0,12.0,78.5,12.5",          # wider than the span limit
    "77.0,12.0,77.5,13.5",          # taller than the span limit
])
def test_bad_bbox_rejected(raw):
    with pytest.raises(ValueError):
        geo.parse_bbox(raw)


@pytest.mark.parametrize("lat,ok", [(0, True), (-90, True), (90, True), (90.0001, False), (-90.0001, False),
                                    (float("nan"), False), (float("inf"), False)])
def test_latitude_range(lat, ok):
    assert geo.valid_lat(lat) is ok


@pytest.mark.parametrize("lon,ok", [(0, True), (-180, True), (180, True), (180.0001, False),
                                    (-180.0001, False), (float("nan"), False), (float("-inf"), False)])
def test_longitude_range(lon, ok):
    assert geo.valid_lon(lon) is ok


# ------------------------------------------------------------------ search text and cursor
def test_search_text_is_trimmed():
    assert geo.normalise_search("  H-003 ") == "H-003"


@pytest.mark.parametrize("raw", ["", "   ", "x" * (geo.MAX_SEARCH_LENGTH + 1), "Kavya\x00", "a\x7fb", "H-003\n1"])
def test_bad_search_text_rejected(raw):
    with pytest.raises(ValueError):
        geo.normalise_search(raw)


@pytest.mark.parametrize("raw,expected", [("H-006", "H-006"), (" h-012 ", "H-012"), ("H-1000", "H-1000")])
def test_cursor_normalised(raw, expected):
    assert geo.normalise_household_cursor(raw) == expected


@pytest.mark.parametrize("raw", ["", "H-1", "P-001", "H-00a", "H-٠٠١", "H-001; DROP TABLE x", "6"])
def test_bad_cursor_rejected(raw):
    with pytest.raises(ValueError):
        geo.normalise_household_cursor(raw)


# ------------------------------------------------------------------ access-log redaction
def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                             ("127.0.0.1:5000", "GET", path, "1.1", 200), None)


def test_access_log_drops_gps_query_string():
    record = _access_record("/api/v2/households/nearby?lat=12.977466&lon=77.594572&radius_m=1000")
    assert RedactQueryString().filter(record) is True
    line = record.getMessage()
    assert "12.977466" not in line and "77.594572" not in line
    assert "/api/v2/households/nearby?[redacted]" in line


def test_access_log_without_query_unchanged():
    record = _access_record("/api/health")
    RedactQueryString().filter(record)
    assert record.getMessage() == '127.0.0.1:5000 - "GET /api/health HTTP/1.1" 200'


def test_configure_logging_installs_the_filter_once():
    configure_logging()
    configure_logging()
    filters = [f for f in logging.getLogger("uvicorn.access").filters if isinstance(f, RedactQueryString)]
    assert len(filters) == 1


# ------------------------------------------------------------------ request limiter
def test_request_limiter_blocks_after_limit_per_key(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.auth.ratelimit.time.monotonic", lambda: now[0])
    limiter = RequestRateLimiter(3, 60)
    assert [limiter.allow("u1") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("u2") is True          # other users are unaffected
    now[0] += 61                                 # window passes
    assert limiter.allow("u1") is True
