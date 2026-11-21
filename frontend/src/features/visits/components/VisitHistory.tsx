import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiV2, isUnauthorized } from "../../../lib/apiV2";
import { formatDate } from "../../../lib/labels";
import type { PersonOut, V2VisitOut } from "../../../types/contracts";
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
    <section
      aria-labelledby="history-heading"
      data-testid="visit-history"
      className="mt-3 flex flex-col gap-2 rounded-xl border-2 border-rule bg-paper p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 id="history-heading" className="font-display text-sm font-bold text-ink">
            Visit History / ಭೇಟಿ ಇತಿಹಾಸ {visits !== null ? `(${count})` : ""}
          </h3>
          <p className="text-xs text-ink-soft break-words">
            {person.full_name} ({person.public_id})
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          aria-label="Refresh visit history"
          className="min-h-10 rounded-lg border border-rule bg-sheet px-3 text-xs font-semibold text-ink disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-alarm-wash px-3 py-2 text-xs text-alarm"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void load()}
            className="min-h-10 rounded-lg border border-alarm px-2.5 font-semibold"
          >
            Retry
          </button>
        </div>
      )}

      {visits === null && !error ? (
        <p className="text-xs text-ink-soft">Loading confirmed visits…</p>
      ) : visits && visits.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule bg-sheet px-3 py-3 text-xs text-ink-soft">
          No confirmed visits yet · ಇನ್ನೂ ದೃಢಪಡಿಸಿದ ಭೇಟಿಗಳಿಲ್ಲ
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {visits?.map((v) => {
            const typeLabel = visitTypeDisplay(v.visit_type);
            const expanded = expandedIds.has(v.id);
            const detailsId = `visit-details-${v.id}`;
            const vaccines = formatVaccinations(v.vaccinations_due);

            return (
              <li
                key={v.id}
                data-testid="history-item"
                className="min-w-0 rounded-xl border border-rule bg-sheet px-3 py-2.5 text-xs"
              >
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={detailsId}
                  data-testid="history-item-toggle"
                  onClick={() => setExpandedIds((prev) => toggleExpandedVisit(prev, v.id))}
                  className="flex min-h-12 w-full flex-col gap-1.5 text-left"
                >
                  <div className="flex w-full flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-ink break-words">
                      {typeLabel.kn} · {typeLabel.en}
                    </span>
                    <span
                      data-testid="history-save-status"
                      className="rounded-full bg-leaf/15 px-2 py-0.5 text-[11px] font-semibold text-leaf"
                    >
                      Saved · Confirmed
                    </span>
                  </div>

                  <div className="flex w-full flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 text-ink-soft">
                    <span>{formatDateTime(v.confirmed_at)}</span>
                    <span className="break-words">
                      {person.full_name} ({v.person_public_id})
                    </span>
                  </div>

                  <div className="flex w-full flex-wrap items-center justify-between gap-2 pt-0.5">
                    <span className="text-ink break-words">
                      Weight: {v.weight_kg !== null ? `${v.weight_kg} kg` : "—"} · Follow-up:{" "}
                      {formatDate(v.next_visit_date)}
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      {v.danger_signs.length > 0 && (
                        <span className="rounded-full bg-alarm-wash px-2 py-0.5 text-[11px] font-semibold text-alarm">
                          Danger flags ({v.danger_signs.length})
                        </span>
                      )}
                      <span className="font-semibold text-ink">
                        {expanded ? "Hide details" : "View details"}
                      </span>
                    </div>
                  </div>
                </button>

                {expanded && (
                  <div
                    id={detailsId}
                    data-testid="history-item-details"
                    className="mt-2 border-t border-rule pt-2"
                  >
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                      <dt className="text-ink-soft">Member</dt>
                      <dd className="min-w-0 font-medium text-ink break-words">
                        {person.full_name} ({v.person_public_id})
                      </dd>
                      <dt className="text-ink-soft">Household</dt>
                      <dd className="min-w-0 text-ink break-words">{v.household_public_id}</dd>
                      <dt className="text-ink-soft">Visit type</dt>
                      <dd className="min-w-0 text-ink break-words">
                        {typeLabel.kn} · {typeLabel.en}
                      </dd>
                      <dt className="text-ink-soft">Save status</dt>
                      <dd className="min-w-0 font-semibold text-leaf break-words">
                        Saved · Confirmed (v{v.record_version})
                      </dd>
                      <dt className="text-ink-soft">Confirmed at</dt>
                      <dd className="min-w-0 text-ink break-words">{formatDateTime(v.confirmed_at)}</dd>
                      <dt className="text-ink-soft">Weight</dt>
                      <dd className="min-w-0 font-medium text-ink">
                        {v.weight_kg !== null ? `${v.weight_kg} kg` : "—"}
                      </dd>
                      <dt className="text-ink-soft">Follow-up</dt>
                      <dd className="min-w-0 text-ink">{formatDate(v.next_visit_date)}</dd>
                      <dt className="text-ink-soft">Vaccinations</dt>
                      <dd className="min-w-0 text-ink break-words">{vaccines}</dd>
                      <dt className={v.danger_signs.length > 0 ? "text-alarm" : "text-ink-soft"}>
                        Danger flags
                      </dt>
                      <dd
                        className={`min-w-0 break-words ${
                          v.danger_signs.length > 0 ? "text-alarm" : "text-ink"
                        }`}
                      >
                        {v.danger_signs.length > 0 ? (
                          <>
                            {v.danger_signs.join(", ")}{" "}
                            <span className="ml-1 inline-block rounded-full border border-alarm/30 bg-paper px-1.5 py-0.5 text-[10px] font-semibold">
                              Demo only · pending clinical review
                            </span>
                          </>
                        ) : (
                          "None"
                        )}
                      </dd>
                      {v.requires_phc_referral && (
                        <>
                          <dt className="text-alarm">PHC referral</dt>
                          <dd className="min-w-0 font-semibold text-alarm break-words">
                            PHC referral flagged (demo only)
                          </dd>
                        </>
                      )}
                      <dt className="text-ink-soft">Recorded by</dt>
                      <dd className="min-w-0 text-ink-soft break-words">{v.recorded_by}</dd>
                      <dt className="text-ink-soft">Visit ID</dt>
                      <dd className="min-w-0 text-ink-soft break-words">{v.id.slice(0, 8)}</dd>
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
