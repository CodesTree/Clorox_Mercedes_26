import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import App from "./App";

vi.mock("./scene/CarScene", () => ({
  CarScene: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <div data-testid="car-scene">
      <button type="button" aria-label="Select Battery/electrical" onClick={() => onSelect("battery")}>
        Select Battery/electrical
      </button>
    </div>
  ),
}));

const profile = {
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
  glb_asset: "/models/amg-gt.glb",
  created_at: "2026-07-03T00:00:00Z",
  updated_at: "2026-07-03T00:00:00Z",
};

const snapshot = {
  rpm: 853,
  coolant_c: 76,
  battery_v: 12.7,
  health: 87,
  odo_km: 45320,
  simulated: true,
  ts: "2026-07-03T00:00:00Z",
};

function response(data: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
  } as Response);
}

function mockFetch(
  options: {
    modelUnavailable?: boolean;
    placeholderProfile?: boolean;
    calendarError?: boolean;
    advisoryError?: boolean;
  } = {},
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: RequestInfo | URL) => {
      const path = String(url);
      if (path.includes("/health")) {
        return response({ status: "ok", version: "0.1.0" });
      }
      if (path.includes("/vehicle/profile")) {
        return response(
          options.placeholderProfile
            ? {
                ...profile,
                name: "Demo Mercedes SL-Class",
                model: "string",
                year: 1970,
                mileage: 0,
                transmission: "string",
                fuel_type: "string",
                engine_size: 0,
              }
            : profile,
        );
      }
      if (path.includes("/obd/snapshot")) {
        return response(snapshot);
      }
      if (path.includes("/odx/faults")) {
        return response({
          faults: [
            {
              code: "ODX-REPORT-STATUS",
              description: "ODX diagnostic service exposes status_report",
              severity: "info",
              system: "somersault_base_variant",
            },
          ],
        });
      }
      if (path.includes("/market/comps")) {
        return response({
          comps: [],
          median_rm: 721000,
          delta_pct: 0.024,
          n: 12,
        });
      }
      if (path.includes("/predict")) {
        if (options.modelUnavailable) {
          return response({ detail: "train model first: python -m ml.train" }, false, 503);
        }
        return response({
          value_rm: 738000,
          low_rm: 712000,
          high_rm: 765000,
          confidence: 0.92,
          currency: "RM",
        });
      }
      if (path.includes("/depreciation")) {
        if (options.modelUnavailable) {
          return response({ detail: "train model first: python -m ml.train" }, false, 503);
        }
        return response({
          points: [
            { year: 2021, value_rm: 1798000, retained_pct: 1 },
            { year: 2023, value_rm: 1052000, retained_pct: 0.59 },
            { year: 2026, value_rm: 738000, retained_pct: 0.41 },
            { year: 2028, value_rm: 640000, retained_pct: 0.36 },
          ],
        });
      }
      if (path.includes("/advisory/interpret")) {
        if (options.advisoryError) {
          return response({ detail: "Not Found" }, false, 404);
        }
        return response({
          recommendation: "Repair and keep",
          summary:
            "Gemini says repair and keep because the RM18,400 repair bundle is lower than the five-year depreciation loss.",
          horizon_years: 5,
          current_value_rm: 738000,
          horizon_value_rm: 620000,
          depreciation_loss_rm: 118000,
          total_repair_cost_rm: 18400,
          repairs: [
            { name: "Battery health check", cost_rm: 4200 },
            { name: "Brake wear service", cost_rm: 7800 },
            { name: "Cooling system inspection", cost_rm: 6400 },
          ],
          llm_used: true,
        });
      }
      if (path.includes("/booking")) {
        return response({
          booking_id: 12,
          status: "dry_run",
          dispatched: false,
          dry_run: true,
          payload: options.calendarError
            ? {
                calendar_mode: "shared",
                calendar_error: "Google Calendar credentials file not found",
              }
            : { text: "Inspection booking request" },
        });
      }
      return response({}, false, 404);
    }),
  );
}

