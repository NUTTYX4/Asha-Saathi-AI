import type { Map as MapLibreMap, Marker, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import type { HouseholdPin } from "../../../types/contracts";
import { pinBounds, toLngLat } from "../geo";

/**
 * Basemap. By default the pins sit on a plain background and the map makes no external requests.
 * A street basemap is opt-in: set VITE_MAP_STYLE_URL (e.g. in frontend/.env.local) to a MapLibre
 * style URL whose terms the project owner has accepted, such as OpenFreeMap's
 * https://tiles.openfreemap.org/styles/liberty (free, no key; attribution is added automatically).
 * Whatever the basemap does, the pins and the household list keep working: a tile failure never
 * blocks selecting a household.
 */
const STYLE_URL = ((import.meta.env.VITE_MAP_STYLE_URL as string | undefined) ?? "").trim();
const PLAIN_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#e8eee6" } }],
};
const PARK_CENTRE: [number, number] = [77.5925, 12.9745]; // [lng, lat], Cubbon Park (synthetic demo area)
const DEMO_ATTRIBUTION = "Synthetic demo pins · not real residences";

type Problem = null | "tiles" | "unsupported";
type MapLibre = typeof import("maplibre-gl");

interface Props {
  pins: HouseholdPin[];
  highlightedId: string | null;
  onPick: (pin: HouseholdPin) => void;
}

export function HouseholdMap({ pins, highlightedId, onPick }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const lib = useRef<MapLibre | null>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef(new Map<string, { marker: Marker; el: HTMLButtonElement }>());
  const pick = useRef(onPick);
  pick.current = onPick;
  const [ready, setReady] = useState(false);
  const [problem, setProblem] = useState<Problem>(null);

  // Create the map once (MapLibre is loaded on demand, in its own chunk).
  useEffect(() => {
    let cancelled = false;
    let instance: MapLibreMap | null = null;
    const placed = markers.current;
    (async () => {
      try {
        // MapLibre 6 is ESM-only and needs its worker URL set once when bundled (Vite recipe).
        const [maplibre, worker] = await Promise.all([
          import("maplibre-gl"),
          import("maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"),
          import("maplibre-gl/dist/maplibre-gl.css"),
        ]);
        maplibre.setWorkerUrl(worker.default);
        if (cancelled || !container.current) return;
        instance = new maplibre.Map({
          container: container.current,
          style: STYLE_URL || PLAIN_STYLE,
          center: PARK_CENTRE,
          zoom: 15,
          attributionControl: { compact: true, customAttribution: DEMO_ATTRIBUTION },
        });
        instance.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        // Style or tile failures (offline, blocked, provider down): keep the pins, say so.
        instance.on("error", (event) => {
          if (cancelled) return;
          setProblem(event.error instanceof maplibre.GPUInitializationError ? "unsupported" : "tiles");
        });
        lib.current = maplibre;
        map.current = instance;
        setReady(true);
      } catch {
        // No WebGL, or the map code could not load: the list below is the fallback.
        if (!cancelled) setProblem("unsupported");
      }
    })();
    return () => {
      cancelled = true;
      placed.forEach(({ marker }) => marker.remove());
      placed.clear();
      instance?.remove();
      map.current = null;
      setReady(false);
    };
  }, []);

  // Place one keyboard-focusable button per pin, then fit the view to them.
  useEffect(() => {
    const m = map.current;
    const maplibre = lib.current;
    if (!ready || !m || !maplibre) return;
    const placed = markers.current;
    placed.forEach(({ marker }) => marker.remove());
    placed.clear();
    for (const pin of pins) {
      const el = document.createElement("button");
      el.type = "button";
      el.className = "asha-pin";
      el.textContent = pin.public_id.replace(/^H-0*/, "");
      el.dataset.household = pin.public_id;
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        pick.current(pin);
      });
      const marker = new maplibre.Marker({ element: el, anchor: "center" }).setLngLat(toLngLat(pin)).addTo(m);
      // Set after addTo so MapLibre's default marker label does not replace ours.
      el.setAttribute("aria-label", `Household ${pin.public_id}, ${pin.member_count} members`);
      el.title = `${pin.public_id} · ${pin.member_count} members`;
      placed.set(pin.id, { marker, el });
    }
    const bounds = pinBounds(pins);
    if (bounds) m.fitBounds(bounds, { padding: 48, maxZoom: 17, duration: 0 });
  }, [pins, ready]);

  useEffect(() => {
    markers.current.forEach(({ el }, id) => {
      const active = id === highlightedId;
      el.classList.toggle("asha-pin--active", active);
      el.setAttribute("aria-pressed", String(active));
    });
  }, [highlightedId, pins, ready]);

  return (
    <section aria-label="Map of your households" className="flex flex-col gap-1">
      <div
        ref={container}
        data-testid="household-map"
        className={`h-80 w-full overflow-hidden rounded-2xl bg-[#e8eee6] lg:h-[30rem] ${problem === "unsupported" ? "hidden" : ""}`}
      />
      {problem && (
        <p role="status" data-testid="map-problem" className="rounded-xl bg-paper px-3 py-2 text-sm">
          {problem === "tiles"
            ? "Map background could not load (offline or blocked). The pins and the household list still work."
            : "The map cannot run in this browser. Use the household list below."}
        </p>
      )}
    </section>
  );
}
