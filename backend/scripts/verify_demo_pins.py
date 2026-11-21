"""Check the synthetic demo pins against OpenStreetMap (public Overpass API, read-only).

    .venv\\Scripts\\python -m scripts.verify_demo_pins        (from backend/, needs internet)

For each pin:
  * it lies inside Cubbon Park (OSM way 22895320, leisure=park);
  * every mapped area containing it is green open space (park, garden, wood, grass, ...) and
    none is a building, water body, amenity/facility or other land use;
  * no building lies within 30 m.
Also checks the pins are >= MIN_PIN_SEPARATION_M apart.
Sends only the pin coordinates and a generic client name. Exit code 1 on any failure.
"""

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from app.seed.demo_data import MIN_PIN_SEPARATION_M, PINS

OVERPASS = "https://overpass-api.de/api/interpreter"
PARK_WAY_ID = 22895320
OPEN_SPACE = {
    "leisure": {"park", "garden"},
    "natural": {"wood", "scrub", "grassland", "tree_row"},
    "landuse": {"grass", "forest", "meadow", "recreation_ground", "village_green"},
}
ALWAYS_BAD = ("building", "amenity", "man_made", "aeroway", "military", "water", "waterway")


def overpass(query: str) -> dict:
    for attempt in range(6):
        try:
            req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(),
                                         headers={"User-Agent": "demo-pin-open-space-check/1.0"})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            wait = 5 * (attempt + 1)
            print(f"    Overpass {getattr(exc, 'code', type(exc).__name__)}; retrying in {wait}s")
            time.sleep(wait)
    raise SystemExit("Overpass API unavailable; try again later. (No result recorded.)")


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[1] - b[1]) * 111320 * math.cos(lat), (a[0] - b[0]) * 110540)


def classify(tags: dict) -> str | None:
    """'open' (acceptable), 'bad' (not open space), or None (irrelevant, e.g. admin boundary)."""
    if any(k in tags for k in ALWAYS_BAD):
        return "bad"
    relevant = [k for k in OPEN_SPACE if k in tags]
    if not relevant:
        return None
    return "open" if all(tags[k] in OPEN_SPACE[k] for k in relevant) else "bad"


def check_pin(lat: float, lon: float) -> tuple[bool, str]:
    # 1) Objects that form the areas containing the point (plus multipolygons using those ways).
    data = overpass(f"""[out:json][timeout:30];
is_in({lat},{lon})->.a;
way(pivot.a)->.w;
rel(pivot.a)->.r;
rel(bw.w)->.wr;
(.w; .r; .wr;);
out tags;""")
    time.sleep(1)
    # 2) Buildings within 30 m (separate query so results cannot be confused).
    near = overpass(f"""[out:json][timeout:30];
way(around:30,{lat},{lon})["building"];
out ids;""")
    buildings = [e["id"] for e in near["elements"]]
    in_park = any(e["type"] == "way" and e["id"] == PARK_WAY_ID for e in data["elements"])
    containing, bad = [], []
    for e in data["elements"]:
        tags = e.get("tags") or {}
        kind = classify(tags)
        if kind is None:
            continue
        label = next(f"{k}={tags[k]}" for k in (*ALWAYS_BAD, *OPEN_SPACE) if k in tags)
        containing.append(f"{label} ({e['type']} {e['id']})")
        if kind == "bad":
            bad.append(label)
    ok = in_park and not bad and not buildings
    detail = (f"in Cubbon Park={in_park}; inside: {', '.join(containing) or 'none'}; "
              f"buildings within 30 m: {buildings or 0}")
    return ok, detail


def main() -> int:
    failures = 0
    for public_id, (lat, lon) in PINS.items():
        ok, detail = check_pin(lat, lon)
        failures += not ok
        print(f"{public_id} ({lat:.6f}, {lon:.6f})  {'OK  ' if ok else 'FAIL'}  {detail}")
        time.sleep(2)  # be gentle with the public Overpass service
    pts = list(PINS.values())
    min_sep = min(metres(a, b) for i, a in enumerate(pts) for b in pts[i + 1:])
    sep_ok = min_sep >= MIN_PIN_SEPARATION_M
    failures += not sep_ok
    print(f"minimum pairwise separation: {min_sep:.0f} m ({'OK' if sep_ok else 'FAIL'}, need >= {MIN_PIN_SEPARATION_M} m)")
    print("RESULT:", "ALL PINS OK" if failures == 0 else f"{failures} FAILURE(S)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
