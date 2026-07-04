import type { ComponentId } from "../components/componentConfig";

export type HighlightKind = "box" | "wheelPair" | "cabin" | "fullFrame";
export type HighlightShape = "engineBay" | "batteryModule" | "fuelTank" | "controlModule";

export interface HighlightRegion {
  kind: HighlightKind;
  shape?: HighlightShape;
  position: readonly [number, number, number];
  size: readonly [number, number, number];
}

export const HIGHLIGHT_REGIONS: Record<ComponentId, HighlightRegion> = {
  engine: {
    kind: "box",
    shape: "engineBay",
    position: [1.55, 0.5, 0],
    size: [1, 0.42, 1],
  },
  battery: {
    kind: "box",
    shape: "batteryModule",
    position: [-1.85, 0.52, 0.35],
    size: [0.5, 0.26, 0.45],
  },
  brakes: {
    kind: "wheelPair",
    position: [0, 0.37, 0.82],
    size: [0.23, 0.06, 0.23],
  },
  fuel: {
    kind: "box",
    shape: "fuelTank",
    position: [-1.15, 0.38, 0],
    size: [0.9, 0.28, 1.1],
  },
  mileage: {
    kind: "box",
    shape: "controlModule",
    position: [0.62, 0.88, -0.32],
    size: [0.3, 0.16, 0.5],
  },
  diagnostics: {
    kind: "box",
    shape: "controlModule",
    position: [0.95, 0.5, -0.55],
    size: [0.22, 0.14, 0.24],
  },
  service: {
    kind: "fullFrame",
    position: [0, 0.72, 0],
    size: [5.2, 1.42, 1.8],
  },
};
