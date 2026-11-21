import { describe, expect, it } from "vitest";

import type { HouseholdDetail, HouseholdPin, PersonOut } from "../../types/contracts";
import {
  confirmedHousehold,
  confirmedPerson,
  highlightedHouseholdId,
  initialSelection,
  type Selection,
  type SelectionAction,
  selectionReducer,
} from "./selection";

// Synthetic fixtures only (shapes match the API contracts).
function pin(n: number): HouseholdPin {
  return {
    id: `hh-${n}`,
    public_id: `H-00${n}`,
    label: `Demo House ${n}, Synthetic Lane A`,
    landmark: "Synthetic demo pin",
    territory_code: "DEMO-A",
    latitude: 12.97 + n / 1000,
    longitude: 77.59 + n / 1000,
    location_source: "synthetic_demo",
    member_count: 2,
    is_demo_data: true,
  };
}

function detail(n: number): HouseholdDetail {
  return { ...pin(n), latest_survey: null };
}

function person(id: string, household: number): PersonOut {
  return {
    id,
    public_id: `P-${id}`,
    household_public_id: `H-00${household}`,
    full_name: `Synthetic Person ${id}`,
    sex: "female",
    date_of_birth: null,
    age: { basis: "unknown" },
    relationship_to_head: "head",
    residence_status: "resident",
    programmes: [],
    relationships: [],
    is_demo_data: true,
  };
}

const run = (actions: SelectionAction[], from: Selection = initialSelection) => actions.reduce(selectionReducer, from);

