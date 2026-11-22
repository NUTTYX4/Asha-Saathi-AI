import type {
  AdminAssignment,
  AdminOverview,
  AdminTerritoryCoverage,
  AdminUser,
  AdminVisitPage,
  AdminWorker,
  AssignmentCreate,
  AuditOut,
  ReassignRequest,
  TerritoryOut,
  AshaSaathiContracts,
  HouseholdDetail,
  HouseholdPin,
  LoginRequest,
  MeOut,
  NearbyHousehold,
  PersonOut,
  V2VisitOut,
} from "../types/contracts";

export type V2ClientEvent = AshaSaathiContracts["v2_client_event"];

/**
 * Authenticated V2 API (same origin; Vite proxies /api). The session is an httpOnly cookie, so
 * no token is ever visible to this code. Unsafe requests carry the anti-CSRF header the backend
 * requires. Nothing here stores responses beyond the caller's React state.
 */
const CSRF = { "X-Requested-With": "asha-saathi" };
const NEXT_PAGE_HEADER = "X-Next-After";
const MAX_PAGES = 20; // 20 x 100 pins: far beyond any single worker's area

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** status 0 = the request never reached the server (offline, proxy down). */
export function isUnauthorized(e: unknown): boolean {
  return e instanceof ApiError && e.status === 401;
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      cache: "no-store",
      ...init,
      headers: { Accept: "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check the connection and try again.");
  }
  if (!response.ok) {
    let message = `Request failed (HTTP ${response.status})`;
    try {
      const body: unknown = await response.json();
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === "string") message = detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, message);
  }
  return response;
}

async function getJson<T>(path: string): Promise<T> {
  return (await (await send(path)).json()) as T;
}

async function postJson<T>(path: string, body?: unknown): Promise<T | undefined> {
  const response = await send(path, {
    method: "POST",
    headers: { ...CSRF, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return response.status === 204 ? undefined : ((await response.json()) as T);
}

const seg = encodeURIComponent;

export const apiV2 = {
  me: () => getJson<MeOut>("/api/v2/auth/me"),
  login: async (body: LoginRequest) => (await postJson<MeOut>("/api/v2/auth/login", body)) as MeOut,
  logout: async () => {
    await postJson<void>("/api/v2/auth/logout");
  },

  /** Every pin the caller may see (optionally matching `q`), following the page cursor. */
  async households(q?: string): Promise<HouseholdPin[]> {
    const pins: HouseholdPin[] = [];
    let after: string | null = null;
    for (let page = 0; page < MAX_PAGES; page++) {
      const params = new URLSearchParams({ limit: "100" });
      if (q) params.set("q", q);
      if (after) params.set("after", after);
      const response = await send(`/api/v2/households?${params}`);
      pins.push(...((await response.json()) as HouseholdPin[]));
      after = response.headers.get(NEXT_PAGE_HEADER);
      if (!after) break;
    }
    return pins;
  },

  /** Suggestions near a GPS fix. The coordinates are sent once and not kept. */
  nearby: (lat: number, lon: number, radiusM: number) =>
    getJson<NearbyHousehold[]>(
      `/api/v2/households/nearby?${new URLSearchParams({
        lat: lat.toFixed(6),
        lon: lon.toFixed(6),
        radius_m: String(Math.round(radiusM)),
        limit: "20",
      })}`,
    ),

  household: (id: string) => getJson<HouseholdDetail>(`/api/v2/households/${seg(id)}`),
  members: (householdId: string) => getJson<PersonOut[]>(`/api/v2/households/${seg(householdId)}/members`),
  /** Server recheck that this person is an active member of this household. */
  member: (householdId: string, personId: string) =>
    getJson<PersonOut>(`/api/v2/households/${seg(householdId)}/members/${seg(personId)}`),
  /** Every confirmed visit the caller may see for this person, newest first. */
  async personVisits(personId: string): Promise<V2VisitOut[]> {
    const visits: V2VisitOut[] = [];
    let before: string | null = null;
    for (let page = 0; page < MAX_PAGES; page++) {
      const params = new URLSearchParams({ limit: "50" });
      if (before) params.set("before", before);
      const chunk = await getJson<V2VisitOut[]>(`/api/v2/people/${seg(personId)}/visits?${params}`);
      visits.push(...chunk);
      if (chunk.length < 50) break;
      const last = chunk[chunk.length - 1];
      if (!last || last.id === before) break;
      before = last.id;
    }
    return visits;
  },
  visitReceipt: (clientVisitId: string) =>
    getJson<V2VisitOut>(`/api/v2/visits/by-client-key/${seg(clientVisitId)}`),

  /** Admin dashboard (admin role only; the server enforces it on every call). */
  admin: {
    overview: (f: AdminFilter) => getJson<AdminOverview>(`/api/v2/admin/overview?${filterParams(f)}`),
    workers: (f: AdminFilter) => getJson<AdminWorker[]>(`/api/v2/admin/workers?${filterParams(f)}`),
    visits: (f: AdminFilter, opts: { visitType?: string; sort?: "newest" | "oldest"; limit?: number; offset?: number }) => {
      const params = filterParams(f);
      if (opts.visitType) params.set("visit_type", opts.visitType);
      params.set("sort", opts.sort ?? "newest");
      params.set("limit", String(opts.limit ?? 25));
      params.set("offset", String(opts.offset ?? 0));
      return getJson<AdminVisitPage>(`/api/v2/admin/visits?${params}`);
    },
    coverage: (f: AdminFilter) => getJson<AdminTerritoryCoverage[]>(`/api/v2/admin/coverage?${filterParams(f)}`),
    users: () => getJson<AdminUser[]>("/api/v2/admin/users"),
    territories: () => getJson<TerritoryOut[]>("/api/v2/territories"),
    assignments: () => getJson<AdminAssignment[]>("/api/v2/admin/assignments"),
    audit: (limit = 100) => getJson<AuditOut[]>(`/api/v2/admin/audit?limit=${limit}`),
    assign: async (body: AssignmentCreate) => postJson<unknown>("/api/v2/admin/assignments", body),
    endAssignment: async (id: string) => postJson<unknown>(`/api/v2/admin/assignments/${seg(id)}/end`),
    reassign: async (id: string, body: ReassignRequest) =>
      (await postJson<AdminAssignment>(`/api/v2/admin/assignments/${seg(id)}/reassign`, body)) as AdminAssignment,
  },
};

export interface AdminFilter {
  dateFrom?: string;
  dateTo?: string;
  territoryId?: string;
  workerId?: string;
}

function filterParams(f: AdminFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (f.dateFrom) params.set("date_from", f.dateFrom);
  if (f.dateTo) params.set("date_to", f.dateTo);
  if (f.territoryId) params.set("territory_id", f.territoryId);
  if (f.workerId) params.set("worker_id", f.workerId);
  return params;
}

export function v2SessionSocketUrl(): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/ws/v2/session`;
}
