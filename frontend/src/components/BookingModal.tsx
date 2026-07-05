import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  BookingAvailabilityOut,
  BookingDiagnosticsOut,
  BookingOut,
  BookingReplyOut,
  VehicleProfile,
} from "../api/client";
import { getBookingDiagnostics } from "../api/client";
import { demoUser } from "../api/mockData";
import {
  currentVehicleLocation,
  formatDistanceKm,
  getRankedWorkshops,
  type RankedWorkshop,
} from "./workshops";

interface BookingModalProps {
  open: boolean;
  profile: VehicleProfile | null;
  activeBooking: BookingOut | null;
  onBookingChange: (booking: BookingOut | null) => void;
  onClose: () => void;
  onSubmit: (form: {
    name: string;
    workshop: string;
    car_model: string;
    purpose: string;
    date: string;
    time: string;
  }) => Promise<BookingOut>;
  onGetAvailability: (date: string) => Promise<BookingAvailabilityOut>;
  onCheckReply: (bookingId: number) => Promise<BookingReplyOut>;
}

type Step = "details" | "review" | "status";

const BOOKING_PURPOSE = "Certified inspection";

// Flip to true to surface the developer diagnostics panel below the booking status.
const SHOW_DEV_DIAGNOSTICS = false;

// The web app waits on "sent" while the workshop replies over Telegram. These
// are the terminal states that stop the auto-poll.
const TERMINAL_STATUSES = new Set(["booked", "failed", "dry_run"]);
const POLL_INTERVAL_MS = 5000;
const MAX_POLLS = 12; // ~60s of waiting before we surface a manual retry.

function statusLabel(result: BookingOut): string {
  if (result.dry_run) return "Dry-run booking saved";
  if (result.status === "sent") return "Booking request sent - awaiting confirmation";
  if (result.status === "booked") return "Booking confirmed";
  return `Booking ${result.status}`;
}

function statusHeadline(status: string | undefined): string {
  switch (status) {
    case "booked":
      return "Inspection confirmed";
    case "sent":
      return "Awaiting booking confirmation";
    case "failed":
      return "No slot confirmed";
    case "dry_run":
      return "Dry-run booking saved";
    default:
      return "Booking update";
  }
}

