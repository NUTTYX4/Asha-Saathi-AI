import { CircleAlert, MapPinned, RefreshCw, Search, X } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ApiError, apiV2, isUnauthorized } from "../../lib/apiV2";
import type { HouseholdPin, MeOut } from "../../types/contracts";
import { Button, ConfirmDialog, Notice } from "../ui/primitives";
import { DESKTOP_QUERY, useMediaQuery } from "../ui/useMediaQuery";
import { HouseholdList } from "./components/HouseholdList";
import { HouseholdMap } from "./components/HouseholdMap";
import { JourneyRail, type Screen } from "./components/JourneyRail";
import { NearbyPanel } from "./components/NearbyPanel";
import { HouseholdPreviewSheet, HouseholdScreen, MemberScreen } from "./components/SelectionPanel";
import { confirmedHousehold, highlightedHouseholdId, initialSelection, selectionReducer } from "./selection";

const SESSION_ENDED = "Your session has ended. Please sign in again.";
const NOT_AVAILABLE = "That record is not available to your account any more. The selection was cleared.";

interface Props {
  me: MeOut;
  onSessionLost: (notice: string) => void;
}

type View = "auto" | "households" | "household";

/**
 * The worker journey: authorized pins → candidate preview → Confirm household (server recheck)
 * → members → Select member (server recheck) → person-bound voice visit and history.
 *
 * On a phone each step is its own screen and decisions sit in a bottom sheet; from the lg
 * breakpoint the households stay on the left and the current step on the right. The selection
 * reducer (selection.ts) is the single source of truth: screens only display it. Leaving a live
 * voice visit asks first, because leaving ends it without saving.
 * Keyed by user, so signing out or switching account discards all of this state.
 */
