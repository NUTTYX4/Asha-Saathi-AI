import {
  ArrowLeftRight,
  CalendarDays,
  CircleAlert,
  ClipboardList,
  History,
  Home,
  LayoutDashboard,
  MapPinned,
  RefreshCw,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type AdminFilter, ApiError, apiV2, isUnauthorized } from "../../lib/apiV2";
import { formatDate } from "../../lib/labels";
import type {
  AdminAssignment,
  AdminTerritoryCoverage,
  AdminUser,
  AdminVisitPage,
  AdminWorker,
  AuditOut,
  TerritoryOut,
  VisitType,
} from "../../types/contracts";
import { Badge, Button, ConfirmDialog, Notice } from "../ui/primitives";
import { visitTypeDisplay } from "../visits/visitHistory";

type Tab = "overview" | "workers" | "visits" | "coverage" | "assignments" | "audit";

const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard size={18} /> },
  { id: "workers", label: "ASHA workers", icon: <Users size={18} /> },
  { id: "visits", label: "Visit activity", icon: <ClipboardList size={18} /> },
  { id: "coverage", label: "Territories", icon: <MapPinned size={18} /> },
  { id: "assignments", label: "Assignments", icon: <ArrowLeftRight size={18} /> },
  { id: "audit", label: "Audit history", icon: <History size={18} /> },
];

const VISIT_TYPES = ["routine", "ANC", "PNC", "newborn", "immunisation", "unknown"];

function dateTime(iso: string | null | undefined): string {
  if (!iso) return "No visits yet";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function typeLabel(t: string): string {
  return visitTypeDisplay(t as VisitType).en;
}

/** Loads with the given loader whenever `key` changes; 401 hands control back to the login screen. */
function useLoad<T>(loader: () => Promise<T>, key: string, onSessionLost: (n: string) => void) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  const seq = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loaderRef.current();
      if (mine === seq.current) setState({ data, error: null, loading: false });
    } catch (e) {
      if (mine !== seq.current) return;
      if (isUnauthorized(e)) {
        onSessionLost("Your session has ended. Please sign in again.");
        return;
      }
      setState({ data: null, error: e instanceof ApiError ? e.message : "Could not load this view.", loading: false });
    }
  }, [onSessionLost]);
  useEffect(() => {
    void load();
  }, [load, key]);
  return { ...state, reload: load };
}

function LoadState({ loading, error, onRetry, children }: { loading: boolean; error: string | null; onRetry: () => void; children: ReactNode }) {
  if (error)
    return (
      <Notice tone="error" icon={<CircleAlert size={20} />} role="alert" title="This view did not load">
        <p>{error}</p>
        <Button variant="outline" size="md" className="mt-2" onClick={onRetry}>
          Retry
        </Button>
      </Notice>
    );
  if (loading)
    return (
      <div aria-busy="true" className="flex flex-col gap-2">
        <p className="sr-only">Loading</p>
        <div className="h-24 animate-pulse rounded-lg bg-sunken" />
        <div className="h-24 animate-pulse rounded-lg bg-sunken opacity-70" />
      </div>
    );
  return <>{children}</>;
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-neutral-300 bg-surface px-4 py-6 text-center">
      <p className="font-bold">{title}</p>
      <p className="mt-1 text-sm text-fg-2">{body}</p>
    </div>
  );
}

function Metric({ label, value, hint, testId }: { label: string; value: number | string; hint?: string; testId?: string }) {
  return (
    <div data-testid={testId} className="flex min-w-0 flex-col gap-1 rounded-lg border border-line bg-surface p-4">
      <span className="text-sm font-semibold text-fg-2">{label}</span>
      <span className="text-3xl leading-none font-extrabold tabular-nums">{value}</span>
      {hint && <span className="text-xs text-fg-3">{hint}</span>}
    </div>
  );
}

const fieldClass =
  "min-h-11 w-full rounded-md border border-control bg-surface px-3 text-base text-fg focus-visible:border-berry-600";

