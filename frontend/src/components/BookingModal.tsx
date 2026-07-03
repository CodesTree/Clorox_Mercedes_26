import { useEffect, useMemo, useState } from "react";
import type { BookingOut, VehicleProfile } from "../api/client";
import {
  currentVehicleLocation,
  formatDistanceKm,
  getRankedWorkshops,
  type RankedWorkshop,
} from "./workshops";

interface BookingModalProps {
  open: boolean;
  profile: VehicleProfile | null;
  onClose: () => void;
  onSubmit: (form: {
    name: string;
    workshop: string;
    car_model: string;
    purpose: string;
    date: string;
    time: string;
  }) => Promise<BookingOut>;
}

const BOOKING_PURPOSE = "Certified inspection";

export function BookingModal({ open, profile, onClose, onSubmit }: BookingModalProps) {
  const [name, setName] = useState("");
  const [date, setDate] = useState("2026-07-10");
  const [time, setTime] = useState("10:00");
  const [status, setStatus] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
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

  useEffect(() => {
    if (!open) return;
    setSelectedWorkshopId(defaultWorkshopId);
    setPickerOpen(false);
    setStatus(null);
  }, [defaultWorkshopId, open]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="booking-modal" role="dialog" aria-modal="true" aria-label="Book inspection">
        <div className="modal-header">
          <div>
            <span className="eyebrow">Official Mercedes slot</span>
            <h2>Book certified inspection</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close booking">
            x
          </button>
        </div>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const result = await onSubmit({
              name,
              workshop,
              car_model: model,
              purpose: BOOKING_PURPOSE,
              date,
              time,
            });
            setStatus(result.dry_run ? "Dry-run booking saved" : "Booking dispatched");
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
              pickerOpen={pickerOpen}
              onOpenPicker={() => setPickerOpen(true)}
              onClosePicker={() => setPickerOpen(false)}
              onSelectWorkshop={(nextWorkshop) => {
                setSelectedWorkshopId(nextWorkshop.id);
                setPickerOpen(false);
              }}
            />
          ) : null}
          <label>
            Car model
            <input value={model} readOnly />
          </label>
          <label>
            Date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
          </label>
          <label>
            Time
            <input type="time" value={time} onChange={(event) => setTime(event.target.value)} required />
          </label>
          <button className="primary-button" type="submit">
            Submit booking
          </button>
        </form>
        {status ? <p className="modal-status">{status}</p> : null}
      </section>
    </div>
  );
}

interface WorkshopSelectorProps {
  selectedWorkshop: RankedWorkshop;
  rankedWorkshops: RankedWorkshop[];
  pickerOpen: boolean;
  onOpenPicker: () => void;
  onClosePicker: () => void;
  onSelectWorkshop: (workshop: RankedWorkshop) => void;
}

function WorkshopSelector({
  selectedWorkshop,
  rankedWorkshops,
  pickerOpen,
  onOpenPicker,
  onClosePicker,
  onSelectWorkshop,
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

      {pickerOpen ? (
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
      ) : null}
    </div>
  );
}