export function BookingModal({
  open,
  profile,
  activeBooking,
  onBookingChange,
  onClose,
  onSubmit,
  onGetAvailability,
  onCheckReply,
}: BookingModalProps) {
  const [name, setName] = useState(demoUser.name);
  const [date, setDate] = useState("2026-07-10");
  const [time, setTime] = useState("");
  const [step, setStep] = useState<Step>("details");
  const [pickerOpen, setPickerOpen] = useState(false);

  const [slots, setSlots] = useState<string[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<BookingOut | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [lastReply, setLastReply] = useState<BookingReplyOut | null>(null);
  const [pollExhausted, setPollExhausted] = useState(false);
  const pollCountRef = useRef(0);

  const [diagnostics, setDiagnostics] = useState<BookingDiagnosticsOut | null>(null);
  const [diagOpen, setDiagOpen] = useState(false);

  const rankedWorkshops = useMemo(() => getRankedWorkshops(), []);
  const defaultWorkshopId = useMemo(() => {
    const profileMatch = rankedWorkshops.find((workshop) => workshop.name === profile?.workshop);
    return profileMatch?.id ?? rankedWorkshops[0]?.id ?? "";
  }, [profile?.workshop, rankedWorkshops]);
  const [selectedWorkshopId, setSelectedWorkshopId] = useState(defaultWorkshopId);
  const selectedWorkshop =
    rankedWorkshops.find((workshop) => workshop.id === selectedWorkshopId) ?? rankedWorkshops[0];
  const workshop = selectedWorkshop?.name ?? profile?.workshop ?? "Hap Seng Star KL";
  const model = profile?.name ?? profile?.model ?? "Mercedes-AMG GT";

  // On open, resume an already in-flight/completed booking instead of
  // blowing it away: reopening the modal must not let the user start a
  // second concurrent booking while one is pending (and stale duplicate
  // bookings break Telegram reply matching - see MAIN.md booking notes).
  // `activeBooking` is intentionally left out of the dependency array: this
  // should only decide details-vs-status at the moment the modal opens, not
  // re-run on every parent-side update while it's already open.
  useEffect(() => {
    if (!open) return;
    setSelectedWorkshopId(defaultWorkshopId);
    setPickerOpen(false);
    setLastReply(null);
    setPollExhausted(false);
    setName(demoUser.name);
    pollCountRef.current = 0;
    if (activeBooking) {
      setResult(activeBooking);
      setStatusMessage(statusLabel(activeBooking));
      setStep("status");
    } else {
      setResult(null);
      setStatusMessage(null);
      setStep("details");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultWorkshopId, open]);

  // Mirror the local booking result up to the parent so the main dashboard
  // CTA can reflect it (and it survives the modal being closed/reopened).
  useEffect(() => {
    onBookingChange(result);
  }, [result, onBookingChange]);

  // Availability is driven by the user's Google Calendar: only free slots are
  // selectable. Refetch whenever the date changes while the modal is open.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setSlotsLoading(true);
    onGetAvailability(date)
      .then((res) => {
        if (cancelled) return;
        setSlots(res.slots);
        setTime((prev) => (res.slots.includes(prev) ? prev : res.slots[0] ?? ""));
      })
      .catch(() => {
        if (cancelled) return;
        setSlots([]);
        setTime("");
      })
      .finally(() => {
        if (!cancelled) setSlotsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, date, onGetAvailability]);

  const handleConfirm = useCallback(async () => {
    setSubmitting(true);
    try {
      const res = await onSubmit({
        name,
        workshop,
        car_model: model,
        purpose: BOOKING_PURPOSE,
        date,
        time,
      });
      setResult(res);
      setStatusMessage(statusLabel(res));
      setLastReply(null);
      setPollExhausted(false);
      pollCountRef.current = 0;
      setStep("status");
    } finally {
      setSubmitting(false);
    }
  }, [date, model, name, onSubmit, time, workshop]);

  // Pull the latest Telegram reply once and fold it into the booking state.
  const runCheckReply = useCallback(async () => {
    if (!result) return;
    setChecking(true);
    try {
      const reply = await onCheckReply(result.booking_id);
      setLastReply(reply);
      setStatusMessage(reply.message);
      setResult((prev) =>
        prev
          ? {
              ...prev,
              status: reply.status,
              date: reply.proposed_date || prev.date,
              time: reply.proposed_time || prev.time,
              workshop: reply.workshop || prev.workshop,
            }
          : prev,
      );
    } finally {
      setChecking(false);
    }
  }, [onCheckReply, result]);

  // Auto-poll while awaiting the workshop reply, so the UI advances to
  // Confirmed/Rejected on its own. Stops on a terminal status or after the cap.
  useEffect(() => {
    if (step !== "status" || result?.status !== "sent" || pollExhausted) return;
    let cancelled = false;
    const timer = setInterval(() => {
      if (cancelled) return;
      if (pollCountRef.current >= MAX_POLLS) {
        setPollExhausted(true);
        return;
      }
      pollCountRef.current += 1;
      void runCheckReply();
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [step, result?.status, pollExhausted, runCheckReply]);

  // Live integration diagnostics for the demo panel (config + FreeBusy probe).
  // Fetched once the booking is in flight, when the panel is on screen.
  useEffect(() => {
    if (step !== "status") return;
    let cancelled = false;
    getBookingDiagnostics()
      .then((res) => {
        if (!cancelled) setDiagnostics(res);
      })
      .catch(() => {
        if (!cancelled) setDiagnostics(null);
      });
    return () => {
      cancelled = true;
    };
  }, [step]);

  const handleEditRetry = useCallback(() => {
    if (lastReply) {
      if (lastReply.proposed_date) setDate(lastReply.proposed_date);
      if (lastReply.proposed_time) setTime(lastReply.proposed_time);
    }
    setResult(null);
    setStatusMessage(null);
    setLastReply(null);
    setPollExhausted(false);
    pollCountRef.current = 0;
    setStep("details");
  }, [lastReply]);

  if (!open) return null;

  const canProceed = name.trim().length > 0 && time.length > 0;

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className={`booking-modal${pickerOpen ? " booking-modal--picker-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Book inspection"
      >
        <div className="modal-header">
          <div>
            <span className="eyebrow">Official Mercedes slot</span>
            <h2>Book certified inspection</h2>
            <span className="modal-step">
              {step === "details" ? "Step 1 of 2 - Details" : null}
              {step === "review" ? "Step 2 of 2 - Confirm details" : null}
            </span>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close booking">
            x
          </button>
        </div>

        {step === "details" ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (canProceed) setStep("review");
            }}
          >
            <label>
              Name
              <input value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
            {selectedWorkshop ? (
              <WorkshopSelector
                selectedWorkshop={selectedWorkshop}
                rankedWorkshops={rankedWorkshops}
                onOpenPicker={() => setPickerOpen(true)}
              />
            ) : null}
            <label>
              Car model
              <input value={model} readOnly />
            </label>
            <label>
              Date
              <input
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                required
              />
            </label>
            <label>
              Time
              {slotsLoading ? (
                <span className="slot-hint">Checking calendar availability...</span>
              ) : slots && slots.length > 0 ? (
                <select
                  value={time}
                  onChange={(event) => setTime(event.target.value)}
                  required
                >
                  {slots.map((slot) => (
                    <option key={slot} value={slot}>
                      {slot}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="slot-hint">No free slots on your calendar for this date</span>
              )}
            </label>
            <p className="modal-hint">Only times free on your Google Calendar are shown.</p>
            <button className="primary-button" type="submit" disabled={!canProceed}>
              Next
            </button>
          </form>
        ) : null}

        {step === "review" ? (
          <div className="booking-review">
            <p className="modal-hint">Review the details. Nothing is sent until you confirm.</p>
            <dl className="booking-summary">
              <div>
                <dt>Name</dt>
                <dd>{name}</dd>
              </div>
              <div>
                <dt>Nearest Mercedes Workshop</dt>
                <dd>{workshop}</dd>
              </div>
              <div>
                <dt>Car model</dt>
                <dd>{model}</dd>
              </div>
              <div>
                <dt>Purpose</dt>
                <dd>{BOOKING_PURPOSE}</dd>
              </div>
              <div>
                <dt>Date</dt>
                <dd>{date}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{time}</dd>
              </div>
            </dl>
            <div className="booking-review__actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setStep("details")}
                disabled={submitting}
              >
                Back
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={handleConfirm}
                disabled={submitting}
              >
                Confirm &amp; send booking request
              </button>
            </div>
          </div>
        ) : null}

        {step === "status" ? (
          <div className="booking-status">
            <h3 className="modal-status-headline">{statusHeadline(result?.status)}</h3>
            {statusMessage && statusMessage !== statusHeadline(result?.status) ? (
              <p className="modal-status">{statusMessage}</p>
            ) : null}

            {result?.status === "sent" ? (
              <>
                <p className="modal-hint">
                  {pollExhausted
                    ? "No reply yet. Keep waiting or check again."
                    : "Waiting for the workshop to reply on Telegram..."}
                </p>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    setPollExhausted(false);
                    pollCountRef.current = 0;
                    void runCheckReply();
                  }}
                  disabled={checking}
                >
                  {checking ? "Checking..." : "Check now"}
                </button>
              </>
            ) : null}

            {result?.status === "booked" ? (
              <dl className="booking-summary">
                <div>
                  <dt>Workshop</dt>
                  <dd>{result.workshop || workshop}</dd>
                </div>
                <div>
                  <dt>Date</dt>
                  <dd>{result.date || date}</dd>
                </div>
                <div>
                  <dt>Time</dt>
                  <dd>{result.time || time}</dd>
                </div>
              </dl>
            ) : null}

            {result?.status === "failed" ? (
              <button type="button" className="secondary-button" onClick={handleEditRetry}>
                Edit &amp; retry
              </button>
            ) : null}

            {SHOW_DEV_DIAGNOSTICS ? (
              <BookingDiagnostics
                open={diagOpen}
                onToggle={() => setDiagOpen((prev) => !prev)}
                diagnostics={diagnostics}
                result={result}
                lastReply={lastReply}
              />
            ) : null}

            <button type="button" className="primary-button" onClick={onClose}>
              {result?.status === "booked" ? "Booked" : "Done"}
            </button>
          </div>
        ) : null}

        {pickerOpen && selectedWorkshop ? (
          <div className="workshop-picker-shell">
            <WorkshopPicker
              selectedWorkshop={selectedWorkshop}
              rankedWorkshops={rankedWorkshops}
              onClosePicker={() => setPickerOpen(false)}
              onSelectWorkshop={(nextWorkshop) => {
                setSelectedWorkshopId(nextWorkshop.id);
                setPickerOpen(false);
              }}
            />
          </div>
        ) : null}
      </section>
    </div>
  );
}

interface BookingDiagnosticsProps {
  open: boolean;
  onToggle: () => void;
  diagnostics: BookingDiagnosticsOut | null;
  result: BookingOut | null;
  lastReply: BookingReplyOut | null;
}

function mark(ok: boolean, pending = false): string {
  if (pending) return "⏳";
  return ok ? "✅" : "❌";
}

// Developer-only panel (Phase 8): proves the Telegram round-trip end to end
// without reading backend logs during the demo.
function BookingDiagnostics({
  open,
  onToggle,
  diagnostics,
  result,
  lastReply,
}: BookingDiagnosticsProps) {
  const messageId = result?.payload?.telegram_message_id ?? null;
  const booked = result?.status === "booked";
  const failed = result?.status === "failed";
  // A terminal booked/failed state necessarily means a reply was received and
  // parsed, even after the modal was reopened and the transient reply is gone.
  const replyReceived =
    booked || failed || Boolean(lastReply && lastReply.classification !== "none");
  const parsedClassification = booked
    ? "confirmed"
    : failed
      ? "unavailable"
      : (lastReply?.classification ?? "-");

  const checks: { label: string; badge: string; detail: string }[] = [
    {
      label: "Booking Request Generated",
      badge: mark(Boolean(result)),
      detail: result ? `Booking #${result.booking_id}` : "Not sent",
    },
    {
      label: "Telegram Message Sent",
      badge: mark(Boolean(messageId)),
      detail: messageId ? `Message ID ${messageId}` : "No message id",
    },
    {
      label: "Awaiting Workshop Reply",
      badge: mark(false, result?.status === "sent"),
      detail: result?.status === "sent" ? "Polling for reply" : "Not waiting",
    },
    {
      label: "Telegram Reply Received",
      badge: mark(replyReceived),
      detail: lastReply?.message ? lastReply.message : booked ? "Confirmed" : "No reply yet",
    },
    {
      label: "Reply Parsed",
      badge: mark(replyReceived),
      detail: parsedClassification,
    },
    {
      label: "Google Calendar Booking",
      badge: mark(booked),
      detail: booked ? "Event created" : "Pending",
    },
    {
      label: "UI Updated",
      badge: mark(Boolean(result) && result?.status !== "sent"),
      detail: result ? `State: ${result.status}` : "-",
    },
  ];

  return (
    <div className="booking-diagnostics">
      <button type="button" className="secondary-button" onClick={onToggle}>
        {open ? "Hide" : "Show"} developer diagnostics
      </button>
      {open ? (
        <div className="booking-diagnostics__body">
          <table className="diagnostics-table">
            <tbody>
              {checks.map((check) => (
                <tr key={check.label}>
                  <td>{check.badge}</td>
                  <td>{check.label}</td>
                  <td>{check.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="diagnostics-debug">
            <div>
              <dt>Telegram configured</dt>
              <dd>{diagnostics ? String(diagnostics.telegram_configured) : "-"}</dd>
            </div>
            <div>
              <dt>Booking ID</dt>
              <dd>{result?.booking_id ?? "-"}</dd>
            </div>
            <div>
              <dt>Message ID</dt>
              <dd>{messageId ?? "-"}</dd>
            </div>
            <div>
              <dt>Workflow state</dt>
              <dd>{result?.status ?? "IDLE"}</dd>
            </div>
            <div>
              <dt>Last reply</dt>
              <dd>{lastReply?.message ?? "-"}</dd>
            </div>
            <div>
              <dt>Retry round</dt>
              <dd>{lastReply?.round ?? 0}</dd>
            </div>
            <div>
              <dt>Proposed date / time</dt>
              <dd>
                {lastReply
                  ? `${lastReply.proposed_date} ${lastReply.proposed_time}`
                  : "-"}
              </dd>
            </div>
            <div>
              <dt>Calendar</dt>
              <dd>{diagnostics?.calendar_id ?? "-"}</dd>
            </div>
            <div>
              <dt>FreeBusy probe</dt>
              <dd>{diagnostics?.freebusy_probe ?? "-"}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </div>
  );
}

interface WorkshopSelectorProps {
  selectedWorkshop: RankedWorkshop;
  rankedWorkshops: RankedWorkshop[];
  onOpenPicker: () => void;
}

function WorkshopSelector({
  selectedWorkshop,
  onOpenPicker,
}: WorkshopSelectorProps) {
  return (
    <div className="workshop-field">
      <div className="field-label">Nearest workshop</div>
      <div className="workshop-summary">
        <div>
          <strong>{selectedWorkshop.name}</strong>
          <span>
            {formatDistanceKm(selectedWorkshop.distanceKm)} - {selectedWorkshop.area}
          </span>
        </div>
        <button type="button" className="secondary-button" onClick={onOpenPicker}>
          Change workshop
        </button>
      </div>
      <p>
        {currentVehicleLocation.label} - {currentVehicleLocation.area}
      </p>
    </div>
  );
}

interface WorkshopPickerProps {
  selectedWorkshop: RankedWorkshop;
  rankedWorkshops: RankedWorkshop[];
  onClosePicker: () => void;
  onSelectWorkshop: (workshop: RankedWorkshop) => void;
}

function WorkshopPicker({
  selectedWorkshop,
  rankedWorkshops,
  onClosePicker,
  onSelectWorkshop,
}: WorkshopPickerProps) {
  return (
    <section className="workshop-picker" role="dialog" aria-label="Select Mercedes centre">
      <div className="workshop-picker__header">
        <div>
          <span className="eyebrow">Closest official centres</span>
          <h3>Select Mercedes centre</h3>
        </div>
        <button type="button" className="icon-button" onClick={onClosePicker} aria-label="Close workshop map">
          x
        </button>
      </div>
      <div className="workshop-map" aria-hidden="true">
        <span className="map-grid" />
        <span className="vehicle-pin">CAR</span>
        {rankedWorkshops.map((workshop, index) => (
          <span
            key={workshop.id}
            className={`workshop-pin${workshop.id === selectedWorkshop.id ? " workshop-pin--active" : ""}`}
            style={{ left: `${workshop.mapX}%`, top: `${workshop.mapY}%` }}
          >
            {index + 1}
          </span>
        ))}
      </div>
      <div className="workshop-options">
        {rankedWorkshops.map((workshop) => (
          <button
            type="button"
            key={workshop.id}
            className={`workshop-option${workshop.id === selectedWorkshop.id ? " workshop-option--active" : ""}`}
            onClick={() => onSelectWorkshop(workshop)}
          >
            <span>
              <strong>{workshop.name}</strong>
              <small>{workshop.address}</small>
            </span>
            <em>
              Select {workshop.name} - {formatDistanceKm(workshop.distanceKm)}
            </em>
          </button>
        ))}
      </div>
    </section>
  );
}
