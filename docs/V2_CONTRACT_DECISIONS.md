# V2 contract decisions: proposed contracts mapped to the real code

This document responds to the combined engineering handoff (`01_NOVIX_V2_COMBINED_ENGINEERING_HANDOFF.md`, §4.0 step 4 and §10). For every contract that handoff proposes, it records whether it is already implemented, added in Phase 4, or deferred.

The handoff's route names are provisional. Where the Phase 3 code already had a working convention, that convention stays and the handoff name is listed as an alias.

**Status labels**

| Label | Meaning |
| --- | --- |
| IMPLEMENTED-VERIFIED-IN-REPO | Code and tests exist, and they passed in Docker on 21 Nov 2026 |
| ADDED-P4 | New in Phase 4, verified in Docker and in a real browser |
| ALIAS | The proposal is served by an existing object under another name |
| DEFERRED | Not built yet; the phase that will build it is named |

## 1. Baseline verified before Phase 4 (read-only preflight, 21 Nov 2026)

| Check | Observed |
| --- | --- |
| Git | Branch `v2/backend-foundation` at `c16647a`, clean tree. `main` is at `aba3f2b` (= `origin/main`). Nothing pushed or merged |
| Migrations | `alembic current` and `heads` both `0003` |
| Database | PostgreSQL 17.11 and PostGIS 3.6.4. The `households.location` column is `geography(Point,4326)` with a GiST index |
| Docker | `db` and `api` healthy. The database port is not published |
| Test suite | `docker compose exec api python -m pytest -q`: **133 passed** |
| Seed (`seed_demo --check`) | 12 households, 50 people and 2 territories (6 + 6). 55 relationships and 10 enrolments. Minimum pin separation 80 m. INVARIANTS: OK |
| Accounts | `demo_worker_a` (DEMO-A), `demo_worker_b` (DEMO-B), `demo_supervisor` (DEMO-A and DEMO-B), `demo_admin` (no grant; the admin policy sees all). All **inactive** until the owner sets passwords |
| Round 1 routes | Off in V2: `/api/visits` returns 404 and health reports `legacy_round1_api: false` |
| Gnani | Prisma `prisma-v3.0` and Timbre `timbre-v3.0` are configured. No live calls were made in Phase 4 |

