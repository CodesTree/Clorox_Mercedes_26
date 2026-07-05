import { describe, expect, it } from "vitest";
import { COMPONENTS } from "./componentConfig";

describe("componentConfig anchors", () => {
  it("assigns each component one of 3 fixed anchors, by list order mod 3", () => {
    const expected: Record<string, "top" | "left" | "lower-right"> = {
      engine: "top",
      battery: "left",
      brakes: "lower-right",
      fuel: "top",
      mileage: "left",
      diagnostics: "lower-right",
      service: "top",
    };

    for (const component of COMPONENTS) {
      expect(component.anchor).toBe(expected[component.id]);
    }
  });

  it("only ever uses the 3 known anchor values", () => {
    const validAnchors = new Set(["top", "left", "lower-right"]);
    for (const component of COMPONENTS) {
      expect(validAnchors.has(component.anchor)).toBe(true);
    }
  });
});
