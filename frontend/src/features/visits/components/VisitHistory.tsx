import { CalendarDays, ChevronDown, CircleAlert, CircleCheck, RefreshCw, Scale } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiV2, isUnauthorized } from "../../../lib/apiV2";
import { formatDate } from "../../../lib/labels";
import type { PersonOut, V2VisitOut } from "../../../types/contracts";
import { Badge, Button, Notice } from "../../ui/primitives";
import {
  filterVisitsForPerson,
  formatVaccinations,
  toggleExpandedVisit,
  visitTypeDisplay,
} from "../visitHistory";

interface Props {
  person: PersonOut;
  refreshKey: number;
  onSessionLost: () => void;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

/** Confirmed visits of the selected person, newest first, straight from PostgreSQL. */
export function VisitHistory({ person, refreshKey, onSessionLost }: Props) {
  const [visits, setVisits] = useState<V2VisitOut[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());
  const requestSeqRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    const expectedId = person.id;
    const expectedPublicId = person.public_id;
    setLoading(true);
    setError(null);
    try {
      const data = await apiV2.personVisits(expectedId);
      if (!mountedRef.current || requestSeqRef.current !== seq) return;
      setVisits(filterVisitsForPerson(data, expectedPublicId));
    } catch (err) {
      if (!mountedRef.current || requestSeqRef.current !== seq) return;
      if (isUnauthorized(err)) {
        onSessionLost();
        return;
      }
      setError(err instanceof ApiError ? err.message : "Could not load confirmed visits.");
    } finally {
      if (mountedRef.current && requestSeqRef.current === seq) {
        setLoading(false);
      }
    }
  }, [onSessionLost, person.id, person.public_id]);

  useEffect(() => {
    setVisits(null);
    setExpandedIds(new Set());
  }, [person.id]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const count = visits?.length ?? 0;

  return (
    <section aria-labelledby="history-heading" data-testid="visit-history" className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h3 id="history-heading" className="flex flex-col text-xl leading-tight font-extrabold">
            <span lang="kn">ಭೇಟಿ ಇತಿಹಾಸ</span>
            <span className="text-base text-fg-2">
              Visit history{visits !== null && ` (${count})`}
            </span>
          </h3>
          <p className="text-sm break-words text-fg-2">
            Confirmed visits for {person.full_name} ({person.public_id})
          </p>
        </div>
        <Button
          variant="ghost"
          size="md"
          onClick={() => void load()}
          disabled={loading}
          aria-label="Refresh visit history"
          icon={<RefreshCw size={18} className={loading ? "animate-spin" : ""} />}
        >
          {loading ? "Refreshing" : "Refresh"}
        </Button>
      </div>

      {error && (
        <Notice tone="error" icon={<CircleAlert size={20} />} role="alert" title="Visit history did not load">
          <p>{error}</p>
          <Button variant="outline" size="md" className="mt-2" onClick={() => void load()}>
            Retry
          </Button>
        </Notice>
      )}

      {visits === null && !error ? (
        <div aria-busy="true" className="flex flex-col gap-2">
          <p className="sr-only">Loading confirmed visits</p>
          <div className="h-20 animate-pulse rounded-lg bg-sunken" />
          <div className="h-20 animate-pulse rounded-lg bg-sunken opacity-70" />
        </div>
      ) : visits && visits.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-neutral-300 bg-surface px-4 py-6 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-berry-50 text-berry-600">
            <CalendarDays size={24} aria-hidden="true" />
          </span>
          <p className="font-bold">No confirmed visits yet</p>
          <p lang="kn" className="text-sm text-fg-2">
            ಇನ್ನೂ ದೃಢಪಡಿಸಿದ ಭೇಟಿಗಳಿಲ್ಲ
          </p>
          <p className="max-w-xs text-sm text-fg-2">A visit appears here as soon as you confirm and save it.</p>
        </div>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
          {visits?.map((v) => {
            const typeLabel = visitTypeDisplay(v.visit_type);
            const expanded = expandedIds.has(v.id);
            const detailsId = `visit-details-${v.id}`;
            const vaccines = formatVaccinations(v.vaccinations_due);
            const when = new Date(v.confirmed_at);
            const valid = !Number.isNaN(when.getTime());

            return (
              <li key={v.id} data-testid="history-item" className="min-w-0">
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={detailsId}
                  data-testid="history-item-toggle"
                  onClick={() => setExpandedIds((prev) => toggleExpandedVisit(prev, v.id))}
                  className="flex w-full items-start gap-3 px-4 py-3.5 text-left hover:bg-neutral-50"
                >
                  <span
                    aria-hidden="true"
                    className="flex w-12 shrink-0 flex-col items-center rounded-md bg-berry-50 py-1.5 text-berry-700"
                  >
                    <span className="text-lg leading-none font-extrabold">{valid ? when.getDate() : "–"}</span>
                    <span className="text-xs font-bold">
                      {valid ? when.toLocaleDateString("en-IN", { month: "short" }) : ""}
                    </span>
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-bold break-words">{typeLabel.en}</span>
                      <Badge tone="success" icon={<CircleCheck size={14} />} data-testid="history-save-status">
                        Saved
                      </Badge>
                      {v.danger_signs.length > 0 && (
                        <Badge tone="error" icon={<CircleAlert size={14} />}>
                          Danger flags ({v.danger_signs.length})
                        </Badge>
                      )}
                    </span>
                    <span className="text-sm break-words text-fg-2">
                      {formatDateTime(v.confirmed_at)}, {person.full_name} ({v.person_public_id})
                    </span>
                    <span className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                      <span className="inline-flex items-center gap-1">
                        <Scale size={16} aria-hidden="true" className="text-fg-3" />
                        {v.weight_kg !== null ? `${v.weight_kg} kg` : "Weight not recorded"}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <CalendarDays size={16} aria-hidden="true" className="text-fg-3" />
                        Follow-up {formatDate(v.next_visit_date)}
                      </span>
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1 self-center text-sm font-bold text-berry-600">
                    <span className="hidden sm:inline">{expanded ? "Hide" : "Details"}</span>
                    <span className="sr-only sm:hidden">{expanded ? "Hide details" : "Show details"}</span>
                    <ChevronDown
                      size={20}
                      aria-hidden="true"
                      className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
                    />
                  </span>
                </button>

                {expanded && (
                  <div id={detailsId} data-testid="history-item-details" className="bg-neutral-25 px-4 pt-1 pb-4">
                    <dl className="grid grid-cols-[minmax(6.5rem,auto)_1fr] gap-x-4 gap-y-2 text-sm">
                      <dt className="text-fg-2">Member</dt>
                      <dd className="min-w-0 font-semibold break-words">
                        {person.full_name} ({v.person_public_id})
                      </dd>
                      <dt className="text-fg-2">Household</dt>
                      <dd className="min-w-0 break-words">{v.household_public_id}</dd>
                      <dt className="text-fg-2">Visit type</dt>
                      <dd className="min-w-0 break-words">
                        <span lang="kn">{typeLabel.kn}</span> ({typeLabel.en})
                      </dd>
                      <dt className="text-fg-2">Status</dt>
                      <dd className="min-w-0 font-semibold break-words text-success-700">
                        Saved and confirmed (version {v.record_version})
                      </dd>
                      <dt className="text-fg-2">Confirmed</dt>
                      <dd className="min-w-0 break-words">{formatDateTime(v.confirmed_at)}</dd>
                      <dt className="text-fg-2">Weight</dt>
                      <dd className="min-w-0 font-semibold">{v.weight_kg !== null ? `${v.weight_kg} kg` : "Not recorded"}</dd>
                      <dt className="text-fg-2">Follow-up</dt>
                      <dd className="min-w-0">{formatDate(v.next_visit_date)}</dd>
                      <dt className="text-fg-2">Vaccinations</dt>
                      <dd className="min-w-0 break-words">{vaccines}</dd>
                      <dt className={v.danger_signs.length > 0 ? "font-semibold text-error-700" : "text-fg-2"}>
                        Danger flags
                      </dt>
                      <dd className={`min-w-0 break-words ${v.danger_signs.length > 0 ? "text-error-700" : ""}`}>
                        {v.danger_signs.length > 0 ? (
                          <>
                            {v.danger_signs.join(", ")}
                            <span className="mt-1 block text-xs font-bold">Demo only: pending clinical review</span>
                          </>
                        ) : (
                          "None"
                        )}
                      </dd>
                      {v.requires_phc_referral && (
                        <>
                          <dt className="font-semibold text-error-700">PHC referral</dt>
                          <dd className="min-w-0 font-semibold break-words text-error-700">Flagged (demo rule)</dd>
                        </>
                      )}
                      <dt className="text-fg-2">Recorded by</dt>
                      <dd className="min-w-0 break-words text-fg-2">{v.recorded_by}</dd>
                      <dt className="text-fg-2">Visit ID</dt>
                      <dd className="min-w-0 break-words text-fg-2">{v.id.slice(0, 8)}</dd>
                    </dl>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
