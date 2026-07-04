import { beforeEach, expect, test, vi } from "vitest";
import { createBooking } from "./client";

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
