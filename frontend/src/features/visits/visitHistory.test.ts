import { describe, expect, it } from "vitest";

import type { V2VisitOut, VisitType } from "../../types/contracts";
import {
  filterVisitsForPerson,
  formatVaccinations,
  toggleExpandedVisit,
  visitTypeDisplay,
} from "./visitHistory";

function makeVisit(overrides: Partial<V2VisitOut> = {}): V2VisitOut {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    client_visit_id: "22222222-2222-4222-8222-222222222222",
    person_public_id: "P-020",
    household_public_id: "H-005",
    recorded_by: "Demo ASHA Worker A",
    visit_type: "routine",
    subject_population: "unresolved",
    weight_kg: 55,
    vaccinations_due: null,
    next_visit_date: "2026-11-28",
    danger_signs: [],
    requires_phc_referral: false,
    rule_status: "demo_only_pending_clinical_review",
    ruleset_version: "rules-demo",
    extraction_source: "deterministic",
    record_version: 2,
    confirmed_at: "2026-11-21T20:31:39.489100Z",
    is_demo_data: true,
    ...overrides,
  };
}

describe("filterVisitsForPerson", () => {
  it("isolates records to the exact selected person and excludes mother/newborn/other entries", () => {
    const mother = makeVisit({ id: "v-mother", person_public_id: "P-010", visit_type: "PNC" });
    const newborn = makeVisit({ id: "v-baby", person_public_id: "P-011", visit_type: "newborn" });
    const selected = makeVisit({ id: "v-self", person_public_id: "P-020", visit_type: "routine" });

    const filtered = filterVisitsForPerson([mother, selected, newborn], "P-020");
    expect(filtered.map((v) => v.id)).toEqual(["v-self"]);
  });

  it("handles empty lists", () => {
    expect(filterVisitsForPerson([], "P-020")).toEqual([]);
  });

  it("deduplicates by id and orders newest-first by confirmed_at and id tie-break", () => {
    const older = makeVisit({
      id: "v-1",
      confirmed_at: "2026-11-20T10:00:00Z",
    });
    const newerA = makeVisit({
      id: "v-a",
      confirmed_at: "2026-11-21T20:31:39Z",
    });
    const newerB = makeVisit({
      id: "v-b",
      confirmed_at: "2026-11-21T20:31:39Z",
    });
    const dup = makeVisit({
      id: "v-a",
      confirmed_at: "2026-11-21T20:31:39Z",
    });

    const filtered = filterVisitsForPerson([older, newerA, dup, newerB], "P-020");
    expect(filtered.map((v) => v.id)).toEqual(["v-b", "v-a", "v-1"]);
  });
});

describe("toggleExpandedVisit", () => {
  it("toggles ids immutably", () => {
    const initial = new Set<string>(["v-1"]);
    const expanded = toggleExpandedVisit(initial, "v-2");
    expect(Array.from(expanded).sort()).toEqual(["v-1", "v-2"]);
    expect(Array.from(initial)).toEqual(["v-1"]);

    const collapsed = toggleExpandedVisit(expanded, "v-1");
    expect(Array.from(collapsed)).toEqual(["v-2"]);
  });
});

describe("visitTypeDisplay", () => {
  it("formats known visit types and falls back safely for unknown values", () => {
    expect(visitTypeDisplay("routine")).toEqual({ kn: "ಸಾಮಾನ್ಯ ಭೇಟಿ", en: "Routine / General Visit" });
    expect(visitTypeDisplay("newborn")).toEqual({ kn: "ನವಜಾತ ಶಿಶು", en: "Newborn" });
    expect(visitTypeDisplay("ANC")).toEqual({ kn: "ಗರ್ಭಿಣಿ ಭೇಟಿ", en: "ANC" });
    expect(visitTypeDisplay("PNC")).toEqual({ kn: "ಹೆರಿಗೆ ನಂತರ", en: "PNC" });
    expect(visitTypeDisplay("immunisation")).toEqual({ kn: "ಲಸಿಕೆ", en: "Immunisation" });
    expect(visitTypeDisplay("custom_type" as VisitType)).toEqual({ kn: "custom_type", en: "custom_type" });
  });
});

describe("formatVaccinations", () => {
  it("handles null, empty, and populated lists", () => {
    expect(formatVaccinations(null)).toBe("—");
    expect(formatVaccinations([])).toBe("None");
    expect(formatVaccinations(["BCG", "OPV-0"])).toBe("BCG, OPV-0");
  });
});
