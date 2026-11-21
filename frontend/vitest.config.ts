import { defineConfig } from "vitest/config";

// Unit tests for pure frontend logic (selection state machine, coordinate helpers). No DOM needed.
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
