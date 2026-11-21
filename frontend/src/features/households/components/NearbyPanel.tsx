import { useEffect, useRef, useState } from "react";

import { ApiError, apiV2, isUnauthorized } from "../../../lib/apiV2";
import type { NearbyHousehold } from "../../../types/contracts";
import { accuracyLevel, closeTogether, formatMetres, nearbyRadius } from "../geo";

type State =
  | { status: "idle" }
  | { status: "locating" }
  | { status: "failed"; message: string }
  | { status: "done"; accuracyM: number; radiusM: number; results: NearbyHousehold[] };

interface Props {
  onPick: (pin: NearbyHousehold) => void;
  onSessionLost: () => void;
}

/**
 * Optional GPS hint. Location is requested only when the worker presses the button (one reading,
 * no tracking), sent once to the server, and not stored. The result is a list of suggestions:
 * nothing is previewed or confirmed automatically, even if there is exactly one.
 */
export function NearbyPanel({ onPick, onSessionLost }: Props) {
  const [state, setState] = useState<State>({ status: "idle" });
  // After logout or unmount, a late GPS fix must not be sent anywhere or update anything.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  function locate() {
    if (!("geolocation" in navigator)) {
      setState({ status: "failed", message: "This browser has no location service. Use search or the list." });
      return;
    }
    setState({ status: "locating" });
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        if (!mounted.current) return;
        const { latitude, longitude, accuracy } = position.coords;
        const radiusM = nearbyRadius(accuracy);
        try {
          const results = await apiV2.nearby(latitude, longitude, radiusM);
          if (!mounted.current) return;
          setState({ status: "done", accuracyM: accuracy, radiusM, results });
        } catch (e) {
          if (!mounted.current) return;
          if (isUnauthorized(e)) return onSessionLost();
          setState({ status: "failed", message: e instanceof ApiError ? e.message : "Nearby search failed." });
        }
      },
      (error) => {
        if (!mounted.current) return;
        const message =
          error.code === error.PERMISSION_DENIED
            ? "Location permission was denied. Use search or the list below; nothing else changes."
            : error.code === error.TIMEOUT
              ? "Location timed out. Use search or the list below."
              : "Location is unavailable. Use search or the list below.";
        setState({ status: "failed", message });
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  }

  return (
    <section aria-labelledby="nearby-heading" className="flex flex-col gap-2 rounded-2xl bg-sheet p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="nearby-heading" className="font-display text-base font-bold">
          Near me <span className="font-body text-xs font-normal text-ink-soft">(GPS hint only)</span>
        </h2>
        <button
          type="button"
          onClick={locate}
          disabled={state.status === "locating"}
          className="min-h-11 rounded-xl border border-ink px-3 text-sm font-semibold disabled:opacity-60"
        >
          {state.status === "locating" ? "Locating…" : "Use my location"}
        </button>
      </div>
      <div aria-live="polite" className="flex flex-col gap-2 text-sm">
        {state.status === "failed" && (
          <p role="status" className="rounded-xl bg-paper px-3 py-2">
            {state.message}
          </p>
        )}
        {state.status === "done" && (
          <>
            <p className="text-ink-soft">
              Accuracy ±{formatMetres(state.accuracyM)}.
              {accuracyLevel(state.accuracyM) === "poor" && " Imprecise: check the household ID with the family."}
              {" "}Suggestions only: choose and confirm the household yourself.
            </p>
            {state.results.length === 0 ? (
              <p>No household of yours within {formatMetres(state.radiusM)}.</p>
            ) : (
              <>
                {closeTogether(
                  state.results.map((r) => r.distance_m),
                  state.accuracyM,
                ) && <p className="font-semibold">Several households are close together. Confirm the ID with the family.</p>}
                <ul className="flex flex-col gap-1" aria-label="Nearby suggestions">
                  {state.results.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button"
                        onClick={() => onPick(r)}
                        data-nearby={r.public_id}
                        className="flex min-h-11 w-full items-center justify-between rounded-lg border border-rule px-3 text-left"
                      >
                        <span className="font-semibold">{r.public_id}</span>
                        <span className="text-ink-soft">{formatMetres(r.distance_m)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