beforeEach(() => {
  mockFetch();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("renders the Phase 04 cinematic dashboard layout with API-fed values", async () => {
  render(<App />);

  expect(screen.getByTestId("wordmark-star")).toBeInTheDocument();
  expect(await screen.findByText(/738,000/)).toBeInTheDocument();
  expect(screen.getByLabelText("Live OBD-II rail")).toBeInTheDocument();
  expect(screen.getByText("853")).toBeInTheDocument();
  expect(screen.getByText("12.7")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Component dock" })).toBeInTheDocument();
  expect(screen.getByLabelText("Selected component detail")).toBeInTheDocument();
  expect(screen.getByLabelText("Depreciation forecast")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Book certified inspection/i })).toBeInTheDocument();
  expect(screen.getByText(/DRAG TO ORBIT/i)).toBeInTheDocument();
  expect(screen.getByText(/SCROLL TO ZOOM/i)).toBeInTheDocument();
});

test("right component dock opens the matching bottom detail panel", async () => {
  render(<App />);

  const diagnostics = await screen.findByRole("button", {
    name: /DTC Diagnostics fault codes/i,
  });
  fireEvent.click(diagnostics);

  expect(diagnostics).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText("ODX-REPORT-STATUS")).toBeInTheDocument();
  expect(screen.getByText(/somersault_base_variant/)).toBeInTheDocument();
});

test("fallback car region selection stays in sync with the component panel", async () => {
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /Select Battery\/electrical/i }));

  expect(screen.getByRole("button", { name: /BAT Battery\/electrical/i })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByText(/Battery voltage/i)).toBeInTheDocument();
});

test("booking modal suggests nearest Mercedes centre and submits the hidden inspection purpose", async () => {
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /Book certified inspection/i }));
  const modal = screen.getByRole("dialog", { name: "Book inspection" });

  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Test User" } });

  expect(within(modal).queryByLabelText("Purpose")).not.toBeInTheDocument();
  expect(within(modal).getByText("Hap Seng Star KL")).toBeInTheDocument();
  expect(within(modal).getByText(/Current OBD location/i)).toBeInTheDocument();
  const timeInput = within(modal).getByLabelText("Time");
  expect(timeInput.tagName).toBe("INPUT");
  expect(timeInput).toHaveAttribute("type", "time");
  expect(timeInput).toHaveAttribute("min", "09:00");
  expect(timeInput).toHaveAttribute("max", "18:00");
  expect(timeInput).toHaveAttribute("step", "600");

  fireEvent.click(within(modal).getByRole("button", { name: /Change workshop/i }));
  expect(modal).toHaveClass("booking-modal--picker-open");
  const workshopDialog = screen.getByRole("dialog", { name: /Select Mercedes centre/i });
  expect(workshopDialog.parentElement).toHaveClass("workshop-picker-shell");
  const workshopButtons = within(workshopDialog).getAllByRole("button", { name: /Select .* km away/i });
  expect(workshopButtons[0]).toHaveTextContent("Hap Seng Star KL");

  fireEvent.click(within(workshopDialog).getByRole("button", { name: /Select NZ Wheels Bangsar/i }));
  expect(within(modal).getByText("NZ Wheels Bangsar")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /^Submit booking$/i }));

  await waitFor(() => expect(screen.getByText(/Dry-run booking saved/i)).toBeInTheDocument());

  const bookingCall = vi
    .mocked(fetch)
    .mock.calls.find(([url]) => String(url).includes("/booking"));
  expect(bookingCall).toBeDefined();
  const requestBody = JSON.parse(String((bookingCall?.[1] as RequestInit | undefined)?.body));
  expect(requestBody).toMatchObject({
    name: "Test User",
    workshop: "NZ Wheels Bangsar",
    car_model: "Mercedes-AMG GT 63 S 4MATIC+",
    purpose: "Certified inspection",
  });
});