export function HouseholdWorkspace({ me, onSessionLost }: Props) {
  const [selection, dispatch] = useReducer(selectionReducer, initialSelection);
  const [pins, setPins] = useState<HouseholdPin[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HouseholdPin[] | null>(null);
  const [status, setStatus] = useState("");
  const [view, setView] = useState<View>("auto");
  const [voiceActive, setVoiceActive] = useState(false);
  const [pendingLeave, setPendingLeave] = useState<(() => void) | null>(null);
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const panelHeading = useRef<HTMLHeadingElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
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

  // Any change of what is selected returns to the screen for that step.
  useEffect(() => {
    setView("auto");
  }, [selection.phase]);

  const hasHousehold =
    selection.phase === "household_confirmed" || selection.phase === "person_preview" || selection.phase === "person_confirmed";

  const screen: Screen = (() => {
    if (view === "households" || selection.phase === "none" || selection.phase === "household_preview") return "households";
    if (view === "household" || selection.phase !== "person_confirmed") return "household";
    return "member";
  })();
  // On a desktop the households stay visible, so the detail column ignores the "households" view.
  const detail: Screen | "none" | "preview" =
    selection.phase === "none"
      ? "none"
      : selection.phase === "household_preview"
        ? "preview"
        : view === "household" || selection.phase !== "person_confirmed"
          ? "household"
          : "member";
  const memberVisible = isDesktop ? detail === "member" : screen === "member";

  /** Run `action` now, or first ask if it would end a live voice visit. */
  const leaveVisit = useCallback(
    (action: () => void, endsVisit: boolean) => {
      if (voiceActive && endsVisit) setPendingLeave(() => action);
      else action();
    },
    [voiceActive],
  );

  const focusPanel = () =>
    requestAnimationFrame(() => {
      panelHeading.current?.focus({ preventScroll: true });
      panelHeading.current?.scrollIntoView({ block: "nearest" });
    });

  const toTop = () => {
    if (!isDesktop) window.scrollTo({ top: 0 });
  };

  function preview(pin: HouseholdPin) {
    if (confirmedHousehold(selection)?.id === pin.id) {
      setView("auto");
      setStatus(`${pin.public_id} is already the confirmed household.`);
      toTop();
      focusPanel();
      return;
    }
    leaveVisit(() => {
      dispatch({ type: "preview_household", pin });
      setStatus(`${pin.public_id} is a candidate. Confirm it to see the members.`);
      focusPanel();
    }, memberVisible);
  }

  async function confirmHousehold() {
    if (selection.phase !== "household_preview") return;
    const id = selection.candidate.id;
    const attempt = ++attempts.current;
    dispatch({ type: "confirm_household_started", householdId: id, attempt });
    try {
      const [household, members] = await Promise.all([apiV2.household(id), apiV2.members(id)]);
      dispatch({ type: "household_confirmed", household, members, attempt });
      setStatus(`Household ${household.public_id} confirmed: ${members.length} members.`);
      toTop();
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
      toTop();
      focusPanel();
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

  function clearSearch() {
    searches.current++;
    setResults(null);
    setQuery("");
  }

  function goStep(target: Screen) {
    if (target === "households" && isDesktop) {
      searchInput.current?.focus();
      return;
    }
    const hidesMember = isDesktop ? target === "household" && detail === "member" : screen === "member" && target !== "member";
    leaveVisit(() => {
      setView(target === "member" ? "auto" : target);
      toTop();
    }, hidesMember);
  }

  const highlighted = highlightedHouseholdId(selection);
  const confirmedId = confirmedHousehold(selection)?.id ?? null;
  const showHouseholds = isDesktop || screen === "households";
  const previewOpen = selection.phase === "household_preview";

  const householdsPane = (
    <div className={`flex flex-col gap-3 ${previewOpen ? "pb-[24rem] lg:pb-0" : ""}`}>
      <form role="search" onSubmit={search} className="flex gap-2">
        <label htmlFor="household-search" className="sr-only">
          Search by household ID or label
        </label>
        <div className="relative min-w-0 flex-1">
          <Search size={20} aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-fg-3" />
          <input
            id="household-search"
            ref={searchInput}
            value={query}
            maxLength={64}
            autoComplete="off"
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. H-003"
            className="h-12 w-full rounded-md border border-control bg-surface pr-3 pl-10 text-base placeholder:text-fg-3 hover:border-neutral-700 focus:border-berry-600 focus:outline-none focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#902c4e]"
          />
        </div>
        <Button type="submit" size="lg" className="px-4">
          Search
        </Button>
        {results && (
          <Button variant="ghost" size="lg" className="px-3" onClick={clearSearch} icon={<X size={18} />}>
            All
          </Button>
        )}
      </form>

      {loadError && (
        <Notice tone="error" icon={<CircleAlert size={20} />} role="alert" title="Households did not load">
          <p>{loadError}</p>
          <Button variant="outline" size="md" className="mt-2" icon={<RefreshCw size={18} />} onClick={() => void loadPins()}>
            Retry
          </Button>
        </Notice>
      )}

      {pins && <HouseholdMap pins={pins} highlightedId={highlighted} onPick={preview} />}
      <NearbyPanel onPick={preview} onSessionLost={lost} />

      <section aria-labelledby="list-heading" className="flex flex-col gap-2">
        <h2 id="list-heading" className="px-1 text-lg font-extrabold">
          {results ? `Search results (${results.length})` : pins ? `Your households (${pins.length})` : "Your households"}
        </h2>
        {pins === null && !loadError ? (
          <div aria-busy="true" className="flex flex-col gap-2">
            <p className="sr-only">Loading households</p>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-sunken" />
            ))}
          </div>
        ) : (
          <HouseholdList pins={results ?? pins ?? []} highlightedId={highlighted} confirmedId={confirmedId} onPick={preview} />
        )}
      </section>
    </div>
  );

  const previewSheet =
    selection.phase === "household_preview" ? (
      <HouseholdPreviewSheet
        ref={panelHeading}
        candidate={selection.candidate}
        confirming={selection.confirming}
        onConfirm={confirmHousehold}
        onCancel={() => dispatch({ type: "cancel_preview" })}
      />
    ) : null;

  const householdScreen = hasHousehold ? (
    <HouseholdScreen
      ref={panelHeading}
      household={selection.household}
      members={selection.members}
      candidateId={selection.phase === "person_preview" ? selection.candidate.id : null}
      selectedId={selection.phase === "person_confirmed" ? selection.person.id : null}
      candidate={selection.phase === "person_preview" ? selection.candidate : null}
      confirmingPerson={selection.phase === "person_preview" && selection.confirming}
      onBack={() => goStep("households")}
      onChangeHousehold={() =>
        leaveVisit(() => {
          dispatch({ type: "change_household" });
          setStatus("Selection cleared. Choose a household.");
        }, memberVisible)
      }
      onPreviewPerson={(personId) =>
        leaveVisit(() => dispatch({ type: "preview_person", personId }), memberVisible)
      }
      onSelectPerson={selectPerson}
      onCancelPerson={() => dispatch({ type: "cancel_preview" })}
    />
  ) : null;

  const memberScreen =
    selection.phase === "person_confirmed" ? (
      <MemberScreen
        ref={panelHeading}
        household={selection.household}
        person={selection.person}
        canRecord={me.role === "worker"}
        onBack={() => goStep("household")}
        onChangeMember={() => leaveVisit(() => dispatch({ type: "change_member" }), true)}
        onSessionLost={lost}
        onVoiceActiveChange={setVoiceActive}
      />
    ) : null;

  const desktopDetail =
    detail === "none" ? (
      <section className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface px-6 py-10 text-center shadow-sm">
        <span className="grid size-16 place-items-center rounded-full bg-berry-50 text-berry-600">
          <MapPinned size={32} aria-hidden="true" />
        </span>
        <h2 className="text-xl font-extrabold">Choose a household</h2>
        <p className="max-w-xs text-fg-2">
          Pick a pin, a row in the list, or search by ID. Nothing opens until you confirm the household.
        </p>
      </section>
    ) : detail === "preview" ? (
      previewSheet
    ) : detail === "household" ? (
      householdScreen
    ) : (
      memberScreen
    );

  return (
    <div className="flex flex-col">
      <JourneyRail
        selection={selection}
        screen={isDesktop ? (detail === "member" ? "member" : detail === "household" ? "household" : "households") : screen}
        status={status}
        householdCount={pins ? pins.length : null}
        onStep={goStep}
      />

      <div className="mx-auto w-full max-w-7xl px-4 pt-4 pb-12 sm:px-6 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(24rem,30rem)] lg:items-start lg:gap-6">
        {showHouseholds && householdsPane}
        {isDesktop ? (
          <div className="flex flex-col">{desktopDetail}</div>
        ) : screen === "households" ? (
          previewSheet
        ) : screen === "household" ? (
          householdScreen
        ) : (
          memberScreen
        )}
      </div>

      <ConfirmDialog
        open={pendingLeave !== null}
        title="End this voice visit?"
        body="Nothing has been saved. The microphone stops and this draft is discarded."
        confirmLabel="End visit"
        cancelLabel="Keep recording"
        onConfirm={() => {
          const action = pendingLeave;
          setPendingLeave(null);
          action?.();
        }}
        onCancel={() => setPendingLeave(null)}
      />
    </div>
  );
}
