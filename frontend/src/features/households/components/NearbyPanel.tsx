import { Loader2, LocateFixed, MapPinOff, Navigation } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError, apiV2, isUnauthorized } from "../../../lib/apiV2";
import type { NearbyHousehold } from "../../../types/contracts";
import { Button } from "../../ui/primitives";
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
    <section aria-labelledby="nearby-heading" className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <h2 id="nearby-heading" className="flex min-w-0 items-center gap-2 text-base font-extrabold">
          <LocateFixed size={20} aria-hidden="true" className="shrink-0 text-berry-600" />
          <span className="min-w-0">
            Near me <span className="block text-xs font-semibold text-fg-2">GPS hint only, never selects</span>
          </span>
        </h2>
        <Button
          variant="outline"
          size="md"
          className="w-full sm:w-auto"
          onClick={locate}
          disabled={state.status === "locating"}
          icon={state.status === "locating" ? <Loader2 size={18} className="animate-spin" /> : <Navigation size={18} />}
        >
          {state.status === "locating" ? "Locating…" : "Use my location"}
        </Button>
      </div>
      <div aria-live="polite" className="flex flex-col gap-2 text-sm">
        {state.status === "failed" && (
          <p role="status" className="flex items-start gap-2 rounded-md bg-sunken px-3 py-2 text-fg">
            <MapPinOff size={18} aria-hidden="true" className="mt-px shrink-0 text-fg-2" />
            {state.message}
          </p>
        )}
        {state.status === "done" && (
          <>
            <p className="text-fg-2">
              Accuracy ±{formatMetres(state.accuracyM)}.
              {accuracyLevel(state.accuracyM) === "poor" && " Imprecise: check the household ID with the family."}
              {" "}Suggestions only: choose and confirm the household yourself.
            </p>
            {state.results.length === 0 ? (
              <p className="font-semibold">No household of yours within {formatMetres(state.radiusM)}.</p>
            ) : (
              <>
                {closeTogether(
                  state.results.map((r) => r.distance_m),
                  state.accuracyM,
                ) && (
                  <p className="rounded-md bg-warning-50 px-3 py-2 font-semibold text-warning-700">
                    Several households are close together. Confirm the ID with the family.
                  </p>
                )}
                <ul className="divide-y divide-line overflow-hidden rounded-md border border-line" aria-label="Nearby suggestions">
                  {state.results.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button"
                        onClick={() => onPick(r)}
                        data-nearby={r.public_id}
                        className="flex min-h-12 w-full items-center justify-between gap-3 px-3 text-left hover:bg-neutral-50"
                      >
                        <span className="font-extrabold">{r.public_id}</span>
                        <span className="text-fg-2">{formatMetres(r.distance_m)} away</span>
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
