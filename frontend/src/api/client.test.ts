import { beforeEach, expect, test, vi } from "vitest";
import { createBooking, predictObd, type CarFeaturesIn } from "./client";

beforeEach(() => {
  vi.restoreAllMocks();
});

test("creates a booking and exposes shared calendar payload", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        booking_id: 123,
        status: "booked",
        dispatched: true,
        dry_run: false,
        payload: {
          calendar_mode: "shared",
          calendar_event_id: "shared-event-123",
          calendar_html_link: "https://calendar.google.test/event/123",
        },
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const result = await createBooking({
    profile_id: 1,
    name: "Chan",
    workshop: "Hap Seng Star KL",
    car_model: "Mercedes-AMG GT 63 S 4MATIC+",
    purpose: "Certified inspection",
    date: "2026-07-10",
    time: "10:00",
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/booking",
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("Hap Seng Star KL"),
    }),
  );
  expect(result.payload?.calendar_mode).toBe("shared");
  expect(result.payload?.calendar_event_id).toBe("shared-event-123");
});

test("predicts resale value from full OBD car features", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        value_rm: 117668,
        low_rm: 89145,
        high_rm: 146191,
        confidence: 0.758,
        currency: "RM",
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const features: CarFeaturesIn = {
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

  const result = await predictObd(features);

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/predict/obd",
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("C-Class T-Modell"),
    }),
  );
  expect(result.value_rm).toBe(117668);
});