**Fixture facts (handoff R03; read from the seed, not invented):**
- H-003 (Territory A) has four members: Prakash Halli (head), Kavya Halli (spouse, PNC), "Baby of Kavya Halli" (born 6 days before the 21 Nov 2026 demo date, NEWBORN) and Nagamma Halli (the head's mother). The mother–newborn link is an explicit `mother_of` edge.
- The other mother–newborn pairs are in H-007 (baby 20 days old) and H-009 (baby 4 days old), both in Territory B.
- Pin labels are neutral, for example "Demo House 3, Synthetic Lane A". Every pin landmark says it is a synthetic Cubbon Park point and not a residence.

## 2. Data model

| Proposed (handoff) | Real object | Status |
| --- | --- | --- |
| `is_demo` | `is_demo_data` on users, territories, households, people and surveys (R02) | ALIAS |
| Household with a PostGIS point | `households`: `public_id` H-###, `territory_id`, `label`, `landmark`, `location geography(Point,4326)` (GiST), `location_source`, `is_demo_data` | IMPLEMENTED-VERIFIED-IN-REPO |
| Person, membership, relationships, enrolments | `people` (FK `household_id`, `active`), `person_relationships` (explicit edges), `programme_enrolments` (explicit only) | IMPLEMENTED-VERIFIED-IN-REPO |
| Worker territory grant | `territory_assignments` (active while `ends_at IS NULL`) | IMPLEMENTED-VERIFIED-IN-REPO |
| Spatial index | `ix_households_location` (GiST on geography) | IMPLEMENTED-VERIFIED-IN-REPO |
| Person-linked visits / idempotency receipt | none. The Round 1 `visits.beneficiary_id` is free text with no foreign key to `people` | DEFERRED to Phase 5 (additive migration) |

**Phase 4 schema change: none.** No migration and no data change. The only rows Phase 4 writes are `audit_events` rows for refused lookups (see §4).

## 3. REST routes

All routes require the Phase 2 session cookie (`asha_session`: httpOnly, Secure, SameSite=Strict). Every object lookup goes through `app/services/households.py`. Another territory's object, or a missing one, returns the same `404 {"detail":"Not found"}`.

| Proposed | Real route | Status and notes |
| --- | --- | --- |
| `GET /api/v2/territories/mine` | `GET /api/v2/territories` (the territories the caller may see: their active grants; admins see all, per the Phase 2 policy) and `GET /api/v2/auth/me` (role and territories) | ALIAS: no new route |
| `GET /api/v2/households?territory_id&bbox&cursor&limit&q` | `GET /api/v2/households?territory=<code>&q=&bbox=&after=&limit=` | IMPLEMENTED (P3) + ADDED-P4 (filters, see below) |
| `GET /api/v2/households/nearby?lat&lon&radius_m&limit` | same path | ADDED-P4 |
| `GET /api/v2/households/{household_id}` | same path. The key may be a UUID or H-### (case-insensitive) | IMPLEMENTED-VERIFIED-IN-REPO (+ denial audit) |
| `GET /api/v2/households/{id}/members` | same path, returns `PersonOut[]` | IMPLEMENTED-VERIFIED-IN-REPO. Not paginated, because a household's size bounds it |
| Member binding: "verify FK + territory" | `GET /api/v2/households/{household}/members/{person}` | ADDED-P4: the server recheck behind **Select member**. Returns 404 if the person is in another household (even a visible one), inactive, or missing |
| `GET /api/v2/people/{person_id}` | same path. The key may be a UUID or P-### | IMPLEMENTED-VERIFIED-IN-REPO. Relationship names are now limited to the caller's territories |
| `GET /api/v2/people/{id}/visits` | none | DEFERRED to Phase 5. No person-linked visits exist yet, and the front section says "only if already available". A stub that always returned `[]` would be misleading |

**List filters (Phase 4).** Each filter only narrows the caller's authorized set; none can widen it.
- `q`: 1–64 characters, case-insensitive. Matches the household ID or label text. `%` and `_` are matched literally. People's names are not searchable from the map.
- `bbox=min_lon,min_lat,max_lon,max_lat`: GeoJSON order. Values must be finite and within the WGS84 ranges, with min < max and a span of at most 1° each way. Antimeridian boxes are refused. Bounds are inclusive.
- `territory=<code>`: a code outside the caller's grants returns `[]`, exactly like a code that does not exist.
- `limit`: 1–100, default 100.
- `after`: keyset cursor, the last `H-###` of the previous page. Results are in natural order (H-002 before H-010). When more remain, the response carries the next cursor in the `X-Next-After` header.
- The body stays the Phase 3 bare list. The handoff's `{items, next_cursor}` envelope corresponds to this header, so existing clients keep working (§8.1, "preserve compatibility and document the alias").

**Nearby.** Required `lat` (−90..90) and `lon` (−180..180), which must be finite. `radius_m` 1–5000 (default 1000), `limit` 1–100 (default 20).
- Query: authorized territories ∩ `ST_DWithin(location, ST_MakePoint(lon, lat)::geography, radius_m)`, which uses the GiST index.
- `distance_m` comes from `ST_Distance` on geography: metres on the WGS84 spheroid, rounded to 0.1 m.
- Sort: distance first, then natural ID order, so ties such as overlapping pins are deterministic.
- It is a suggestion list only: nothing is selected or confirmed from GPS.

**Pin DTO (`HouseholdPin`)**
- Fields: `id`, `public_id`, `label`, `landmark`, `territory_code`, `latitude`, `longitude`, `location_source`, `member_count`, `is_demo_data`. Nearby adds `distance_m`.
- Aliases for the handoff example: `household_id` = `id`, `demo_code` = `public_id`, `is_demo` = `is_demo_data`, `locality_label` = `label`/`landmark`.
- The position uses named fields instead of a GeoJSON array. The browser converts them to MapLibre's `[longitude, latitude]` in one tested helper (`frontend/src/features/households/geo.ts`).
- Pins carry no names, programmes, ages, relationships or health fields. Tests check the exact key set and the raw response text.

**Errors**

| Status | When |
| --- | --- |
| 401 | Not signed in, expired, revoked or deactivated |
| 403 | Role or anti-CSRF refusal (writes only) |
| 404 | Uniform for a foreign or missing household or person |
| 422 | Invalid search, bbox, cursor, coordinates, radius or limit. The message is safe and contains no SQL |
| 429 | More than `DISCOVERY_REQUESTS_PER_MINUTE` household/person reads per user per minute (default 240, in memory) |

## 4. Security decisions added in Phase 4

- **Uniform, audited refusals.** Every refused household or person lookup writes one `access.denied` audit event, whether the record is missing, outside the caller's territories, or malformed:
  - It records the actor, the resource kind, the requested ID (or `<malformed>`) and the route. It never records names.
  - Missing and foreign lookups take the same code path, so neither the response nor its timing reveals which IDs exist.
- **Relationship scope.** `PersonOut.relationships` lists a related person only if that person's household is in the caller's territories. No API creates cross-household edges, but the database does not forbid them. This is defence in depth, and it is tested.
- **Location privacy.** uvicorn access logs keep the path but replace the query string with `?[redacted]`, so a worker's GPS fix (`nearby?lat=…&lon=…`) and search text never reach container logs. The browser asks for location only when the worker presses **Use my location**: a single reading, no tracking, not stored.
- **Rate limit.** Applies per user on household/person reads (429), to slow scripted scanning. Like the login limiter it is in memory, so a restart clears it.
- **Round 1 routes.** Still off by default in V2. The Phase 4 tests assert it again.

## 5. Browser flow (`/v2`)

The Round 1 voice screen at `/` is unchanged. `/v2` is a separate lazy-loaded chunk, and MapLibre is a further on-demand chunk.

The handoff's state machine (§7.3) is implemented as a pure reducer in `frontend/src/features/households/selection.ts`, unit-tested with Vitest. Its states map as follows:

| Handoff state | Reducer phase |
| --- | --- |
| NO_CONTEXT | `none` |
| HOUSEHOLD_PREVIEW | `household_preview` |
| HOUSEHOLD_CONFIRMED | `household_confirmed` |
| PERSON_PREVIEW | `person_preview` |
| PERSON_CONFIRMED | `person_confirmed` |

How the flow behaves:
- A pin, list row, search result or GPS suggestion only creates a candidate. The preview shows the pin fields and no members.
- **Confirm household** fetches the household detail and members. These requests are the server recheck.
- **Select member** calls the member binding route. Only a 200 response selects the member.
- A late response for a household or person the worker has already moved away from is ignored.
- Choosing another household drops the member. Logout, an expired or revoked session, or a refused recheck resets everything.
- The workspace is keyed by user and grants, so a grant change also resets it. The session is rechecked every 60 s and whenever the tab becomes visible.
- The breadcrumb always shows exactly what is confirmed, for example `Selected: H-003 / Kavya Halli`.

## 6. Map tiles (handoff §6.1)

The default basemap is a **plain background with no external requests**. The pins are still drawn and are keyboard-focusable buttons.

**Proposed compliant alternative (owner opt-in):**
- OpenFreeMap: `VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty` in `frontend/.env.local`, which is git-ignored.
- What its terms say (verified 21 Nov 2026):
  - It is free, with no API key, registration, cookies or view limits.
  - Commercial use is allowed.
  - MapLibre adds the required attribution automatically.
- Conditions the owner must accept:
  - The integrator must be 18 or older.
  - The service is as-is, with no SLA, and may be discontinued at any time.
  - Requests are processed by Cloudflare.
  - Hungarian law applies.
  - Automated data collection is forbidden.
- For a real deployment, every tile request reveals the viewed area and the client's IP to the provider.

**Failure behaviour.** If the style or tiles fail (offline, blocked, provider down), the map says so and keeps the pins, and the household list and search still work. If WebGL2 is unavailable, the list is the fallback.

**Automated tests.** They never contact the tile provider. The browser harness answers the configured style request locally, or refuses it to simulate an outage.

## 7. Handed to Phase 5 (not built)

- An authenticated, member-bound voice session. The server must recheck the household–person pair and the active grant at session start and again at save, whatever the browser holds.
- An additive migration that links visits to `people.id` and adds an idempotency receipt.
- `GET /api/v2/people/{id}/visits`, once person-linked visits exist.
