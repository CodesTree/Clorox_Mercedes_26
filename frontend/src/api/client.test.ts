import { beforeEach, expect, test, vi } from "vitest";
import { createBooking, respondToAdvisoryVoice } from "./client";

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

test("posts advisory voice questions to the backend voice endpoint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        reply: "Trade in now.",
        audio_base64: "UklGRg==",
        mime_type: "audio/wav",
        tts_provider: "gemini",
        fallback_reason: null,
        text_provider: "local",
        tts_wait_ms: 123,
        gemini_key_detected: true,
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const advisory = {
    current_value_rm: 82000,
    estimated_repair_cost_rm: 12000,
    predicted_value_after_repair_rm: 88000,
    repair_outcome_rm: 76000,
    trade_in_now_rm: 82000,
    recommendation: "trade_in" as const,
    summary: "Trading in is recommended.",
  };

  const result = await respondToAdvisoryVoice("Should I sell my car now?", advisory);

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/advisory/voice/respond",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ question: "Should I sell my car now?", advisory }),
    }),
  );
  expect(result.audio_base64).toBe("UklGRg==");
  expect(result.tts_provider).toBe("gemini");
  expect(result.text_provider).toBe("local");
  expect(result.tts_wait_ms).toBe(123);
});