/** Admin dashboard: activity and coverage from confirmed records, plus assignment management. */
export function AdminDashboard({ onSessionLost }: { onSessionLost: (notice: string) => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [filter, setFilter] = useState<AdminFilter>({});
  const [selectedWorker, setSelectedWorker] = useState<AdminWorker | null>(null);
  const filterKey = JSON.stringify(filter);

  const lookups = useLoad(
    async () => {
      const [users, territories] = await Promise.all([apiV2.admin.users(), apiV2.admin.territories()]);
      return { users, territories };
    },
    "lookups",
    onSessionLost,
  );
  const workers = useMemo(() => (lookups.data?.users ?? []).filter((u) => u.role === "worker"), [lookups.data]);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6" data-testid="admin-dashboard">
      <div>
        <h2 className="flex flex-col text-2xl leading-tight font-extrabold">
          <span lang="kn">ನಿರ್ವಾಹಕ ಫಲಕ</span>
          <span className="text-base text-fg-2">Admin dashboard</span>
        </h2>
        <p className="text-sm text-fg-2">Counts come from confirmed visit records and the household register. Synthetic data.</p>
      </div>

      <nav aria-label="Dashboard sections" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <ul className="flex w-max gap-1 rounded-lg bg-sunken p-1">
          {TABS.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                aria-current={tab === t.id ? "page" : undefined}
                onClick={() => {
                  setTab(t.id);
                  setSelectedWorker(null);
                }}
                className={`flex min-h-11 items-center gap-2 rounded-md px-3 text-sm font-bold whitespace-nowrap ${
                  tab === t.id ? "bg-surface text-berry-700 shadow-xs" : "text-fg-2 hover:text-fg"
                }`}
              >
                <span aria-hidden="true">{t.icon}</span>
                {t.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {tab !== "assignments" && tab !== "audit" && (
        <FilterBar filter={filter} onChange={setFilter} territories={lookups.data?.territories ?? []} workers={workers} />
      )}

      {tab === "overview" && <OverviewTab filter={filter} filterKey={filterKey} onSessionLost={onSessionLost} />}
      {tab === "workers" &&
        (selectedWorker ? (
          <WorkerDetail worker={selectedWorker} filter={filter} onBack={() => setSelectedWorker(null)} onSessionLost={onSessionLost} />
        ) : (
          <WorkersTab filter={filter} filterKey={filterKey} onOpen={setSelectedWorker} onSessionLost={onSessionLost} />
        ))}
      {tab === "visits" && <VisitsTab filter={filter} filterKey={filterKey} onSessionLost={onSessionLost} />}
      {tab === "coverage" && <CoverageTab filter={filter} filterKey={filterKey} onSessionLost={onSessionLost} />}
      {tab === "assignments" && (
        <AssignmentsTab users={lookups.data?.users ?? []} territories={lookups.data?.territories ?? []} onSessionLost={onSessionLost} />
      )}
      {tab === "audit" && <AuditTab users={lookups.data?.users ?? []} onSessionLost={onSessionLost} />}
    </div>
  );
}

function FilterBar({
  filter,
  onChange,
  territories,
  workers,
}: {
  filter: AdminFilter;
  onChange: (f: AdminFilter) => void;
  territories: TerritoryOut[];
  workers: AdminUser[];
}) {
  const invalid = Boolean(filter.dateFrom && filter.dateTo && filter.dateFrom > filter.dateTo);
  return (
    <section aria-label="Filters" className="grid grid-cols-1 gap-3 rounded-lg border border-line bg-surface p-3 min-[380px]:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1fr_auto] [&>label:nth-of-type(n+3)]:min-[380px]:max-lg:col-span-2 [&>div]:min-[380px]:max-lg:col-span-2">
      <label className="flex flex-col gap-1 text-sm font-semibold">
        From
        <input type="date" className={fieldClass} value={filter.dateFrom ?? ""} onChange={(e) => onChange({ ...filter, dateFrom: e.target.value || undefined })} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        To
        <input type="date" className={fieldClass} value={filter.dateTo ?? ""} onChange={(e) => onChange({ ...filter, dateTo: e.target.value || undefined })} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Territory
        <select className={fieldClass} value={filter.territoryId ?? ""} onChange={(e) => onChange({ ...filter, territoryId: e.target.value || undefined })}>
          <option value="">All territories</option>
          {territories.map((t) => (
            <option key={t.id} value={t.id}>
              {t.code}: {t.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        ASHA worker
        <select className={fieldClass} value={filter.workerId ?? ""} onChange={(e) => onChange({ ...filter, workerId: e.target.value || undefined })}>
          <option value="">All workers</option>
          {workers.map((w) => (
            <option key={w.id} value={w.id}>
              {w.display_name}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-end">
        <Button variant="ghost" size="md" block onClick={() => onChange({})}>
          Clear filters
        </Button>
      </div>
      {invalid && (
        <p role="alert" className="text-sm font-bold text-error-700 sm:col-span-2 lg:col-span-5">
          "From" must be on or before "To".
        </p>
      )}
    </section>
  );
}

function OverviewTab({ filter, filterKey, onSessionLost }: { filter: AdminFilter; filterKey: string; onSessionLost: (n: string) => void }) {
  const { data, loading, error, reload } = useLoad(() => apiV2.admin.overview(filter), filterKey, onSessionLost);
  const types = data ? Object.entries(data.visits_by_type) : [];
  const maxType = Math.max(1, ...types.map(([, n]) => n));
  return (
    <LoadState loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="flex flex-col gap-4" data-testid="admin-overview">
          <section aria-label="Register" className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-4">
            <Metric testId="m-workers" label="Active ASHA workers" value={data.active_workers} />
            <Metric label="Territories with a worker" value={`${data.territories_with_worker} of ${data.territories_total}`} />
            <Metric testId="m-households" label="Households registered" value={data.households_registered} hint="On the register (not a visit count)" />
            <Metric label="Beneficiaries registered" value={data.beneficiaries_registered} />
          </section>
          <section aria-label="Visits in the selected range" className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-4">
            <Metric testId="m-visits" label="Confirmed visits" value={data.visits_confirmed} />
            <Metric testId="m-hh-visited" label="Households visited" value={data.households_visited} hint="At least one confirmed visit in range" />
            <Metric label="Beneficiaries visited" value={data.beneficiaries_visited} hint="Distinct people visited in range" />
            <Metric label="Households without an assigned worker" value={data.households_without_assigned_worker} />
          </section>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <section aria-labelledby="by-type" className="rounded-lg border border-line bg-surface p-4">
              <h3 id="by-type" className="font-extrabold">
                Visits by type
              </h3>
              {types.length === 0 ? (
                <p className="mt-2 text-sm text-fg-2">No confirmed visits in this range.</p>
              ) : (
                <ul className="mt-3 flex flex-col gap-2">
                  {types.map(([t, n]) => (
                    <li key={t} className="grid grid-cols-[7.5rem_1fr_2.5rem] items-center gap-2 text-sm">
                      <span className="font-semibold">{typeLabel(t)}</span>
                      <span className="h-3 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
                        <span className="block h-full rounded-full bg-berry-500" style={{ width: `${(n / maxType) * 100}%` }} />
                      </span>
                      <span className="text-right font-bold tabular-nums">{n}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section aria-labelledby="followups" className="rounded-lg border border-line bg-surface p-4">
              <h3 id="followups" className="flex items-center gap-2 font-extrabold">
                <CalendarDays size={18} aria-hidden="true" /> Follow-ups
              </h3>
              <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 text-sm">
                <dt className="text-fg-2">Upcoming next-visit dates</dt>
                <dd className="text-right text-lg font-extrabold tabular-nums" data-testid="m-followups">
                  {data.followups_upcoming}
                </dd>
                <dt className="text-fg-2">Next-visit date passed, no later visit recorded</dt>
                <dd className="text-right text-lg font-extrabold tabular-nums">{data.followups_date_passed}</dd>
              </dl>
              <p className="mt-2 text-xs text-fg-3">From each person's latest confirmed visit. Dates are in India Standard Time.</p>
            </section>
          </div>
        </div>
      )}
    </LoadState>
  );
}

function WorkersTab({ filter, filterKey, onOpen, onSessionLost }: { filter: AdminFilter; filterKey: string; onOpen: (w: AdminWorker) => void; onSessionLost: (n: string) => void }) {
  const { data, loading, error, reload } = useLoad(() => apiV2.admin.workers(filter), filterKey, onSessionLost);
  return (
    <LoadState loading={loading} error={error} onRetry={reload}>
      {data && data.length === 0 ? (
        <Empty title="No ASHA workers match" body="Clear the filters to see every worker." />
      ) : (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2" aria-label="ASHA workers" data-testid="admin-workers">
          {data?.map((w) => (
            <li key={w.id}>
              <button
                type="button"
                data-worker={w.username}
                onClick={() => onOpen(w)}
                className="flex w-full flex-col gap-3 rounded-lg border border-line bg-surface p-4 text-left hover:border-berry-300"
              >
                <span className="flex flex-wrap items-center justify-between gap-2">
                  <span className="min-w-0">
                    <span className="block font-extrabold break-words">{w.display_name}</span>
                    <span className="block text-sm text-fg-2">{w.username}</span>
                  </span>
                  <span className="flex flex-wrap gap-1">
                    {w.territories.length ? (
                      w.territories.map((t) => (
                        <Badge key={t.id} tone="brand">
                          {t.code}
                        </Badge>
                      ))
                    ) : (
                      <Badge tone="warning">No territory assigned</Badge>
                    )}
                    {!w.active && <Badge tone="neutral">Account disabled</Badge>}
                  </span>
                </span>
                <span className="grid grid-cols-2 gap-2 text-sm min-[420px]:grid-cols-4">
                  <Stat label="Households assigned" value={w.households_assigned} />
                  <Stat label="Households visited" value={w.households_visited} />
                  <Stat label="Confirmed visits" value={w.visits_confirmed} />
                  <Stat label="Upcoming follow-ups" value={w.followups_upcoming} />
                </span>
                <span className="text-sm text-fg-2">Most recent visit: {dateTime(w.last_visit_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </LoadState>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <span className="flex flex-col rounded-md bg-sunken px-2 py-1.5">
      <span className="text-lg leading-tight font-extrabold tabular-nums">{value}</span>
      <span className="text-xs text-fg-2">{label}</span>
    </span>
  );
}

function WorkerDetail({ worker, filter, onBack, onSessionLost }: { worker: AdminWorker; filter: AdminFilter; onBack: () => void; onSessionLost: (n: string) => void }) {
  return (
    <section aria-labelledby="worker-detail-heading" className="flex flex-col gap-3" data-testid="admin-worker-detail">
      <div>
        <Button variant="ghost" size="md" onClick={onBack}>
          Back to all workers
        </Button>
      </div>
      <div className="rounded-lg border border-line bg-surface p-4">
        <h3 id="worker-detail-heading" className="text-xl font-extrabold">
          {worker.display_name}
        </h3>
        <p className="text-sm text-fg-2">
          {worker.username} · {worker.territories.map((t) => `${t.code}: ${t.name}`).join(", ") || "No territory assigned"}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <Stat label="Households assigned" value={worker.households_assigned} />
          <Stat label="Households visited" value={worker.households_visited} />
          <Stat label="Beneficiaries visited" value={worker.beneficiaries_visited} />
          <Stat label="Confirmed visits" value={worker.visits_confirmed} />
        </div>
      </div>
      <h4 className="font-extrabold">Activity history</h4>
      <VisitsTab filter={{ ...filter, workerId: worker.id }} filterKey={`${JSON.stringify(filter)}:${worker.id}`} onSessionLost={onSessionLost} compact />
    </section>
  );
}

function VisitsTab({ filter, filterKey, onSessionLost, compact = false }: { filter: AdminFilter; filterKey: string; onSessionLost: (n: string) => void; compact?: boolean }) {
  const [visitType, setVisitType] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [offset, setOffset] = useState(0);
  const limit = 25;
  useEffect(() => setOffset(0), [filterKey, visitType, sort]);
  const { data, loading, error, reload } = useLoad<AdminVisitPage>(
    () => apiV2.admin.visits(filter, { visitType: visitType || undefined, sort, limit, offset }),
    `${filterKey}|${visitType}|${sort}|${offset}`,
    onSessionLost,
  );
  return (
    <div className="flex flex-col gap-3" data-testid="admin-visits">
      {!compact && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:max-w-xl">
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Visit type
            <select className={fieldClass} value={visitType} onChange={(e) => setVisitType(e.target.value)}>
              <option value="">All types</option>
              {VISIT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {typeLabel(t)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Order
            <select className={fieldClass} value={sort} onChange={(e) => setSort(e.target.value as "newest" | "oldest")}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </label>
        </div>
      )}
      <LoadState loading={loading} error={error} onRetry={reload}>
        {data && data.total === 0 ? (
          <Empty title="No confirmed visits" body="Nothing matches these filters yet." />
        ) : (
          data && (
            <>
              <p className="text-sm text-fg-2" role="status">
                Showing {data.offset + 1}–{data.offset + data.items.length} of {data.total} confirmed visits
              </p>
              <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface" aria-label="Confirmed visits">
                {data.items.map((v) => (
                  <li key={v.id} data-testid="admin-visit-row" className="grid grid-cols-1 gap-1 px-4 py-3 text-sm sm:grid-cols-[11rem_1fr_auto] sm:items-center sm:gap-4">
                    <span className="font-bold">{dateTime(v.confirmed_at)}</span>
                    <span className="min-w-0 break-words">
                      <span className="font-semibold">{typeLabel(v.visit_type)}</span> · {v.household_public_id} / {v.person_public_id} · {v.territory_code} ·{" "}
                      {v.worker_display_name}
                      {v.next_visit_date && <span className="text-fg-2"> · follow-up {formatDate(v.next_visit_date)}</span>}
                    </span>
                    <span className="flex flex-wrap gap-1">
                      <Badge tone="success">Confirmed v{v.record_version}</Badge>
                      {v.danger_sign_count > 0 && <Badge tone="error">Demo alert flags: {v.danger_sign_count}</Badge>}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2">
                <Button variant="outline" size="md" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
                  Previous
                </Button>
                <Button variant="outline" size="md" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>
                  Next
                </Button>
              </div>
            </>
          )
        )}
      </LoadState>
    </div>
  );
}

function CoverageTab({ filter, filterKey, onSessionLost }: { filter: AdminFilter; filterKey: string; onSessionLost: (n: string) => void }) {
  const { data, loading, error, reload } = useLoad<AdminTerritoryCoverage[]>(() => apiV2.admin.coverage(filter), filterKey, onSessionLost);
  return (
    <LoadState loading={loading} error={error} onRetry={reload}>
      <p className="text-sm text-fg-2">
        "Visited" means at least one confirmed visit in the selected range. Pins are registration locations, not visit GPS.
      </p>
      {data && data.length === 0 ? (
        <Empty title="No territories match" body="Clear the filters to see every territory." />
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2" data-testid="admin-coverage">
          {data?.map((t) => (
            <section key={t.id} aria-labelledby={`cov-${t.id}`} className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 id={`cov-${t.id}`} className="font-extrabold">
                    {t.code}: {t.name}
                  </h3>
                  <p className="text-sm text-fg-2">Workers: {t.workers.join(", ") || "none assigned"}</p>
                </div>
                {!t.active && <Badge tone="neutral">Inactive</Badge>}
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <Stat label="Registered" value={t.households_registered} />
                <Stat label="Visited" value={t.households_visited} />
                <Stat label="Not visited" value={t.households_not_visited} />
              </div>
              <p className="text-sm text-fg-2">Last recorded visit: {dateTime(t.last_visit_at)}</p>
              <ul className="flex flex-wrap gap-1.5" aria-label={`Households in ${t.code}`}>
                {t.households.map((h) => (
                  <li key={h.id}>
                    <span
                      title={h.last_visit_at ? `Last visit ${dateTime(h.last_visit_at)}` : "No confirmed visit"}
                      className={`inline-flex min-h-8 items-center gap-1 rounded-md px-2 text-xs font-bold ${
                        h.visited_in_range ? "bg-success-50 text-success-700" : "bg-sunken text-fg-2"
                      }`}
                    >
                      <Home size={12} aria-hidden="true" />
                      {h.public_id}
                      <span className="sr-only">{h.visited_in_range ? ", visited in range" : ", not visited in range"}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </LoadState>
  );
}

type Pending =
  | { kind: "end"; a: AdminAssignment }
  | { kind: "reassign"; a: AdminAssignment; territory: TerritoryOut }
  | { kind: "assign"; user: AdminUser; territory: TerritoryOut };

function AssignmentsTab({ users, territories, onSessionLost }: { users: AdminUser[]; territories: TerritoryOut[]; onSessionLost: (n: string) => void }) {
  const [version, setVersion] = useState(0);
  const { data, loading, error, reload } = useLoad(() => apiV2.admin.assignments(), String(version), onSessionLost);
  const [pending, setPending] = useState<Pending | null>(null);
  const [result, setResult] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [moveTo, setMoveTo] = useState<Record<string, string>>({});
  const [newUser, setNewUser] = useState("");
  const [newTerritory, setNewTerritory] = useState("");
  const assignable = users.filter((u) => u.role !== "admin" && u.active);
  const active = (data ?? []).filter((a) => !a.ends_at);
  const ended = (data ?? []).filter((a) => a.ends_at);

  async function run() {
    if (!pending) return;
    const p = pending;
    setPending(null);
    try {
      if (p.kind === "end") await apiV2.admin.endAssignment(p.a.id);
      if (p.kind === "reassign") await apiV2.admin.reassign(p.a.id, { territory_id: p.territory.id });
      if (p.kind === "assign") await apiV2.admin.assign({ user_id: p.user.id, territory_id: p.territory.id });
      setResult({
        tone: "success",
        text:
          p.kind === "end"
            ? `Ended ${p.a.display_name}'s assignment to ${p.a.territory_code}.`
            : p.kind === "reassign"
              ? `${p.a.display_name} moved from ${p.a.territory_code} to ${p.territory.code}.`
              : `${p.user.display_name} assigned to ${p.territory.code}.`,
      });
      setNewUser("");
      setNewTerritory("");
    } catch (e) {
      if (isUnauthorized(e)) return onSessionLost("Your session has ended. Please sign in again.");
      setResult({ tone: "error", text: e instanceof ApiError ? e.message : "The change was not saved." });
    }
    setVersion((v) => v + 1);
  }

  const dialog = pending
    ? pending.kind === "end"
      ? {
          title: "End this assignment?",
          body: `${pending.a.display_name} will immediately lose access to ${pending.a.territory_code}. Their recorded visits stay unchanged.`,
          confirm: "End assignment",
        }
      : pending.kind === "reassign"
        ? {
            title: `Move ${pending.a.display_name}?`,
            body: `Access to ${pending.a.territory_code} ends and access to ${pending.territory.code} starts, in one step. Visits already recorded stay with this worker; no household or beneficiary record moves.`,
            confirm: `Move to ${pending.territory.code}`,
          }
        : {
            title: `Assign ${pending.user.display_name}?`,
            body: `${pending.user.display_name} will be able to see and record visits in ${pending.territory.code}.`,
            confirm: "Assign",
          }
    : null;

  const selectedUser = assignable.find((u) => u.id === newUser);
  const selectedTerritory = territories.find((t) => t.id === newTerritory);

  return (
    <div className="flex flex-col gap-4" data-testid="admin-assignments">
      {result && (
        <Notice tone={result.tone} icon={result.tone === "success" ? <RefreshCw size={20} /> : <XCircle size={20} />} role="status">
          <p>{result.text}</p>
        </Notice>
      )}
      <section aria-labelledby="assign-new" className="rounded-lg border border-line bg-surface p-4">
        <h3 id="assign-new" className="flex items-center gap-2 font-extrabold">
          <UserPlus size={18} aria-hidden="true" /> Assign a worker to a territory
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Worker
            <select className={fieldClass} value={newUser} onChange={(e) => setNewUser(e.target.value)}>
              <option value="">Choose a worker</option>
              {assignable.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name} ({u.role})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Territory
            <select className={fieldClass} value={newTerritory} onChange={(e) => setNewTerritory(e.target.value)}>
              <option value="">Choose a territory</option>
              {territories.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.code}: {t.name}
                </option>
              ))}
            </select>
          </label>
          <Button
            size="md"
            disabled={!selectedUser || !selectedTerritory}
            onClick={() => selectedUser && selectedTerritory && setPending({ kind: "assign", user: selectedUser, territory: selectedTerritory })}
          >
            Assign
          </Button>
        </div>
      </section>

      <LoadState loading={loading} error={error} onRetry={reload}>
        <section aria-labelledby="current-assignments" className="flex flex-col gap-2">
          <h3 id="current-assignments" className="font-extrabold">
            Current assignments ({active.length})
          </h3>
          {active.length === 0 ? (
            <Empty title="No active assignments" body="Assign a worker above." />
          ) : (
            <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
              {active.map((a) => {
                const others = territories.filter((t) => t.id !== a.territory_id);
                const target = territories.find((t) => t.id === moveTo[a.id]);
                return (
                  <li key={a.id} data-assignment={a.username} className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-end lg:justify-between">
                    <div className="min-w-0">
                      <p className="font-bold break-words">
                        {a.display_name} <span className="font-normal text-fg-2">({a.role})</span>
                      </p>
                      <p className="text-sm text-fg-2">
                        {a.territory_code}: {a.territory_name} · since {dateTime(a.starts_at)}
                      </p>
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(10rem,1fr)_auto_auto] sm:items-end">
                      <label className="flex flex-col gap-1 text-sm font-semibold">
                        Move to
                        <select className={fieldClass} value={moveTo[a.id] ?? ""} onChange={(e) => setMoveTo({ ...moveTo, [a.id]: e.target.value })}>
                          <option value="">Choose territory</option>
                          {others.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.code}
                            </option>
                          ))}
                        </select>
                      </label>
                      <Button variant="outline" size="md" disabled={!target} onClick={() => target && setPending({ kind: "reassign", a, territory: target })}>
                        Move
                      </Button>
                      <Button variant="danger" size="md" onClick={() => setPending({ kind: "end", a })}>
                        End
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <section aria-labelledby="ended-assignments" className="flex flex-col gap-2">
          <h3 id="ended-assignments" className="font-extrabold">
            Assignment history ({ended.length})
          </h3>
          {ended.length === 0 ? (
            <p className="text-sm text-fg-2">No ended assignments.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface text-sm">
              {ended.map((a) => (
                <li key={a.id} className="px-4 py-2.5 break-words">
                  <span className="font-semibold">{a.display_name}</span> · {a.territory_code} · {dateTime(a.starts_at)} to {dateTime(a.ends_at)}
                  {a.created_by_username && <span className="text-fg-2"> · by {a.created_by_username}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </LoadState>

      <ConfirmDialog
        open={dialog !== null}
        title={dialog?.title ?? ""}
        body={dialog?.body ?? ""}
        confirmLabel={dialog?.confirm ?? "Confirm"}
        cancelLabel="Cancel"
        onConfirm={() => void run()}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}

function AuditTab({ users, onSessionLost }: { users: AdminUser[]; onSessionLost: (n: string) => void }) {
  const { data, loading, error, reload } = useLoad<AuditOut[]>(() => apiV2.admin.audit(100), "audit", onSessionLost);
  const names = useMemo(() => new Map(users.map((u) => [u.id, u.username])), [users]);
  return (
    <LoadState loading={loading} error={error} onRetry={reload}>
      {data && data.length === 0 ? (
        <Empty title="No audit events yet" body="Sign-ins, record access and admin changes appear here." />
      ) : (
        <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface text-sm" aria-label="Audit events" data-testid="admin-audit">
          {data?.map((e) => (
            <li key={e.id} className="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[11rem_12rem_1fr] sm:gap-3">
              <span className="font-semibold">{dateTime(e.occurred_at)}</span>
              <span className="font-bold break-words">{e.action}</span>
              <span className="min-w-0 break-words text-fg-2">
                {e.actor_user_id ? names.get(e.actor_user_id) ?? "unknown user" : "system / anonymous"} · {e.resource_kind}
              </span>
            </li>
          ))}
        </ul>
      )}
    </LoadState>
  );
}
