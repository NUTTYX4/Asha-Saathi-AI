import { ChevronLeft, ChevronRight, CircleCheck, Droplets, House, MapPin, Toilet, UserRound, Users } from "lucide-react";
import { forwardRef, type ReactNode, useState } from "react";

import type { HouseholdDetail, HouseholdPin, PersonOut } from "../../../types/contracts";
import { Badge, Button, Sheet } from "../../ui/primitives";
import { VisitHistory } from "../../visits/components/VisitHistory";
import { VoiceVisitPanel } from "../../voice/v2/VoiceVisitPanel";
import { activeProgrammes, ageLabel, codeLabel, relationshipLine } from "../labels";
import type { Selection } from "../selection";

/** One sentence that states exactly what is (and is not) confirmed. Read by screen readers. */
export function SelectionBreadcrumb({ selection }: { selection: Selection }) {
  let household = "No household";
  let member = "No member";
  if (selection.phase === "household_preview") household = `${selection.candidate.public_id} (not confirmed)`;
  if (selection.phase !== "none" && selection.phase !== "household_preview") household = selection.household.public_id;
  if (selection.phase === "person_preview") member = `${selection.candidate.full_name} (not selected)`;
  if (selection.phase === "person_confirmed") member = selection.person.full_name;
  return (
    <p data-testid="selection-breadcrumb">
      Selected: {household} / {member}
    </p>
  );
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter((p) => p && p.toLowerCase() !== "of");
  return ((parts[0]?.[0] ?? "") + (parts[parts.length - 1]?.[0] ?? "")).toUpperCase();
}

function Avatar({ name, size = "md" }: { name: string; size?: "md" | "lg" }) {
  return (
    <span
      aria-hidden="true"
      data-initials={initials(name)}
      className={`v2-avatar grid shrink-0 place-items-center rounded-full bg-berry-100 font-extrabold text-berry-700 ${
        size === "lg" ? "size-14 text-lg" : "size-11 text-sm"
      }`}
    />
  );
}

function Facts({ children }: { children: ReactNode }) {
  return <dl className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-4 gap-y-2 text-sm">{children}</dl>;
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-fg-2">{term}</dt>
      <dd className="min-w-0 font-semibold break-words">{children}</dd>
    </>
  );
}

