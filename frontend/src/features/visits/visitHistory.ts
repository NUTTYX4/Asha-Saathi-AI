import { VISIT_LABEL } from "../../lib/labels";
import type { V2VisitOut, VisitType } from "../../types/contracts";

function confirmedTimestampMs(iso: string): number {
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms;
}

/**
 * Keeps only confirmed visits belonging to `personPublicId`, deduplicated by visit ID
 * and ordered newest-first (`confirmed_at` descending, then `id` descending).
 */
export function filterVisitsForPerson(visits: V2VisitOut[], personPublicId: string): V2VisitOut[] {
  const seen = new Set<string>();
  const filtered: V2VisitOut[] = [];
  for (const visit of visits) {
    if (visit.person_public_id !== personPublicId || seen.has(visit.id)) continue;
    seen.add(visit.id);
    filtered.push(visit);
  }
  return filtered.sort((a, b) => {
    const diff = confirmedTimestampMs(b.confirmed_at) - confirmedTimestampMs(a.confirmed_at);
    if (diff !== 0) return diff;
    const isoCmp = b.confirmed_at.localeCompare(a.confirmed_at);
    return isoCmp !== 0 ? isoCmp : b.id.localeCompare(a.id);
  });
}

/** Returns a new Set with `visitId` expanded state toggled. */
export function toggleExpandedVisit(expandedIds: ReadonlySet<string>, visitId: string): Set<string> {
  const next = new Set(expandedIds);
  if (next.has(visitId)) {
    next.delete(visitId);
  } else {
    next.add(visitId);
  }
  return next;
}

/** Bilingual label for a visit type, falling back to raw code if unexpected. */
export function visitTypeDisplay(visitType: VisitType): { kn: string; en: string } {
  return VISIT_LABEL[visitType] ?? { kn: visitType, en: visitType };
}

/** Human-readable display for confirmed `vaccinations_due`. */
export function formatVaccinations(vaccinationsDue: string[] | null): string {
  if (vaccinationsDue === null) return "—";
  return vaccinationsDue.length > 0 ? vaccinationsDue.join(", ") : "None";
}
