import { type FormEvent, useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ApiError, apiV2, isUnauthorized } from "../../lib/apiV2";
import type { HouseholdPin, MeOut } from "../../types/contracts";
import { HouseholdList } from "./components/HouseholdList";
import { HouseholdMap } from "./components/HouseholdMap";
import { NearbyPanel } from "./components/NearbyPanel";
import { SelectionBreadcrumb, SelectionPanel } from "./components/SelectionPanel";
import { confirmedHousehold, highlightedHouseholdId, initialSelection, selectionReducer } from "./selection";

const SESSION_ENDED = "Your session has ended. Please sign in again.";
const NOT_AVAILABLE = "That record is not available to your account any more. The selection was cleared.";

interface Props {
  me: MeOut;
  onSessionLost: (notice: string) => void;
}

/**
 * Phase 4 worker flow: authorized pins → candidate preview → Confirm household (server recheck)
 * → members → Select member (server recheck). Map, GPS and search are interchangeable ways to
 * reach a candidate; the list works with neither map tiles nor location.
 * This component is keyed by user, so signing out or switching account discards all its state.
 */
export function HouseholdWorkspace({ me, onSessionLost }: Props) {
  const [selection, dispatch] = useReducer(selectionReducer, initialSelection);
  const [pins, setPins] = useState<HouseholdPin[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HouseholdPin[] | null>(null);
  const [status, setStatus] = useState("");
  const panelHeading = useRef<HTMLHeadingElement>(null);
  const attempts = useRef(0); // numbers each Confirm / Select press
  const searches = useRef(0); // only the newest search may update the list
  const lost = useCallback(() => onSessionLost(SESSION_ENDED), [onSessionLost]);

  const loadPins = useCallback(async (announce = true) => {
    setLoadError(null);
    try {
      const all = await apiV2.households();
      setPins(all);
      if (announce) setStatus(`${all.length} households in your area.`);
    } catch (e) {
      if (isUnauthorized(e)) lost();
      else setLoadError(e instanceof ApiError ? e.message : "Could not load households.");
    }
  }, [lost]);

  useEffect(() => {
    void loadPins();
  }, [loadPins]);

  const focusPanel = () =>
    requestAnimationFrame(() => {
      panelHeading.current?.focus({ preventScroll: true });
      panelHeading.current?.scrollIntoView({ block: "nearest" });
    });

  const preview = useCallback(
    (pin: HouseholdPin) => {
      if (confirmedHousehold(selection)?.id === pin.id) {
        setStatus(`${pin.public_id} is already the confirmed household.`);
      } else {
        dispatch({ type: "preview_household", pin });
        setStatus(`${pin.public_id} is a candidate. Confirm it to see the members.`);
      }
      focusPanel();
    },
    [selection],
  );

  async function confirmHousehold() {
    if (selection.phase !== "household_preview") return;
    const id = selection.candidate.id;
    const attempt = ++attempts.current;
    dispatch({ type: "confirm_household_started", householdId: id, attempt });
    try {
      const [household, members] = await Promise.all([apiV2.household(id), apiV2.members(id)]);
      dispatch({ type: "household_confirmed", household, members, attempt });
      setStatus(`Household ${household.public_id} confirmed: ${members.length} members.`);
      focusPanel();
    } catch (e) {
      if (isUnauthorized(e)) return lost();
      const refused = e instanceof ApiError && e.status === 404;
      dispatch({ type: "confirm_household_failed", householdId: id, retryable: !refused, attempt });
      setStatus(refused ? NOT_AVAILABLE : e instanceof ApiError ? e.message : "Could not confirm the household.");
      if (refused) void loadPins(false); // keep the explanation on screen
    }
  }

  async function selectPerson() {
    if (selection.phase !== "person_preview") return;
    const { household, candidate } = selection;
    const attempt = ++attempts.current;
    dispatch({ type: "confirm_person_started", personId: candidate.id, attempt });
    try {
      const person = await apiV2.member(household.id, candidate.id);
      dispatch({ type: "person_confirmed", person, attempt });
      setStatus(`Selected ${person.full_name} in ${household.public_id}.`);
    } catch (e) {
      if (isUnauthorized(e)) return lost();
      const refused = e instanceof ApiError && e.status === 404;
      dispatch({ type: "confirm_person_failed", personId: candidate.id, retryable: !refused, attempt });
      setStatus(refused ? NOT_AVAILABLE : e instanceof ApiError ? e.message : "Could not select the member.");
      if (refused) void loadPins(false);
    }
  }

  async function search(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    const ticket = ++searches.current;
    if (!q) {
      setResults(null);
      return;
    }
    try {
      const found = await apiV2.households(q);
      if (ticket !== searches.current) return; // a newer search or "All" superseded this one
      setResults(found);
      setStatus(found.length ? `${found.length} match "${q}".` : `No household in your area matches "${q}".`);
    } catch (err) {
      if (isUnauthorized(err)) return lost();
      if (ticket === searches.current) setStatus(err instanceof ApiError ? err.message : "Search failed.");
    }
  }

  const highlighted = highlightedHouseholdId(selection);
  const confirmedId = confirmedHousehold(selection)?.id ?? null;
  const territories = me.territories.map((t) => t.code).join(", ") || "none";

  return (
    <div className="flex flex-col gap-3">
      <div className="sticky top-0 z-10 -mx-4 border-b border-rule bg-paper/95 px-4 py-2 backdrop-blur">
        <SelectionBreadcrumb selection={selection} />
        <p data-testid="status" aria-live="polite" className="text-xs text-ink-soft">
          {status}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="flex flex-col gap-3 lg:order-2">
          <p className="text-xs text-ink-soft">
            Signed in as {me.display_name} ({me.role}) · Territories: {territories}
          </p>
          <form role="search" onSubmit={search} className="flex gap-2">
            <label htmlFor="household-search" className="sr-only">
              Search by household ID or label
            </label>
            <input
              id="household-search"
              value={query}
              maxLength={64}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Household ID, e.g. H-003"
              className="min-h-12 min-w-0 flex-1 rounded-xl border border-rule bg-sheet px-3"
            />
            <button type="submit" className="min-h-12 rounded-xl bg-ink px-4 font-semibold text-white">
              Search
            </button>
            {results && (
              <button
                type="button"
                onClick={() => {
                  searches.current++;
                  setResults(null);
                  setQuery("");
                }}
                className="min-h-12 rounded-xl border border-ink px-3 text-sm font-semibold"
              >
                All
              </button>
            )}
          </form>
          <NearbyPanel onPick={preview} onSessionLost={lost} />
          <SelectionPanel
            ref={panelHeading}
            selection={selection}
            canRecord={me.role === "worker"}
            onConfirmHousehold={confirmHousehold}
            onCancelPreview={() => dispatch({ type: "cancel_preview" })}
            onPreviewPerson={(personId) => dispatch({ type: "preview_person", personId })}
            onSelectPerson={selectPerson}
            onChangeMember={() => dispatch({ type: "change_member" })}
            onChangeHousehold={() => {
              dispatch({ type: "change_household" });
              setStatus("Selection cleared. Choose a household.");
            }}
            onSessionLost={lost}
          />
        </div>

        <div className="flex flex-col gap-3 lg:order-1">
          {loadError && (
            <div role="alert" className="flex items-center justify-between gap-2 rounded-xl bg-alarm-wash px-3 py-2 text-sm text-alarm">
              <span>{loadError}</span>
              <button type="button" onClick={() => void loadPins()} className="min-h-11 rounded-lg border border-alarm px-3 font-semibold">
                Retry
              </button>
            </div>
          )}
          {pins && <HouseholdMap pins={pins} highlightedId={highlighted} onPick={preview} />}
          <section aria-labelledby="list-heading" className="flex flex-col gap-2">
            <h2 id="list-heading" className="font-display text-base font-bold">
              {results ? `Search results (${results.length})` : pins ? `Your households (${pins.length})` : "Your households"}
            </h2>
            {pins === null && !loadError ? (
              <p className="text-sm text-ink-soft">Loading households…</p>
            ) : (
              <HouseholdList pins={results ?? pins ?? []} highlightedId={highlighted} confirmedId={confirmedId} onPick={preview} />
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