// ---------------------------------------------------------------- 1. household candidate
interface PreviewProps {
  candidate: HouseholdPin;
  confirming: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** A pin, list row, search result or GPS suggestion only makes a candidate. No member data here. */
export const HouseholdPreviewSheet = forwardRef<HTMLHeadingElement, PreviewProps>(function HouseholdPreviewSheet(
  { candidate, confirming, onConfirm, onCancel },
  headingRef,
) {
  return (
    <Sheet testId="household-preview" labelledBy="selection-heading">
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <span className="grid size-12 shrink-0 place-items-center rounded-md bg-berry-50 text-berry-600">
            <House size={24} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 id="selection-heading" ref={headingRef} tabIndex={-1} className="text-2xl leading-tight font-extrabold">
              {candidate.public_id}
            </h2>
            <Badge tone="warning" className="mt-1">
              Candidate, not confirmed
            </Badge>
          </div>
        </div>
        <Facts>
          <Fact term="Label">{candidate.label}</Fact>
          <Fact term="Members">{candidate.member_count}</Fact>
          <Fact term="Territory">{candidate.territory_code}</Fact>
          <Fact term="Pin">{candidate.landmark ?? "Synthetic demo location"}</Fact>
        </Facts>
        <p className="text-sm text-fg-2">
          Check the household ID with the family. Members are shown only after you confirm.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row-reverse">
          <Button block icon={<CircleCheck size={20} />} onClick={onConfirm} disabled={confirming}>
            {confirming ? "Checking…" : "Confirm household"}
          </Button>
          <Button block variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </Sheet>
  );
});

// ---------------------------------------------------------------- 2. confirmed household
interface HouseholdProps {
  household: HouseholdDetail;
  members: PersonOut[];
  candidateId: string | null;
  selectedId: string | null;
  candidate: PersonOut | null;
  confirmingPerson: boolean;
  onBack: () => void;
  onChangeHousehold: () => void;
  onPreviewPerson: (personId: string) => void;
  onSelectPerson: () => void;
  onCancelPerson: () => void;
}

export const HouseholdScreen = forwardRef<HTMLHeadingElement, HouseholdProps>(function HouseholdScreen(
  {
    household,
    members,
    candidateId,
    selectedId,
    candidate,
    confirmingPerson,
    onBack,
    onChangeHousehold,
    onPreviewPerson,
    onSelectPerson,
    onCancelPerson,
  },
  headingRef,
) {
  const survey = household.latest_survey;
  return (
    <section
      aria-labelledby="selection-heading"
      data-testid="household-confirmed"
      className={`flex flex-col gap-4 ${candidate ? "pb-[26rem] lg:pb-0" : ""}`}
    >
      <Button variant="ghost" size="md" icon={<ChevronLeft size={20} />} onClick={onBack} className="self-start lg:hidden">
        All households
      </Button>

      <header className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="selection-heading" ref={headingRef} tabIndex={-1} className="text-2xl leading-tight font-extrabold">
              Household {household.public_id}
            </h2>
            <p className="mt-0.5 text-sm text-fg-2">{household.label}</p>
          </div>
          <Badge tone="success" icon={<CircleCheck size={14} />}>
            Confirmed
          </Badge>
        </div>
        <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-fg-2">
          <li className="inline-flex items-center gap-1.5">
            <Users size={16} aria-hidden="true" /> {household.member_count} members
          </li>
          <li className="inline-flex items-center gap-1.5">
            <MapPin size={16} aria-hidden="true" /> {household.territory_code}
          </li>
          {survey && (
            <li className="inline-flex items-center gap-1.5">
              <Droplets size={16} aria-hidden="true" /> Water: {codeLabel(survey.drinking_water_source)}
            </li>
          )}
          {survey && survey.has_toilet !== null && (
            <li className="inline-flex items-center gap-1.5">
              <Toilet size={16} aria-hidden="true" /> {survey.has_toilet ? "Toilet at home" : "No toilet at home"}
            </li>
          )}
        </ul>
        <Button variant="outline" size="md" onClick={onChangeHousehold} className="self-start">
          Change household
        </Button>
      </header>

      <div className="flex flex-col gap-2">
        <h3 className="px-1 text-lg font-extrabold">
          <span lang="kn">ಸದಸ್ಯರು</span> <span className="text-fg-2">Members ({members.length})</span>
        </h3>
        <ul
          aria-label={`Members of ${household.public_id}`}
          className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface"
        >
          {members.map((m) => {
            const isCandidate = m.id === candidateId;
            const isSelected = m.id === selectedId;
            const programmes = activeProgrammes(m);
            return (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => onPreviewPerson(m.id)}
                  aria-pressed={isCandidate || isSelected}
                  data-member={m.public_id}
                  className={`flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 ${
                    isSelected ? "bg-lime-100" : isCandidate ? "bg-berry-50" : "hover:bg-neutral-50"
                  }`}
                >
                  <Avatar name={m.full_name} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span data-name className="font-bold break-words">
                      {m.full_name}
                    </span>
                    <span className="text-sm text-fg-2">
                      {codeLabel(m.relationship_to_head)}, {ageLabel(m.age)}
                    </span>
                    {programmes.length > 0 && (
                      <span className="mt-1 flex flex-wrap gap-1">
                        {programmes.map((p) => (
                          <Badge key={p} tone="brand">
                            {p}
                          </Badge>
                        ))}
                      </span>
                    )}
                  </span>
                  {isSelected ? (
                    <Badge tone="accent" icon={<CircleCheck size={14} />}>
                      Selected
                    </Badge>
                  ) : (
                    <ChevronRight size={20} aria-hidden="true" className="shrink-0 text-fg-3" />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {candidate && (
        <Sheet testId="member-preview" labelledBy="member-preview-heading">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Avatar name={candidate.full_name} size="lg" />
              <div className="min-w-0">
                <h3 id="member-preview-heading" className="text-xl leading-tight font-extrabold break-words">
                  {candidate.full_name}
                </h3>
                <p className="text-sm text-fg-2">
                  {candidate.public_id}, not selected yet
                </p>
              </div>
            </div>
            <MemberFacts person={candidate} />
            <div className="flex flex-col gap-2 sm:flex-row-reverse">
              <Button block icon={<UserRound size={20} />} onClick={onSelectPerson} disabled={confirmingPerson}>
                {confirmingPerson ? "Checking…" : "Select member"}
              </Button>
              <Button block variant="ghost" onClick={onCancelPerson}>
                Back
              </Button>
            </div>
          </div>
        </Sheet>
      )}
    </section>
  );
});

function MemberFacts({ person }: { person: PersonOut }) {
  const programmes = activeProgrammes(person);
  return (
    <Facts>
      <Fact term="Relationship">{codeLabel(person.relationship_to_head)} (to head)</Fact>
      <Fact term="Sex">{codeLabel(person.sex)}</Fact>
      <Fact term="Age">{ageLabel(person.age)}</Fact>
      <Fact term="Programmes">{programmes.length ? programmes.join(", ") : "None recorded"}</Fact>
      {person.relationships.length > 0 && (
        <Fact term="Family">{person.relationships.map(relationshipLine).join("; ")}</Fact>
      )}
    </Facts>
  );
}

// ---------------------------------------------------------------- 3. selected member and visit
interface MemberProps {
  household: HouseholdDetail;
  person: PersonOut;
  canRecord: boolean;
  onBack: () => void;
  onChangeMember: () => void;
  onSessionLost: () => void;
  onVoiceActiveChange: (active: boolean) => void;
}

export const MemberScreen = forwardRef<HTMLHeadingElement, MemberProps>(function MemberScreen(
  { household, person, canRecord, onBack, onChangeMember, onSessionLost, onVoiceActiveChange },
  headingRef,
) {
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const refreshHistory = () => setHistoryRefreshKey((k) => k + 1);
  const programmes = activeProgrammes(person);

  return (
    <div className="flex flex-col gap-5">
      <Button variant="ghost" size="md" icon={<ChevronLeft size={20} />} onClick={onBack} className="self-start lg:hidden">
        Members of {household.public_id}
      </Button>

      <section
        aria-labelledby="selection-heading"
        data-testid="member-selected"
        className="flex flex-col gap-3 rounded-xl border border-berry-200 bg-berry-50 p-4"
      >
        <div className="flex items-start gap-3">
          <Avatar name={person.full_name} size="lg" />
          <div className="min-w-0 flex-1">
            <h2 id="selection-heading" ref={headingRef} tabIndex={-1} className="text-2xl leading-tight font-extrabold break-words">
              {person.full_name}
            </h2>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-fg-2">
              <span className="font-bold text-fg">{person.public_id}</span>
              <span>Household {household.public_id}</span>
              <Badge tone="accent" icon={<CircleCheck size={14} />}>
                Selected
              </Badge>
            </p>
          </div>
        </div>
        <p className="text-sm">
          {codeLabel(person.relationship_to_head)} (to head), {codeLabel(person.sex)}, {ageLabel(person.age)}
        </p>
        {programmes.length > 0 && (
          <p className="flex flex-wrap gap-1.5">
            {programmes.map((p) => (
              <Badge key={p} tone="brand">
                {p}
              </Badge>
            ))}
          </p>
        )}
        {person.relationships.length > 0 && (
          <p className="text-sm text-fg-2">Family: {person.relationships.map(relationshipLine).join("; ")}</p>
        )}
        <Button variant="ghost" size="md" onClick={onChangeMember} className="self-start">
          Change member
        </Button>
      </section>

      <VoiceVisitPanel
        key={person.id}
        household={household}
        person={person}
        canRecord={canRecord}
        onSessionLost={onSessionLost}
        onVisitSaved={refreshHistory}
        onCheckHistory={refreshHistory}
        onActiveChange={onVoiceActiveChange}
      />

      <VisitHistory person={person} refreshKey={historyRefreshKey} onSessionLost={onSessionLost} />
    </div>
  );
});
