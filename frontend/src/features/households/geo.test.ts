import { describe, expect, it } from "vitest";

import { accuracyLevel, closeTogether, formatMetres, nearbyRadius, pinBounds, toLngLat } from "./geo";

describe("coordinate order", () => {
  it("MapLibre gets [longitude, latitude]", () => {
    // H-003 synthetic pin in Cubbon Park: latitude 12.97..., longitude 77.59...
    expect(toLngLat({ latitude: 12.977466, longitude: 77.594572 })).toEqual([77.594572, 12.977466]);
  });

  it("bounds are [south-west, north-east] in [lng, lat]", () => {
    const b = pinBounds([
      { latitude: 12.978, longitude: 77.5946 },
      { latitude: 12.9703, longitude: 77.5901 },
    ]);
    expect(b).toEqual([
      [77.5901, 12.9703],
      [77.5946, 12.978],
    ]);
  });

  it("no pins means no bounds", () => {
    expect(pinBounds([])).toBeNull();
  });
});

describe("GPS hint helpers", () => {
  it("radius widens with poor accuracy and stays within the server limits", () => {
    expect(nearbyRadius(10)).toBe(250);
    expect(nearbyRadius(200)).toBe(600);
    expect(nearbyRadius(4000)).toBe(5000);
    expect(nearbyRadius(Number.NaN)).toBe(1000);
    expect(nearbyRadius(-1)).toBe(1000);
  });

  it("accuracy levels", () => {
    expect(accuracyLevel(12)).toBe("good");
    expect(accuracyLevel(60)).toBe("fair");
    expect(accuracyLevel(250)).toBe("poor");
    expect(accuracyLevel(Number.POSITIVE_INFINITY)).toBe("poor");
  });

  it("flags suggestions GPS cannot tell apart", () => {
    expect(closeTogether([0, 0], 5)).toBe(true); // overlapping pins
    expect(closeTogether([12, 40], 50)).toBe(true);
    expect(closeTogether([12, 140], 20)).toBe(false);
    expect(closeTogether([12], 500)).toBe(false);
  });

  it("formats distances", () => {
    expect(formatMetres(12.4)).toBe("12 m");
    expect(formatMetres(1520)).toBe("1.5 km");
  });
});
