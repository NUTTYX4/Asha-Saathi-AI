import { forwardRef, type ReactNode } from "react";

import type { PersonOut } from "../../../types/contracts";
import { activeProgrammes, ageLabel, codeLabel, relationshipLine } from "../labels";
import type { Selection } from "../selection";

interface Props {
  selection: Selection;
  onConfirmHousehold: () => void;
  onCancelPreview: () => void;
  onPreviewPerson: (personId: string) => void;
  onSelectPerson: () => void;
  onChangeMember: () => void;
  onChangeHousehold: () => void;
}

/** Breadcrumb that always shows exactly what is (and is not) confirmed. */
export function SelectionBreadcrumb({ selection }: { selection: Selection }) {
  let household = "No household";
  let member = "No member";
  if (selection.phase === "household_preview") household = `${selection.candidate.public_id} (not confirmed)`;
  if (selection.phase !== "none" && selection.phase !== "household_preview") household = selection.household.public_id;
  if (selection.phase === "person_preview") member = `${selection.candidate.full_name} (not selected)`;
  if (selection.phase === "person_confirmed") member = selection.person.full_name;
  return (
    <p data-testid="selection-breadcrumb" className="text-sm">
      <span className="font-semibold">Selected:</span> {household} / {member}
    </p>
  );
}

const button = "min-h-12 rounded-xl px-4 font-semibold disabled:opacity-60";

export const SelectionPanel = forwardRef<HTMLHeadingElement, Props>(function SelectionPanel(
  { selection, onConfirmHousehold, onCancelPreview, onPreviewPerson, onSelectPerson, onChangeMember, onChangeHousehold },
  headingRef,
) {
  if (selection.phase === "none") {
    return (
      <section aria-labelledby="selection-heading" className="rounded-2xl bg-sheet p-4">
        <h2 id="selection-heading" ref={headingRef} tabIndex={-1} className="font-display text-lg font-bold">
          Choose a household
        </h2>
        <p className="text-sm text-ink-soft">Pick a pin on the map, a household in the list, or search by ID.</p>
      </section>
    );
  }

  if (selection.phase === "household_preview") {
    const pin = selection.candidate;
    return (
      <section aria-labelledby="selection-heading" data-testid="household-preview" className="rounded-2xl border-2 border-rose bg-sheet p-4">
        <h2 id="selection-heading" ref={headingRef} tabIndex={-1} className="font-display text-lg font-bold">
          Candidate: {pin.public_id}
        </h2>
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-sm">
          <dt className="text-ink-soft">Label</dt>
          <dd>{pin.label}</dd>
          <dt className="text-ink-soft">Members</dt>
          <dd>{pin.member_count}</dd>
          <dt className="text-ink-soft">Territory</dt>
          <dd>{pin.territory_code}</dd>
          <dt className="text-ink-soft">Pin</dt>
          <dd>{pin.landmark ?? "Synthetic demo location"}</dd>
        </dl>
        <p className="mt-2 text-sm">Check this is the right household, then confirm to see its members.</p>
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={onConfirmHousehold} disabled={selection.confirming} className={`${button} flex-1 bg-ink text-white`}>
            {selection.confirming ? "Checking…" : "Confirm household"}
          </button>
          <button type="button" onClick={onCancelPreview} className={`${button} border border-ink`}>
            Cancel
          </button>
        </div>
      </section>
    );
  }

  const { household, members } = selection;
  const candidateId = selection.phase === "person_preview" ? selection.candidate.id : null;
  const selectedId = selection.phase === "person_confirmed" ? selection.person.id : null;
  return (
    <section aria-labelledby="selection-heading" data-testid="household-confirmed" className="flex flex-col gap-3 rounded-2xl border-2 border-leaf bg-sheet p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 id="selection-heading" ref={headingRef} tabIndex={-1} className="font-display text-lg font-bold">
            Household {household.public_id} <span className="text-sm font-semibold text-leaf">confirmed</span>
          </h2>
          <p className="text-xs text-ink-soft">
            {household.label} · {household.territory_code}
          </p>
        </div>
        <button type="button" onClick={onChangeHousehold} className="min-h-11 rounded-xl border border-ink px-3 text-sm font-semibold">
          Change household
        </button>
      </div>

      <div>
        <h3 className="text-sm font-semibold">Members ({members.length})</h3>
        <ul className="mt-1 flex flex-col gap-1" aria-label={`Members of ${household.public_id}`}>
          {members.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => onPreviewPerson(m.id)}
                aria-pressed={m.id === candidateId || m.id === selectedId}
                data-member={m.public_id}
                className={`flex min-h-12 w-full items-center justify-between gap-2 rounded-lg border px-3 py-1 text-left ${
                  m.id === selectedId ? "border-leaf bg-leaf/10" : m.id === candidateId ? "border-rose bg-rose/5" : "border-rule"
                }`}
              >
                <span className="flex flex-col">
                  <span className="font-semibold">{m.full_name}</span>
                  <span className="text-xs text-ink-soft">
                    {codeLabel(m.relationship_to_head)} · {ageLabel(m.age)}
                  </span>
                </span>
                <span className="flex flex-wrap justify-end gap-1">
                  {activeProgrammes(m).map((p) => (
                    <span key={p} className="rounded-full bg-paper px-2 py-0.5 text-xs">
                      {p}
                    </span>
                  ))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {selection.phase === "person_preview" && (
        <MemberCard person={selection.candidate}>
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={onSelectPerson} disabled={selection.confirming} className={`${button} flex-1 bg-ink text-white`}>
              {selection.confirming ? "Checking…" : "Select member"}
            </button>
            <button type="button" onClick={onCancelPreview} className={`${button} border border-ink`}>
              Back
            </button>
          </div>
        </MemberCard>
      )}

      {selection.phase === "person_confirmed" && (
        <MemberCard person={selection.person} selected>
          <p className="mt-2 rounded-xl bg-paper px-3 py-2 text-sm">
            Member selected. The voice visit for a selected member is the next phase and is not enabled here.
          </p>
          <button type="button" onClick={onChangeMember} className={`${button} mt-2 border border-ink`}>
            Change member
          </button>
        </MemberCard>
      )}
    </section>
  );
});

function MemberCard({ person, selected = false, children }: { person: PersonOut; selected?: boolean; children: ReactNode }) {
  const programmes = activeProgrammes(person);
  return (
    <div data-testid={selected ? "member-selected" : "member-preview"} className={`rounded-xl border-2 p-3 ${selected ? "border-leaf" : "border-rose"}`}>
      <h3 className="font-display text-base font-bold">
        {person.full_name} <span className="text-xs font-normal text-ink-soft">{person.public_id}</span>
        {selected && <span className="ml-2 text-sm font-semibold text-leaf">selected</span>}
      </h3>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-sm">
        <dt className="text-ink-soft">Relationship</dt>
        <dd>{codeLabel(person.relationship_to_head)} (to head)</dd>
        <dt className="text-ink-soft">Sex</dt>
        <dd>{codeLabel(person.sex)}</dd>
        <dt className="text-ink-soft">Age</dt>
        <dd>{ageLabel(person.age)}</dd>
        <dt className="text-ink-soft">Programmes</dt>
        <dd>{programmes.length ? programmes.join(", ") : "None recorded"}</dd>
        {person.relationships.length > 0 && (
          <>
            <dt className="text-ink-soft">Family</dt>
            <dd>{person.relationships.map(relationshipLine).join("; ")}</dd>
          </>
        )}
      </dl>
      {children}
    </div>
  );
}
