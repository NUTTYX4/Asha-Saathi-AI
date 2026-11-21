/**
 * Small coordinate helpers for the household map. The API returns named `latitude` and
 * `longitude`; MapLibre and GeoJSON want `[longitude, latitude]`. Keep that conversion here
 * (tested) so the order can't be swapped by accident.
 */

export type LngLat = [longitude: number, latitude: number];

interface HasPosition {
  latitude: number;
  longitude: number;
}

export function toLngLat(p: HasPosition): LngLat {
  return [p.longitude, p.latitude];
}

/** South-west and north-east corners around the pins, or null when there are none. */
export function pinBounds(pins: HasPosition[]): [LngLat, LngLat] | null {
  if (pins.length === 0) return null;
  let [minLng, minLat] = toLngLat(pins[0]);
  let [maxLng, maxLat] = [minLng, minLat];
  for (const p of pins) {
    const [lng, lat] = toLngLat(p);
    minLng = Math.min(minLng, lng);
    maxLng = Math.max(maxLng, lng);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  }
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}

export const NEARBY_MIN_RADIUS_M = 250;
export const NEARBY_MAX_RADIUS_M = 5000; // server maximum

/** Search radius for GPS suggestions: wider when the browser reports a poor accuracy. */
export function nearbyRadius(accuracyM: number): number {
  if (!Number.isFinite(accuracyM) || accuracyM < 0) return 1000;
  return Math.min(NEARBY_MAX_RADIUS_M, Math.max(NEARBY_MIN_RADIUS_M, Math.round(accuracyM * 3)));
}

export type AccuracyLevel = "good" | "fair" | "poor";

export function accuracyLevel(accuracyM: number): AccuracyLevel {
  if (!Number.isFinite(accuracyM) || accuracyM > 100) return "poor";
  return accuracyM > 30 ? "fair" : "good";
}

/** True when GPS alone cannot tell the nearest suggestions apart (within the reported accuracy). */
export function closeTogether(distancesM: number[], accuracyM: number): boolean {
  if (distancesM.length < 2) return false;
  const [first, second] = [...distancesM].sort((a, b) => a - b);
  return second - first <= Math.max(accuracyM, 10);
}

export function formatMetres(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}
