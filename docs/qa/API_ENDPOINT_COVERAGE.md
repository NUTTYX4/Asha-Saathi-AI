# API endpoint coverage

- **Branch:** `v2/final-qa-admin`
- **Live inventory:** discovered from the running API's OpenAPI document (read-only `GET /openapi.json` on `127.0.0.1:8000`). Branch additions were found by reading the source.
- **Test database:** all tests ran against disposable PostgreSQL databases that the tests create and drop. The live database was not touched.

## Inventory

| | Count |
| --- | --- |
| HTTP routes on the **live** API (commit `126fd09`-era image) | 21 |
| New HTTP routes on this branch (admin dashboard) | 7 |
| **HTTP routes on this branch** | **28** |
| WebSocket endpoints (`/ws/v2/session`) | 1 |
| Round 1 routes (`/api/visits`, `/api/followups`, `/ws/session`) | 3. Intentionally **not registered** while `LEGACY_ROUND1_API_ENABLED=false` (the V2 default). The proxy also returns 404 for them |

FastAPI's own `/docs` and `/openapi.json` exist on the API port only (`127.0.0.1`). The demo proxy does not forward them.

## Matrix

**Roles:** anonymous (`anon`), `worker_a` (DEMO-A), `worker_b` (DEMO-B), `supervisor` (both territories, read-only), `admin`.

**Statuses:**

- 401 means not signed in.
- 403 means the role is not permitted, or the anti-CSRF header is missing.
- 404 for an object outside your scope is deliberate: it does not confirm that another territory's record exists.

**Test files:**

- `M` = `backend/tests/test_admin_dashboard.py::test_endpoint_role_matrix`. It sends every listed GET as all 5 roles: 21 rows × 5 roles = 105 requests. It also checks that no error body contains a traceback, the word "password" or SQLAlchemy text.
- `AD` = `test_admin_dashboard.py`
- `H` = `test_households.py`
- `A` = `test_auth.py`
- `V` = `test_voice_v2.py`
- `C` = `test_phase5_codex_*.py`
- `E7` = `e2e/phase7_admin.py`
- `E4`, `E5`, `E6` = the Phase 4, 5 and 6 browser suites

