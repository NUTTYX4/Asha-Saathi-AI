import { describe, expect, it } from "vitest";

import { isV2Path } from "./route";

describe("app routing", () => {
  it.each(["/v2", "/v2/", "/v2/anything"])("%s opens the V2 app", (path) => {
    expect(isV2Path(path)).toBe(true);
  });

  it.each(["/", "", "/v2x", "/followups", "/V2", "/x/v2"])("%s keeps the Round 1 screen", (path) => {
    expect(isV2Path(path)).toBe(false);
  });
});
