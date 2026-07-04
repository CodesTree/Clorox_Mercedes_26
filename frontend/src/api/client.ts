// Dev traffic goes through the Vite proxy (/api -> http://localhost:8000).
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export interface HealthOut {
  status: string;
  version: string;
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

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
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

export function getHealth(): Promise<HealthOut> {
  return request<HealthOut>("/health");
}

export function createBooking(booking: BookingIn): Promise<BookingOut> {
  return request<BookingOut>("/booking", {
    method: "POST",
    body: JSON.stringify(booking),
  });
}
