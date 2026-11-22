# Role and security matrix

**Roles in the schema** (`users.role` CHECK constraint): `worker`, `supervisor` and `admin`. There are no other roles.

**Accounts tested:** synthetic accounts on disposable databases only.

- `demo_worker_a` (DEMO-A)
- `demo_worker_b` (DEMO-B)
- `demo_supervisor` (both territories)
- `demo_admin`
- `e2e_supervisor_a` (DEMO-A only), in browser tests

Test passwords were random one-time values: generated per run, passed to the bootstrap over stdin, and never printed or stored. **No live account password was read or changed.**

| Capability | worker (own territory) | worker (other territory) | supervisor | admin | Enforced where | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Sign in / sign out / `me` | yes | yes | yes | yes | server (session cookie: httpOnly, Secure, SameSite=Strict) | `test_auth.py`, `test_admin_dashboard.py` |
| List households and map pins | own 6 | — | all 12 | all 12 | server `visible_territory_ids`; per-user read budget (429) | matrix, `test_households.py`, Phase 4 |
| Read a household, its members or a person | yes | **404** | yes | yes | server; 404 hides existence | matrix |
| Add a household member (`POST /households/{key}/members`, CSRF) | yes | **404** | **403** (read-only) | yes, any territory | server `require_roles("worker","admin")` plus scope | `test_households.py` |
| Read a person's confirmed visits | yes | **404** | yes | yes | server | matrix, `test_voice_v2.py` |
| Lost-ACK receipt lookup | own visits only | 404 | 404 | 404 | server (`worker_id` = caller) | matrix |
| Start a voice visit (`/ws/v2/session`) | yes, bound to one person | NOT_AVAILABLE | read-only (no Start) | — | server `authorize_start` and periodic revalidation | `test_voice_v2.py`, Phase 5 S3/S5 |
| Save a visit | only after the latest read-back and an explicit Confirm and Save | — | — | — | server (read-back ack version, `FOR SHARE` locks, unique `(worker, client_visit_id)`) | `test_voice_v2.py`, Phase 5 S1 |
| Admin dashboard views (7 GET routes) | **403** | **403** | **403** | yes | server `require_roles("admin")` | matrix, Phase 7 A4 |
| Create users, territories or assignments; end or reassign an assignment | **403** | **403** | **403** | yes, plus the anti-CSRF header | server | `test_admin_writes_require_admin_and_csrf`, Phase 7 A3/A4 |
| Change own role or territory | **impossible**: no such route; `POST /auth/me` returns 405 | — | — | — | server | `test_admin_write_validation_and_role_escalation` |

## How the role checks were counted

- **GET routes, as every role.** `test_endpoint_role_matrix` sends 21 request rows × 5 roles (signed out, worker A, worker B, supervisor, admin) = **105 requests**. The 21 rows cover **20 distinct GET routes**: `/territories/{id}` appears twice, once in scope and once with an unknown ID. That is all 7 admin dashboard GETs and 13 non-admin GETs.
- **The 8 POST routes, by targeted tests.** These are not in the matrix:
  - `/auth/login` and `/auth/logout`: CSRF and wrong-password tests.
  - `/admin/users`, `/admin/territories`, `/admin/assignments` and `/admin/assignments/{id}/end`: 4 parametrized cases. Each checks signed out (401), worker A (403), supervisor (403) and admin without CSRF (403), for 16 checks in total. Separate cases check admin validation.
  - `/admin/assignments/{id}/reassign`: signed out (401), worker A, worker B and supervisor (403), admin without CSRF (403), plus 5 validation and conflict cases and the success case.
  - `POST /households/{key}/members`: `test_households.py`, covering an own-territory worker, a foreign territory (404) and a supervisor (403).
- **Not tested as all 5 roles.** Not every one of the 28 routes was tested as all 5 roles. 28 × 5 = 140 would be the full product, and this report does not claim it.

## Checks that passed

1. **Admin is enforced on the server.** Every admin route returns 403 for workers and supervisors, through both direct API calls (`fetch` in the browser and the TestClient) and the UI. The dashboard isn't rendered for those roles, and that is not the control: the server is.
2. **Territory isolation is two-way.** Worker A gets 404 on territory B households, members, people and visits, and the reverse is also true. The WebSocket refuses a foreign person with NOT_AVAILABLE before any speech.
3. **Admin filters can't widen access.** Filters run only on admin routes, which non-admins can't reach. The worker and household routes ignore client-supplied scope.
4. **Mutations validate their input:**
   - unknown or malformed IDs give 404 or 422;
   - unexpected fields on a reassign give 422 (`extra="forbid"`);
   - `role: "root"` gives 422;
   - nothing is written on a refused request (row counts are asserted).
5. **Every write needs the anti-CSRF header**, including login and logout. Without it the response is 403.
6. **Audit records the actor.** `assignment.reassign` stores the admin's user ID and the from/to territories (asserted in pytest and in Phase 7 A3).
7. **Sessions end cleanly.** After logout, admin routes return 401. An ended assignment immediately hides its territory, and live voice sessions end on revalidation.
8. **No sensitive data leaks:**
   - admin user listings never include `password_hash`;
   - no error body contains a traceback, the word "password" or SQLAlchemy text (checked on all 105 matrix requests);
   - a failed login returns a generic message.
9. **Login lockout was not stress-tested.** Only one wrong-password attempt was made per run. The limiter itself has unit tests in `test_auth.py`.

## Known limitation

- **Shared client address behind the demo proxy.** Behind the Cloudflare/Caddy demo proxy, every client shares one address in the login limiter. Repeated wrong passwords for one account can therefore lock that account for everyone for the window. This is a deliberate trade-off, documented in `deploy/tunnel/README.md`.
