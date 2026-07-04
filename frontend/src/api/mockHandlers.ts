import { http, HttpResponse } from "msw";
import {
  demoDepreciation,
  demoFaults,
  demoMarket,
  demoPrediction,
  demoProfile,
  demoSnapshot,
} from "./mockData";
import type { BookingIn } from "./client";

export const mockHandlers = [
  http.get("/api/health", () => HttpResponse.json({ status: "ok", version: "mock" })),
  http.get("/api/vehicle/profile", () => HttpResponse.json(demoProfile)),
  http.get("/api/obd/snapshot", () => HttpResponse.json(demoSnapshot)),
  http.get("/api/odx/faults", () => HttpResponse.json(demoFaults)),
  http.get("/api/market/comps", () => HttpResponse.json(demoMarket)),
  http.post("/api/predict", () => HttpResponse.json(demoPrediction)),
  http.get("/api/depreciation", () => HttpResponse.json(demoDepreciation)),
  http.post("/api/booking", async ({ request }) => {
    const booking = (await request.json()) as BookingIn;
    return HttpResponse.json({
      booking_id: 42,
      status: "dry_run",
      dispatched: false,
      dry_run: true,
      payload: {
        text: `Inspection booking request for ${booking.car_model}`,
        booking,
      },
    });
  }),
];
