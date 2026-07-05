import type {
  CarFeaturesIn,
  DepreciationOut,
  FaultsOut,
  MarketCompsOut,
  ObdSnapshotOut,
  PredictOut,
  VehicleProfile,
} from "./client";

export const demoCarFeatures: CarFeaturesIn = {
  model_class: "C",
  year: 2017,
  mileage: 99300,
  transmission: "Automatic",
  fuel_type: "Diesel",
  engine_size: 2.143,
  source_market: "malaysia",
  age: 9,
  variant: "MERCEDES BENZ C-Class T-Modell (S205) (2014-2018)",
  displacement_cc: 2143,
  n_cylinders: 4,
  n_gears: 6,
  top_speed_kmh: 230,
  torque_nm: 400,
  accel_0_100_s: 7.9,
  boot_l: 490,
  engine_config: "L4",
  aspiration: "turbo",
  gear_type: "manual",
  front_brake: "Ventilated Discs",
  rear_brake: "Discs",
  match_level: "displacement",
  battery_soh: 63.98,
  trans_adapt_offset: -0.0696,
  estimated_annual_mileage: 11033.3,
  dtc_fault_count: 0,
  brake_life_pct: 60.4,
  health_score: 81.6,
};

export const demoProfile: VehicleProfile = {
  id: 1,
  name: "Mercedes-Benz C-Class T-Modell (S205)",
  model: "C",
  year: 2017,
  mileage: 99300,
  transmission: "Automatic",
  fuel_type: "Diesel",
  engine_size: 2.143,
  mpg: null,
  tax: null,
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
  odo_km: 99300,
  simulated: true,
  ts: "2026-07-03T00:00:00Z",
};

export const demoPrediction: PredictOut = {
  value_rm: 117668,
  low_rm: 89145,
  high_rm: 146191,
  confidence: 0.758,
  currency: "RM",
};

export const demoMarket: MarketCompsOut = {
  comps: [],
  median_rm: null,
  delta_pct: null,
  n: 0,
};

export const demoDepreciation: DepreciationOut = {
  points: [
    { year: 2017, value_rm: 225000, retained_pct: 1 },
    { year: 2019, value_rm: 183000, retained_pct: 0.8133 },
    { year: 2021, value_rm: 152000, retained_pct: 0.6756 },
    { year: 2023, value_rm: 132000, retained_pct: 0.5867 },
    { year: 2026, value_rm: 117668, retained_pct: 0.523 },
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
