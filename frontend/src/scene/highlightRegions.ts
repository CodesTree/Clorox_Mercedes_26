import type { ComponentId } from "../components/componentConfig";

export type HighlightKind = "box" | "wheelPair" | "cabin";

export interface HighlightRegion {
  kind: HighlightKind;
  position: readonly [number, number, number];
  size: readonly [number, number, number];
}

export const HIGHLIGHT_REGIONS: Record<ComponentId, HighlightRegion> = {
  engine: {
    kind: "box",
    position: [1.12, 0.43, 0.2],
    size: [1.48, 0.36, 1.36],
  },
  battery: {
    kind: "box",
    position: [1.86, 0.43, -0.58],
    size: [0.5, 0.26, 0.5],
  },
  brakes: {
    kind: "wheelPair",
    position: [0, -0.08, 0.84],
    size: [0.43, 0.06, 0.43],
  },
  fuel: {
    kind: "box",
    position: [-1.78, 0.34, 0.08],
    size: [0.78, 0.32, 1.2],
  },
  mileage: {
    kind: "box",
    position: [-0.24, 0.72, -0.34],
    size: [0.48, 0.22, 0.5],
  },
  diagnostics: {
    kind: "box",
    position: [0.54, 0.31, -0.84],
    size: [0.34, 0.22, 0.28],
  },
  service: {
    kind: "cabin",
    position: [-0.72, 0.79, 0.02],
    size: [1.42, 0.62, 1.5],
  },
};
