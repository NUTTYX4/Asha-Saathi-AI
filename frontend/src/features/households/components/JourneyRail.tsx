import { Check, Info } from "lucide-react";

import type { Selection } from "../selection";
import { SelectionBreadcrumb } from "./SelectionPanel";

export type Screen = "households" | "household" | "member";

interface Props {
  selection: Selection;
  screen: Screen;
  status: string;
  householdCount: number | null;
  onStep: (screen: Screen) => void;
}

/**
 * The visit journey: Households, then one confirmed Household, then one selected Member and the
 * visit. It always shows exactly what is confirmed (a preview is never shown as confirmed) and lets
 * the worker step back. Stepping away from a live voice visit asks first (see the workspace).
 */
export function JourneyRail({ selection, screen, status, householdCount, onStep }: Props) {
  const household =
    selection.phase === "household_confirmed" || selection.phase === "person_preview" || selection.phase === "person_confirmed"
      ? selection.household
      : null;
  const person = selection.phase === "person_confirmed" ? selection.person : null;
  const candidate = selection.phase === "household_preview" ? selection.candidate : null;

  const steps: { id: Screen; label: string; detail: string; done: boolean; enabled: boolean }[] = [
    {
      id: "households",
      label: "Households",
      detail: candidate ? `${candidate.public_id}?` : householdCount === null ? "Loading" : `${householdCount} homes`,
      done: household !== null,
      enabled: true,
    },
    {
      id: "household",
      label: "Household",
      detail: household ? household.public_id : "Not yet",
      done: household !== null,
      enabled: household !== null,
    },
    {
      id: "member",
      label: "Member",
      detail: person ? person.full_name : "Not yet",
      done: person !== null,
      enabled: person !== null,
    },
  ];

  return (
    <div className="sticky top-0 z-20 border-b border-line bg-canvas/95 backdrop-blur">
      <nav aria-label="Visit journey" className="mx-auto max-w-7xl px-3 pt-2.5 pb-2 sm:px-6">
        <ol className="grid grid-cols-3 gap-1.5">
          {steps.map((step, i) => {
            const current = step.id === screen;
            return (
              <li key={step.id} className="min-w-0">
                <button
                  type="button"
                  onClick={() => onStep(step.id)}
                  disabled={!step.enabled}
                  aria-current={current ? "step" : undefined}
                  className={`flex min-h-14 w-full min-w-0 flex-col items-center gap-0.5 rounded-md px-1 py-1.5 text-center transition-colors duration-150 disabled:cursor-default sm:flex-row sm:gap-2 sm:px-2 sm:text-left ${
                    current ? "bg-berry-100" : step.enabled ? "hover:bg-neutral-100" : ""
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`grid size-7 shrink-0 place-items-center rounded-full text-sm font-extrabold ${
                      step.done
                        ? "bg-lime-300 text-on-accent"
                        : current
                          ? "bg-berry-600 text-white"
                          : "border-2 border-neutral-300 text-fg-3"
                    }`}
                  >
                    {step.done ? <Check size={16} strokeWidth={3} /> : i + 1}
                  </span>
                  <span className="flex w-full min-w-0 flex-col">
                    <span className={`truncate text-sm font-extrabold ${current ? "text-berry-700" : step.enabled ? "text-fg" : "text-fg-3"}`}>
                      {step.label}
                    </span>
                    <span className="truncate text-xs text-fg-2">{step.detail}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <div className="sr-only">
          <SelectionBreadcrumb selection={selection} />
        </div>
        {/* Always present so screen readers announce every change. */}
        <p
          data-testid="status"
          aria-live="polite"
          className={`flex items-start gap-1.5 px-1 text-xs text-fg-2 ${status ? "mt-1.5" : ""}`}
        >
          {status && <Info size={14} aria-hidden="true" className="mt-px shrink-0" />}
          <span>{status}</span>
        </p>
      </nav>
    </div>
  );
}