const confirmH3: SelectionAction[] = [
  { type: "preview_household", pin: pin(3) },
  { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
  { type: "household_confirmed", household: detail(3), members: [person("a", 3), person("b", 3)], attempt: 1 },
];

describe("household preview", () => {
  it("a pin only makes a candidate: nothing is confirmed and no members are present", () => {
    const s = run([{ type: "preview_household", pin: pin(3) }]);
    expect(s.phase).toBe("household_preview");
    expect(confirmedHousehold(s)).toBeNull();
    expect(confirmedPerson(s)).toBeNull();
    expect("members" in s).toBe(false);
    expect(highlightedHouseholdId(s)).toBe("hh-3");
  });

  it("cancel returns to no selection", () => {
    expect(run([{ type: "preview_household", pin: pin(3) }, { type: "cancel_preview" }])).toEqual(initialSelection);
  });

  it("previewing another pin replaces the candidate", () => {
    const s = run([{ type: "preview_household", pin: pin(3) }, { type: "preview_household", pin: pin(4) }]);
    expect(s).toMatchObject({ phase: "household_preview", candidate: { id: "hh-4" } });
  });
});

describe("household confirmation", () => {
  it("requires the server recheck for the same household", () => {
    const s = run(confirmH3);
    expect(s.phase).toBe("household_confirmed");
    expect(confirmedHousehold(s)?.public_id).toBe("H-003");
    expect(confirmedPerson(s)).toBeNull();
  });

  it("ignores a late confirmation for a household the user has moved away from", () => {
    const s = run([
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
      { type: "preview_household", pin: pin(4) },
      { type: "household_confirmed", household: detail(3), members: [person("a", 3)], attempt: 1 },
    ]);
    expect(s).toMatchObject({ phase: "household_preview", candidate: { id: "hh-4" }, confirming: false });
  });

  it("cannot confirm without a preview", () => {
    const s = run([{ type: "household_confirmed", household: detail(3), members: [], attempt: 1 }]);
    expect(s).toEqual(initialSelection);
  });

  it("drops any member that does not belong to the confirmed household", () => {
    const s = run([
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
      { type: "household_confirmed", household: detail(3), members: [person("a", 3), person("x", 7)], attempt: 1 },
    ]);
    expect(s.phase === "household_confirmed" && s.members.map((m) => m.id)).toEqual(["a"]);
  });

  it("a refused recheck resets; a network failure keeps the candidate for retry", () => {
    const preview: SelectionAction[] = [
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
    ];
    expect(run([...preview, { type: "confirm_household_failed", householdId: "hh-3", retryable: false, attempt: 1 }])).toEqual(
      initialSelection,
    );
    expect(run([...preview, { type: "confirm_household_failed", householdId: "hh-3", retryable: true, attempt: 1 }])).toMatchObject({
      phase: "household_preview",
      confirming: false,
    });
  });
});

describe("member selection", () => {
  it("previews then selects a member of the confirmed household after the server recheck", () => {
    const s = run([
      ...confirmH3,
      { type: "preview_person", personId: "b" },
      { type: "confirm_person_started", personId: "b", attempt: 1 },
      { type: "person_confirmed", person: person("b", 3), attempt: 1 },
    ]);
    expect(confirmedPerson(s)?.id).toBe("b");
    expect(confirmedHousehold(s)?.id).toBe("hh-3");
  });

  it("a member preview is not a selection", () => {
    const s = run([...confirmH3, { type: "preview_person", personId: "a" }]);
    expect(s.phase).toBe("person_preview");
    expect(confirmedPerson(s)).toBeNull();
  });

  it("cannot preview someone who is not in the confirmed household", () => {
    const before = run(confirmH3);
    expect(run([{ type: "preview_person", personId: "x" }], before)).toBe(before);
  });

  it("cannot pick a member before the household is confirmed", () => {
    const s = run([{ type: "preview_household", pin: pin(3) }, { type: "preview_person", personId: "a" }]);
    expect(s.phase).toBe("household_preview");
  });

  it("rejects a server answer for a different person or household", () => {
    const previewA = run([
      ...confirmH3,
      { type: "preview_person", personId: "a" },
      { type: "confirm_person_started", personId: "a", attempt: 2 },
    ]);
    expect(run([{ type: "person_confirmed", person: person("b", 3), attempt: 2 }], previewA)).toBe(previewA);
    const wrongHouse = { ...person("a", 3), household_public_id: "H-007" };
    expect(run([{ type: "person_confirmed", person: wrongHouse, attempt: 2 }], previewA)).toBe(previewA);
  });

  it("a refused member recheck resets everything", () => {
    const s = run([
      ...confirmH3,
      { type: "preview_person", personId: "a" },
      { type: "confirm_person_started", personId: "a", attempt: 1 },
      { type: "confirm_person_failed", personId: "a", retryable: false, attempt: 1 },
    ]);
    expect(s).toEqual(initialSelection);
  });

  it("choosing another member clears the selected one", () => {
    const s = run([
      ...confirmH3,
      { type: "preview_person", personId: "a" },
      { type: "confirm_person_started", personId: "a", attempt: 1 },
      { type: "person_confirmed", person: person("a", 3), attempt: 1 },
      { type: "preview_person", personId: "b" },
    ]);
    expect(s).toMatchObject({ phase: "person_preview", candidate: { id: "b" } });
    expect(confirmedPerson(s)).toBeNull();
  });
});

describe("clearing", () => {
  const selected: SelectionAction[] = [
    ...confirmH3,
    { type: "preview_person", personId: "a" },
    { type: "confirm_person_started", personId: "a", attempt: 1 },
    { type: "person_confirmed", person: person("a", 3), attempt: 1 },
  ];

  it("picking a different household drops the member and needs a new confirmation", () => {
    const s = run([...selected, { type: "preview_household", pin: pin(4) }]);
    expect(s).toMatchObject({ phase: "household_preview", candidate: { id: "hh-4" } });
    expect(confirmedPerson(s)).toBeNull();
    expect(confirmedHousehold(s)).toBeNull();
  });

  it("re-picking the confirmed household keeps the selection", () => {
    const before = run(selected);
    expect(run([{ type: "preview_household", pin: pin(3) }], before)).toBe(before);
  });

  it.each(["reset", "change_household"] as const)("%s clears household and member", (type) => {
    expect(run([...selected, { type }])).toEqual(initialSelection);
  });

  it("change member keeps the confirmed household only", () => {
    const s = run([...selected, { type: "change_member" }]);
    expect(s.phase).toBe("household_confirmed");
    expect(confirmedPerson(s)).toBeNull();
  });
});

describe("late answers after leaving and returning (review finding)", () => {
  it("a household answer is ignored once the worker left and re-previewed the same household", () => {
    const s = run([
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
      { type: "cancel_preview" },
      { type: "preview_household", pin: pin(3) },
      { type: "household_confirmed", household: detail(3), members: [person("a", 3)], attempt: 1 },
    ]);
    expect(s).toMatchObject({ phase: "household_preview", confirming: false });
  });

  it("only the pending attempt is applied", () => {
    const s = run([
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
      { type: "preview_household", pin: pin(4) },
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 2 },
      { type: "household_confirmed", household: detail(3), members: [], attempt: 1 },
    ]);
    expect(s).toMatchObject({ phase: "household_preview", confirming: true, attempt: 2 });
    expect(run([{ type: "household_confirmed", household: detail(3), members: [], attempt: 2 }], s).phase).toBe(
      "household_confirmed",
    );
  });

  it("a member answer is ignored after switching away and back without pressing Select again", () => {
    const s = run([
      ...confirmH3,
      { type: "preview_person", personId: "a" },
      { type: "confirm_person_started", personId: "a", attempt: 5 },
      { type: "preview_person", personId: "b" },
      { type: "preview_person", personId: "a" },
      { type: "person_confirmed", person: person("a", 3), attempt: 5 },
    ]);
    expect(s).toMatchObject({ phase: "person_preview", confirming: false });
  });

  it("a stale failure does not reset a newer attempt", () => {
    const s = run([
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 1 },
      { type: "cancel_preview" },
      { type: "preview_household", pin: pin(3) },
      { type: "confirm_household_started", householdId: "hh-3", attempt: 2 },
      { type: "confirm_household_failed", householdId: "hh-3", retryable: false, attempt: 1 },
    ]);
    expect(s).toMatchObject({ phase: "household_preview", confirming: true, attempt: 2 });
  });
});
