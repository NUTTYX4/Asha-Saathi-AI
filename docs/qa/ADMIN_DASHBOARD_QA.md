# Admin dashboard QA

**Commits:** `7212f6d` (API) and `69d09bb` (UI), on `v2/final-qa-admin`. Admins land on the dashboard and can switch to the field view at any time. Workers and supervisors never see it, and the server refuses its routes to them (403).

## Features delivered

| Section | What it shows | Data source and definition |
| --- | --- | --- |
| Overview | Active ASHA workers; territories with a worker; households and beneficiaries registered; confirmed visits; households and beneficiaries visited; households without an assigned worker; visits by type; follow-ups | `users`, `territory_assignments`, `households`, `people`, `v2_visits`. "Visited" means at least one **confirmed** visit in the date range. Follow-ups come from each person's **latest** confirmed visit: "upcoming" (next-visit date today or later) and "date passed, no later visit recorded". Calendar days are IST |
| ASHA workers | Name, username, territories, households assigned, households and beneficiaries visited, confirmed visits, upcoming follow-ups, most recent visit. Click a worker for a detail view with their activity history | Worker accounts only. Nobody is labelled inactive or underperforming |
| Visit activity | Date and time, worker, territory, household and person **public IDs**, visit type, "Confirmed vN", follow-up date, demo alert flag count | `v2_visits`. No names, weights, transcripts or audio. Filter by type, sort newest or oldest, page by 25 |
| Territories | Per territory: assigned workers, registered vs visited vs not-visited households, last recorded visit, a chip per household | Pins are **registration locations**. The page says that visits are not GPS-inferred |
| Assignments | Assign a worker to a territory; **Move** with an explicit confirmation (transactional); **End**; current list and history | Existing `POST /admin/assignments` and `/end`, plus the new `/reassign` |
| Audit history | The latest 100 events with time, action, actor and resource kind | `audit_events` |

**Filters:** date from/to (it validates from ≤ to), territory and worker. Every tab has a loading skeleton, an empty state and an error state with Retry. A 401 hands control back to the login screen.

**Not added:** a separate "Households" page, and map markers on the territory view. Households are covered by the register counts and the per-territory chips. A MapLibre coverage map can reuse `HouseholdMap` later. Nothing on the dashboard is a placeholder.

## Assignment management

- **Schema:** `territory_assignments` (`ends_at` instead of deletion; a partial unique index on active rows). No migration was needed.
- **Reassign:**
  1. locks the row `FOR UPDATE`;
  2. refuses an assignment that has already ended (409), the same territory (409), an unknown territory or assignment (404), an admin target (422) and unknown fields (422);
  3. ends the old assignment and inserts the new one in **one transaction**;
  4. audits `assignment.reassign` with the actor and the from/to territories.
- **Visits keep their owner** (asserted), and no beneficiary record moves.
- **Workers can't change their own assignment:** the routes return 403 for workers and supervisors (asserted in pytest and in the browser).
- **Effect on live sessions:** a live voice session of a moved worker is ended by the existing periodic revalidation (Phase 5 behaviour).

## Results

| Suite | Result |
| --- | --- |
| `backend/tests/test_admin_dashboard.py` (disposable PostGIS) | **15 passed** |
| `e2e/phase7_admin.py` (disposable `asha_saathi_e2e`, hermetic browser) | **75 passed, 0 failed** |
| Widths 320, 360, 390, 768, 1024 and 1280 px, overview plus 5 tabs each | no horizontal overflow (36 checks) |
| axe-core WCAG 2.2 A/AA: overview, worker detail, coverage, reassign dialog | 0 serious or critical violations |
| Access: worker and supervisor see no dashboard; 7 admin GETs and the reassign POST return 403; anonymous gets 401 | pass |
| Move worker B to DEMO-A (Cancel first, then confirm), DB plus audit actor check, move back, history keeps both ended rows | pass |

**Bug found and fixed:** confirmation dialogs stretched to the full viewport height, because the `.v2` `min-height: 100%` rule matched the dialog. This also affected the Phase 6 leave-visit dialog. Fixed in `0a77ce2`, with a regression check.

**Screenshots:** `data/e2e/phase7/` (git-ignored; synthetic data only).
