import type {
  DepreciationOut,
  FaultsOut,
  MarketCompsOut,
  ObdSnapshotOut,
  PredictOut,
  VehicleProfile,
} from "./client";

export const demoProfile: VehicleProfile = {
  id: 1,
  name: "Mercedes-AMG GT 63 S 4MATIC+",
  model: "AMG GT 63 S",
  year: 2021,
  mileage: 45320,
  transmission: "Automatic",
  fuel_type: "Petrol V8",
  engine_size: 4.0,
  mpg: 24.2,
  tax: 3880,
  service_history_count: 6,
  service_history_total: 7,
  service_history_max: 7,
  workshop: "Hap Seng Star KL",
  glb_asset: null,
  created_at: "2026-07-03T00:00:00Z",
  updated_at: "2026-07-03T00:00:00Z",
};

export const demoSnapshot: ObdSnapshotOut = {
  rpm: 853,
  coolant_c: 76,
  battery_v: 12.7,
  health: 87,
  odo_km: 45320,
  simulated: true,
  ts: "2026-07-03T00:00:00Z",
};

export const demoPrediction: PredictOut = {
  value_rm: 738000,
  low_rm: 712000,
  high_rm: 765000,
  confidence: 0.92,
  currency: "RM",
};

export const demoMarket: MarketCompsOut = {
  comps: [],
  median_rm: 721000,
  delta_pct: 0.024,
  n: 12,
};

export const demoDepreciation: DepreciationOut = {
  points: [
    { year: 2021, value_rm: 1798000, retained_pct: 1 },
    { year: 2022, value_rm: 1290000, retained_pct: 0.72 },
    { year: 2023, value_rm: 1052000, retained_pct: 0.59 },
    { year: 2024, value_rm: 901000, retained_pct: 0.5 },
    { year: 2025, value_rm: 806000, retained_pct: 0.45 },
    { year: 2026, value_rm: 738000, retained_pct: 0.41 },
    { year: 2027, value_rm: 684000, retained_pct: 0.38 },
    { year: 2028, value_rm: 640000, retained_pct: 0.36 },
  ],
};

export const demoFaults: FaultsOut = {
  faults: [
    {
      code: "ODX-REPORT-STATUS",
      description: "ODX diagnostic service exposes status_report",
      severity: "info",
      system: "somersault_base_variant",
    },
  ],
};
