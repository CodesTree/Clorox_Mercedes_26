const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export interface HealthOut {
  status: string;
  version: string;
}

export interface VehicleProfile {
  id: number;
  name: string;
  model: string;
  year: number;
  mileage: number;
  transmission: string;
  fuel_type: string;
  engine_size: number;
  mpg: number | null;
  tax: number | null;
  service_history_count: number | null;
  service_history_total: number | null;
  service_history_max: number | null;
  workshop: string | null;
  glb_asset: string | null;
  created_at: string;
  updated_at: string;
}

export type VehicleProfileIn = Pick<
  VehicleProfile,
  | "model"
  | "year"
  | "mileage"
  | "transmission"
  | "fuel_type"
  | "engine_size"
  | "mpg"
  | "tax"
  | "service_history_count"
  | "service_history_total"
>;

export interface CarFeaturesIn {
  model_class: string;
  year: number;
  mileage: number;
  transmission: string;
  fuel_type: string;
  engine_size: number;
  source_market: string;
  age: number;
  variant: string;
  displacement_cc: number;
  n_cylinders: number;
  n_gears: number;
  top_speed_kmh: number;
  torque_nm: number;
  accel_0_100_s: number;
  boot_l: number;
  engine_config: string;
  aspiration: string;
  gear_type: string;
  front_brake: string;
  rear_brake: string;
  match_level: string;
  battery_soh: number;
  trans_adapt_offset: number;
  estimated_annual_mileage: number;
  dtc_fault_count: number;
  brake_life_pct: number;
  health_score: number;
}

export interface PredictOut {
  value_rm: number;
  low_rm: number;
  high_rm: number;
  confidence: number;
  currency: "RM";
}

export interface MarketListingOut {
  source: "mudah" | "carlist";
  listing_url: string;
  model: string;
  variant: string | null;
  year: number;
  price_rm: number;
  mileage: number | null;
  location: string | null;
  posted_at: string | null;
}

export interface MarketCompsOut {
  comps: MarketListingOut[];
  median_rm: number | null;
  delta_pct: number | null;
  n: number;
}

export interface DepreciationPoint {
  year: number;
  value_rm: number;
  retained_pct: number;
}

export interface DepreciationOut {
  points: DepreciationPoint[];
}

export interface ObdSnapshotOut {
  rpm: number;
  coolant_c: number;
  battery_v: number;
  health: number;
  odo_km: number;
  simulated: true;
  ts: string;
}

export interface FaultOut {
  code: string;
  description: string;
  severity: string;
  system: string;
}

export interface FaultsOut {
  faults: FaultOut[];
}

export interface BookingIn {
  profile_id: number;
  name: string;
  workshop: string;
  car_model: string;
  purpose: string;
  date: string;
  time: string;
}

export interface BookingPayload {
  calendar_mode?: "shared";
  calendar_event_id?: string;
  calendar_html_link?: string;
  calendar_error?: string;
  text?: string;
  error?: string;
}

export interface BookingOut {
  booking_id: number;
  status: string;
  dispatched: boolean;
  dry_run: boolean;
  payload: BookingPayload | null;
}

export interface AdvisoryData {
  current_value_rm: number;
  estimated_repair_cost_rm: number;
  predicted_value_after_repair_rm: number;
  repair_outcome_rm: number;
  trade_in_now_rm: number;
  recommendation: "repair" | "trade_in";
  summary: string;
}

export interface AdvisoryVoiceResponse {
  reply: string;
  audio_base64: string | null;
  mime_type: string | null;
  tts_provider: "gemini" | "gemini-unavailable";
  fallback_reason: string | null;
  text_provider: "gemini" | "local";
  tts_wait_ms: number;
  gemini_key_detected: boolean;
export interface BookingAvailabilityOut {
  date: string;
  slots: string[];
}

export interface BookingReplyOut {
  booking_id: number;
  status: string;
  booked: boolean;
  proposed_date: string;
  proposed_time: string;
  round: number;
  classification: string;
  message: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

function makeUrl(path: string, params?: Record<string, string | number | boolean | null | undefined>) {
  const base = API_BASE.endsWith("/") ? API_BASE.slice(0, -1) : API_BASE;
  const url = new URL(`${base}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value));
    }
  }
  return /^https?:\/\//i.test(base) ? url.href : url.pathname + url.search;
}

async function request<T>(path: string, init?: RequestInit, params?: Record<string, string | number | boolean>) {
  const resp = await fetch(makeUrl(path, params), {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!resp.ok) {
    let detail = `${resp.status}`;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      // Keep the HTTP status fallback.
    }
    throw new ApiError(detail, resp.status);
  }
  return resp.json() as Promise<T>;
}

export function isModelUnavailable(error: unknown) {
  return error instanceof ApiError && error.status === 503;
}

export function getHealth() {
  return request<HealthOut>("/health");
}

export function getVehicleProfile(id = 1) {
  return request<VehicleProfile>("/vehicle/profile", undefined, { id });
}

export function getObdSnapshot(profileId: number) {
  return request<ObdSnapshotOut>("/obd/snapshot", undefined, { profile_id: profileId });
}

export function getFaults(profileId: number) {
  return request<FaultsOut>("/odx/faults", undefined, { profile_id: profileId });
}

export function getMarketComps(model: string, year: number, limit = 12) {
  return request<MarketCompsOut>("/market/comps", undefined, { model, year, limit });
}

export function predict(profile: VehicleProfileIn) {
  return request<PredictOut>("/predict", {
    method: "POST",
    body: JSON.stringify(profile),
  });
}

export function predictObd(features: CarFeaturesIn) {
  return request<PredictOut>("/predict/obd", {
    method: "POST",
    body: JSON.stringify(features),
  });
}

export function getDepreciation(profileId: number, years = 5) {
  return request<DepreciationOut>("/depreciation", undefined, { profile_id: profileId, years });
}

export function createBooking(booking: BookingIn) {
  return request<BookingOut>("/booking", {
    method: "POST",
    body: JSON.stringify(booking),
  });
}

export function respondToAdvisoryVoice(question: string, advisory: AdvisoryData) {
  const url = makeUrl("/advisory/voice/respond");
  const startedAt = performance.now();
  console.log("[voice] backend URL used:", url);
  console.log("[voice] question sent:", question);
  return request<AdvisoryVoiceResponse>("/advisory/voice/respond", {
    method: "POST",
    body: JSON.stringify({ question, advisory }),
  }).then((response) => {
    console.log("[voice] response latency ms:", Math.round(performance.now() - startedAt));
    console.log("[voice] text provider:", response.text_provider);
    console.log("[voice] tts wait ms:", response.tts_wait_ms);
    console.log("[voice] reply returned:", response.reply);
    console.log("[voice] tts_provider:", response.tts_provider);
    console.log("[voice] fallback_reason:", response.fallback_reason);
    console.log("[voice] audio_base64 length:", response.audio_base64?.length ?? 0);
    return response;
export function getBookingAvailability(date: string) {
  return request<BookingAvailabilityOut>("/booking/availability", undefined, { date });
}

export function checkBookingReply(bookingId: number) {
  return request<BookingReplyOut>(`/booking/${bookingId}/check-reply`, {
    method: "POST",
  });
}

export function makeObdStreamUrl(profileId: number, maxEvents = 100) {
  return makeUrl("/obd/stream", {
    profile_id: profileId,
    max_events: maxEvents,
    interval_seconds: 1,
  });
}