test("booking modal shows calendar error details when booking stays in dry-run", async () => {
  mockFetch({ calendarError: true });

  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /Book certified inspection/i }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Test User" } });
  fireEvent.click(screen.getByRole("button", { name: /^Submit booking$/i }));

  expect(await screen.findByText(/Google Calendar credentials file not found/i)).toBeInTheDocument();
});

test("advisory button opens the keep-versus-sell advisory summary", async () => {
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /Advisory/i }));

  const modal = screen.getByRole("dialog", { name: "AssetIQ advisory" });
  expect(within(modal).getByText(/Keep vs sell analysis/i)).toBeInTheDocument();
  expect(within(modal).getByLabelText("Gemini insight")).toBeInTheDocument();
  expect(
    await within(modal).findByText(
      /Gemini says repair and keep because the RM18,400 repair bundle is lower than the five-year depreciation loss/i,
    ),
  ).toBeInTheDocument();
  expect(within(modal).getByText(/View repair priorities/i)).toBeInTheDocument();
  expect(within(modal).getByText(/Book trade-in appointment/i)).toBeInTheDocument();

  const advisoryCall = vi.mocked(fetch).mock.calls.find(([url]) => String(url).includes("/advisory/interpret"));
  expect(advisoryCall).toBeDefined();
  expect(String(advisoryCall?.[0])).toContain("profile_id=1");
});

test("advisory modal explains when Gemini insight is unavailable", async () => {
  mockFetch({ advisoryError: true });

  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /Advisory/i }));

  const modal = screen.getByRole("dialog", { name: "AssetIQ advisory" });
  expect(await within(modal).findByText(/Gemini insight unavailable/i)).toBeInTheDocument();
  expect(within(modal).getByText(/showing local fallback/i)).toBeInTheDocument();
});

test("shows graceful placeholders when valuation models are not trained", async () => {
  mockFetch({ modelUnavailable: true });

  render(<App />);

  expect(await screen.findByText(/Model not trained yet/i)).toBeInTheDocument();
  expect(screen.getByText(/Forecast unavailable until the ML model is trained/i)).toBeInTheDocument();
  expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
});

test("uses the polished demo vehicle when the backend profile is still the Swagger placeholder", async () => {
  mockFetch({ placeholderProfile: true });

  render(<App />);

  expect(await screen.findByText(/Mercedes-AMG GT 63 S 4MATIC/)).toBeInTheDocument();
  expect(screen.queryByText(/1970 - Demo Mercedes SL-Class - 0 km/i)).not.toBeInTheDocument();
});

test("falls back to OBD polling when the SSE stream errors", async () => {
  type FakeStream = { onerror?: () => void; close: ReturnType<typeof vi.fn> };
  const streamRef: { current?: FakeStream } = {};

  class FakeEventSource {
    onerror?: () => void;
    close = vi.fn();

    constructor() {
      streamRef.current = this;
    }

    addEventListener() {
      return undefined;
    }
  }

  vi.stubGlobal("EventSource", FakeEventSource);
  render(<App />);

  await screen.findByText(/Mercedes-AMG GT 63 S 4MATIC/);
  const stream = streamRef.current;
  if (!stream) {
    throw new Error("Expected dashboard to open the OBD EventSource stream");
  }
  vi.useFakeTimers();
  const fetchMock = vi.mocked(fetch);
  const callsBeforeError = fetchMock.mock.calls.filter(([url]) => String(url).includes("/obd/snapshot")).length;

  await act(async () => {
    stream.onerror?.();
    await vi.advanceTimersByTimeAsync(5000);
  });

  expect(stream.close).toHaveBeenCalled();
  const callsAfterError = fetchMock.mock.calls.filter(([url]) => String(url).includes("/obd/snapshot")).length;
  expect(callsAfterError).toBeGreaterThan(callsBeforeError);
});