| Method | Route | Roles allowed | anon | worker_a | worker_b | supervisor | admin | Input/negative tests | Side effects | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/health` | public | 200 | 200 | 200 | 200 | 200 | none | none | M | PASS |
| POST | `/api/v2/auth/login` | public + CSRF | — | — | — | — | — | missing CSRF 403; wrong password 401 with a generic message; rate limit | session row, audit | A, AD, E4 | PASS |
| POST | `/api/v2/auth/logout` | signed in + CSRF | — | — | — | — | — | missing CSRF 403; access after logout 401 | session revoked, audit | A, AD | PASS |
| GET | `/api/v2/auth/me` | signed in | 401 | 200 | 200 | 200 | 200 | `POST` gives 405 (no write path, so no role change) | none | M, AD | PASS |
| GET | `/api/v2/territories` | signed in (own scope) | 401 | 200 | 200 | 200 | 200 | — | none | M | PASS |
| GET | `/api/v2/territories/{id}` | in scope | 401 | 200 | 404 | 200 | 200 | random UUID 404; bad UUID 422 | none | M | PASS |
| POST | `/api/v2/admin/users` | admin + CSRF | 401 | 403 | 403 | 403 | 201 | role `root` 422; duplicate 409 | user row, audit | AD, A | PASS |
| POST | `/api/v2/admin/territories` | admin + CSRF | 401 | 403 | 403 | 403 | 201 | missing `code` 422; duplicate 409 | territory row, audit | AD, A | PASS |
| POST | `/api/v2/admin/assignments` | admin + CSRF | 401 | 403 | 403 | 403 | 201 | unknown IDs 404; admin target 422; duplicate active 409 | assignment row, audit | AD, A, E7 | PASS |
| POST | `/api/v2/admin/assignments/{id}/end` | admin + CSRF | 401 | 403 | 403 | 403 | 200 | unknown 404; repeat is idempotent | `ends_at` set, audit | AD, A | PASS |
| POST | `/api/v2/admin/assignments/{id}/reassign` **(new)** | admin + CSRF | 401 | 403 | 403 | 403 | 201 | no CSRF 403; extra field 422; same territory 409; unknown territory or assignment 404; already ended 409 | old ended and new created in one transaction, audit | AD, E7 | PASS |
| GET | `/api/v2/admin/audit` | admin | 401 | 403 | 403 | 403 | 200 | `limit` bounds 1–500 | none | M, E7 | PASS |
| GET | `/api/v2/admin/overview` **(new)** | admin | 401 | 403 | 403 | 403 | 200 | `date_from` after `date_to` 422; bad UUID 422 | none | M, AD, E7 | PASS |
| GET | `/api/v2/admin/workers` **(new)** | admin | 401 | 403 | 403 | 403 | 200 | filters | none | M, AD, E7 | PASS |
| GET | `/api/v2/admin/visits` **(new)** | admin | 401 | 403 | 403 | 403 | 200 | `limit=0` 422; bad `sort` 422; type filter; paging | none | M, AD, E7 | PASS |
| GET | `/api/v2/admin/coverage` **(new)** | admin | 401 | 403 | 403 | 403 | 200 | future range gives 0 visited | none | M, AD, E7 | PASS |
| GET | `/api/v2/admin/users` **(new)** | admin | 401 | 403 | 403 | 403 | 200 | role filter; never returns a password hash | none | M, AD | PASS |
| GET | `/api/v2/admin/assignments` **(new)** | admin | 401 | 403 | 403 | 403 | 200 | `include_ended=false` | none | M, AD | PASS |
| GET | `/api/v2/households` | signed in (own scope) | 401 | 200 (6) | 200 (6) | 200 (12) | 200 (12) | `q`, paging cursor, bbox | none | M, H, E4 | PASS |
| GET | `/api/v2/households/nearby` | signed in (own scope) | 401 | 200 | 200 | 200 | 200 | lat/lon/radius bounds 422 | none | M, H, E4 | PASS |
| GET | `/api/v2/households/{key}` | in scope | 401 | 200 | 404 | 200 | 200 | by public ID or UUID | audit (access) | M, H, E4 | PASS |
| GET | `/api/v2/households/{key}/members` | in scope | 401 | 200 | 404 | 200 | 200 | — | audit | M, H, E4 | PASS |
| GET | `/api/v2/households/{key}/members/{person}` | in scope | 401 | 200 | 404 | 200 | 200 | person of another household 404 | audit | M, H | PASS |
| POST | `/api/v2/households/{key}/members` | worker in scope + CSRF | 401 | 201 | 404 | 403 | per role rules | future date of birth 422 | person row, audit | H | PASS |
| GET | `/api/v2/people/{key}` | in scope | 401 | 200 | 404 | 200 | 200 | — | audit | M, H | PASS |
| GET | `/api/v2/people/{key}/visits` | in scope | 401 | 200 | 404 | 200 | 200 | `before` cursor of another person 422; `limit` 1–50 | none | M, V, E5 | PASS |
| GET | `/api/v2/people/{key}/visits/{visit_id}` | in scope | 401 | 200 | 404 | 200 | 200 | visit of another person 404 | none | M, V | PASS |
| GET | `/api/v2/visits/by-client-key/{id}` | own visits only | 401 | 200 (owner) | 404 | 404 | 404 | foreign key 404 | none | M, V, C | PASS |
| WS | `/ws/v2/session` | worker in scope, cookie, same Origin | refused | binds | NOT_AVAILABLE | read-only | — | foreign Origin 403; no cookie 403; foreign person NOT_AVAILABLE; superseded 4409; revoked mid-session | one confirmed row only after an explicit confirm | V, C, E5, tunnel check | PASS |

**Results:**

- Branch backend suite: **360 passed, 6 skipped**, run in a disposable container built from the branch source. The 6 skipped tests need host-only services, and the cause is unchanged from before.
- Admin browser suite: **74/74** before the dialog-height regression check was added (now 75 checks, see `ADMIN_DASHBOARD_QA.md`).
- Matrix: **105/105** requests returned the expected status.
