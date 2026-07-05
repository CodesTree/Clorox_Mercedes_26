import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { createBooking, getMarketComps, getObdSnapshot, getVehicleProfile, predictObd } from "./client";
import { mockHandlers } from "./mockHandlers";

const server = setupServer(...mockHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("MSW handlers cover the Phase 04 dashboard contract", async () => {
  const profile = await getVehicleProfile(1);
  const snapshot = await getObdSnapshot(profile.id);
  const market = await getMarketComps(profile.model, profile.year);
  const valuation = await predictObd({
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
  });
  const booking = await createBooking({
    profile_id: profile.id,
    name: "Test User",
    workshop: "Hap Seng Star KL",
    car_model: profile.name,
    purpose: "Certified inspection",
    date: "2026-07-10",
    time: "10:00",
  });

  expect(profile.name).toContain("C-Class T-Modell");
  expect(snapshot.health).toBe(87);
  expect(market.delta_pct).toBeNull();
  expect(valuation.value_rm).toBe(117668);
  expect(booking.status).toBe("dry_run");
});
