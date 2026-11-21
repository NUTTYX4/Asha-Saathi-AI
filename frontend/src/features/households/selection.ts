import type { HouseholdDetail, HouseholdPin, PersonOut } from "../../types/contracts";

/**
 * Household → member selection (V2 Phase 4). A pure reducer: no fetching, no timers.
 *
 *   none ──pin/list/search/nearby──▶ household_preview ──Confirm (server recheck)──▶ household_confirmed
 *   household_confirmed ──member──▶ person_preview ──Select (server recheck)──▶ person_confirmed
 *
 * - A pin, search result or GPS suggestion only makes a *candidate*. Members are never part of
 *   a preview; they arrive with the server-confirmed household.
 * - Choosing another household always drops the member. Logout, session loss or a refused
 *   recheck resets to `none`.
 * - Each confirmation attempt has a number; a response is applied only to the attempt that is
 *   still pending. A late answer for a household or person the user moved away from (even one
 *   they came back to and have not pressed Confirm on again) is ignored.
 */
export type Selection =
  | { phase: "none" }
  | { phase: "household_preview"; candidate: HouseholdPin; confirming: boolean; attempt: number | null }
  | { phase: "household_confirmed"; household: HouseholdDetail; members: PersonOut[] }
  | {
      phase: "person_preview";
      household: HouseholdDetail;
      members: PersonOut[];
      candidate: PersonOut;
      confirming: boolean;
      attempt: number | null;
    }
  | { phase: "person_confirmed"; household: HouseholdDetail; members: PersonOut[]; person: PersonOut };

export type SelectionAction =
  | { type: "preview_household"; pin: HouseholdPin }
  | { type: "confirm_household_started"; householdId: string; attempt: number }
  | { type: "household_confirmed"; household: HouseholdDetail; members: PersonOut[]; attempt: number }
  | { type: "confirm_household_failed"; householdId: string; retryable: boolean; attempt: number }
  | { type: "preview_person"; personId: string }
  | { type: "confirm_person_started"; personId: string; attempt: number }
  | { type: "person_confirmed"; person: PersonOut; attempt: number }
  | { type: "confirm_person_failed"; personId: string; retryable: boolean; attempt: number }
  | { type: "cancel_preview" }
  | { type: "change_member" }
  | { type: "change_household" }
  | { type: "reset" };

export const initialSelection: Selection = { phase: "none" };

type WithHousehold = Extract<Selection, { household: HouseholdDetail }>;

/** True only while this exact confirmation attempt is still pending. */
function pending(s: { confirming: boolean; attempt: number | null }, attempt: number): boolean {
  return s.confirming && s.attempt === attempt;
}

function hasHousehold(s: Selection): s is WithHousehold {
  return s.phase === "household_confirmed" || s.phase === "person_preview" || s.phase === "person_confirmed";
}

export function selectionReducer(state: Selection, action: SelectionAction): Selection {
  switch (action.type) {
    case "preview_household": {
      // Re-picking the household that is already confirmed keeps the current context.
      if (hasHousehold(state) && state.household.id === action.pin.id) return state;
      if (state.phase === "household_preview" && state.candidate.id === action.pin.id) return state;
      return { phase: "household_preview", candidate: action.pin, confirming: false, attempt: null };
    }
    case "confirm_household_started":
      if (state.phase !== "household_preview" || state.candidate.id !== action.householdId) return state;
      return { ...state, confirming: true, attempt: action.attempt };
    case "household_confirmed": {
      if (state.phase !== "household_preview" || !pending(state, action.attempt)) return state;
      if (state.candidate.id !== action.household.id) return state;
      const members = action.members.filter((m) => m.household_public_id === action.household.public_id);
      return { phase: "household_confirmed", household: action.household, members };
    }
    case "confirm_household_failed":
      if (state.phase !== "household_preview" || !pending(state, action.attempt)) return state;
      if (state.candidate.id !== action.householdId) return state;
      return action.retryable ? { ...state, confirming: false, attempt: null } : initialSelection;
    case "preview_person": {
      if (!hasHousehold(state)) return state;
      if (state.phase === "person_confirmed" && state.person.id === action.personId) return state;
      if (state.phase === "person_preview" && state.candidate.id === action.personId) return state;
      const candidate = state.members.find((m) => m.id === action.personId);
      if (!candidate) return state; // only members of the confirmed household can be chosen
      return {
        phase: "person_preview",
        household: state.household,
        members: state.members,
        candidate,
        confirming: false,
        attempt: null,
      };
    }
    case "confirm_person_started":
      if (state.phase !== "person_preview" || state.candidate.id !== action.personId) return state;
      return { ...state, confirming: true, attempt: action.attempt };
    case "person_confirmed": {
      if (state.phase !== "person_preview" || !pending(state, action.attempt)) return state;
      if (state.candidate.id !== action.person.id) return state;
      if (action.person.household_public_id !== state.household.public_id) return state;
      return { phase: "person_confirmed", household: state.household, members: state.members, person: action.person };
    }
    case "confirm_person_failed":
      if (state.phase !== "person_preview" || !pending(state, action.attempt)) return state;
      if (state.candidate.id !== action.personId) return state;
      // A refusal may mean the household itself is no longer ours: start again from the map.
      return action.retryable ? { ...state, confirming: false, attempt: null } : initialSelection;
    case "cancel_preview":
      if (state.phase === "household_preview") return initialSelection;
      if (state.phase === "person_preview") {
        return { phase: "household_confirmed", household: state.household, members: state.members };
      }
      return state;
    case "change_member":
      if (state.phase === "person_preview" || state.phase === "person_confirmed") {
        return { phase: "household_confirmed", household: state.household, members: state.members };
      }
      return state;
    case "change_household":
    case "reset":
      return initialSelection;
  }
}

/** The household the UI may treat as confirmed (never a preview candidate). */
export function confirmedHousehold(s: Selection): HouseholdDetail | null {
  return hasHousehold(s) ? s.household : null;
}

/** The member the UI may treat as selected (only after the server recheck). */
export function confirmedPerson(s: Selection): PersonOut | null {
  return s.phase === "person_confirmed" ? s.person : null;
}

/** The household ID to highlight on the map and list: the confirmed one, or the candidate. */
export function highlightedHouseholdId(s: Selection): string | null {
  if (s.phase === "household_preview") return s.candidate.id;
  return hasHousehold(s) ? s.household.id : null;
}
