import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { createBooking, getMarketComps, getObdSnapshot, getVehicleProfile, predict } from "./client";
import { mockHandlers } from "./mockHandlers";

const server = setupServer(...mockHandlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("MSW handlers cover the Phase 04 dashboard contract", async () => {
  const profile = await getVehicleProfile(1);
  const snapshot = await getObdSnapshot(profile.id);
  const market = await getMarketComps(profile.model, profile.year);
  const valuation = await predict(profile);
  const booking = await createBooking({
    profile_id: profile.id,
    name: "Test User",
    workshop: "Hap Seng Star KL",
    car_model: profile.name,
    purpose: "Certified inspection",
    date: "2026-07-10",
    time: "10:00",
  });

  expect(profile.name).toContain("Mercedes-AMG GT");
  expect(snapshot.health).toBe(87);
  expect(market.delta_pct).toBe(0.024);
  expect(valuation.value_rm).toBe(738000);
  expect(booking.status).toBe("dry_run");
});
