import { useEffect, useMemo, useState } from "react";
import {
  checkBookingReply,
  createBooking,
  getBookingAvailability,
  getDepreciation,
  getFaults,
  getHealth,
  getMarketComps,
  getObdSnapshot,
  isModelUnavailable,
  makeObdStreamUrl,
  predictObd,
  type BookingOut,
  type DepreciationOut,
  type FaultOut,
  type MarketCompsOut,
  type ObdSnapshotOut,
  type PredictOut,
  type VehicleProfile,
} from "./api/client";
import {
  demoCarFeatures,
  demoDepreciation,
  demoFaults,
  demoMarket,
  demoPrediction,
  demoProfile,
  demoSnapshot,
} from "./api/mockData";
import { AdvisoryModal } from "./components/AdvisoryModal";
import { BookingModal } from "./components/BookingModal";
import { ComponentDetail } from "./components/ComponentDetail";
import { ComponentDock } from "./components/ComponentDock";
import type { ComponentId } from "./components/componentConfig";
import { DepreciationChart } from "./components/DepreciationChart";
import { TelemetryRail } from "./components/TelemetryRail";
import { ValueHeader } from "./components/ValueHeader";
import { CarScene } from "./scene/CarScene";
import "./styles/theme.css";

type ApiStatus = "checking" | "online" | "offline";

interface DashboardState {
  profile: VehicleProfile | null;
  snapshot: ObdSnapshotOut | null;
  faults: FaultOut[];
  market: MarketCompsOut | null;
  prediction: PredictOut | null;
  depreciation: DepreciationOut | null;
  predictionUnavailable: boolean;
  depreciationUnavailable: boolean;
}

const initialDashboard: DashboardState = {
  profile: null,
  snapshot: null,
  faults: [],
  market: null,
  prediction: null,
  depreciation: null,
  predictionUnavailable: false,
  depreciationUnavailable: false,
};

const OBD_POLL_INTERVAL_MS = 5000;

function isOffline(error: unknown) {
  return !isModelUnavailable(error);
}

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [version, setVersion] = useState("");
  const [selectedComponent, setSelectedComponent] = useState<ComponentId>("engine");
  const [bookingOpen, setBookingOpen] = useState(false);
  const [activeBooking, setActiveBooking] = useState<BookingOut | null>(null);
  const [advisoryOpen, setAdvisoryOpen] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardState>(initialDashboard);

  useEffect(() => {
    getHealth()
      .then((health) => {
        setApiStatus("online");
        setVersion(health.version);
      })
      .catch(() => {
        setApiStatus("offline");
        setVersion("demo");
      });
  }, []);

  useEffect(() => {
    let active = true;

    async function loadDashboard() {
      const profile = demoProfile;

      const [snapshotResult, faultsResult, marketResult, predictionResult, depreciationResult] =
        await Promise.allSettled([
          getObdSnapshot(profile.id),
          getFaults(profile.id),
          getMarketComps(profile.model, profile.year),
          predictObd(demoCarFeatures),
          getDepreciation(profile.id, 5),
        ]);

      if (!active) return;

      const predictionUnavailable =
        predictionResult.status === "rejected" && isModelUnavailable(predictionResult.reason);
      const depreciationUnavailable =
        depreciationResult.status === "rejected" && isModelUnavailable(depreciationResult.reason);
      const anyOffline = [snapshotResult, faultsResult, marketResult, predictionResult, depreciationResult].some(
        (result) => result.status === "rejected" && isOffline(result.reason),
      );

      if (anyOffline) setApiStatus("offline");

      setDashboard({
        profile,
        snapshot: snapshotResult.status === "fulfilled" ? snapshotResult.value : demoSnapshot,
        faults: faultsResult.status === "fulfilled" ? faultsResult.value.faults : demoFaults.faults,
        market: marketResult.status === "fulfilled" ? marketResult.value : demoMarket,
        prediction:
          predictionResult.status === "fulfilled"
            ? predictionResult.value
            : predictionUnavailable
              ? null
              : demoPrediction,
        depreciation:
          depreciationResult.status === "fulfilled"
            ? depreciationResult.value
            : depreciationUnavailable
              ? null
              : demoDepreciation,
        predictionUnavailable,
        depreciationUnavailable,
      });
    }

    loadDashboard();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const profileId = dashboard.profile?.id;
    if (!profileId) return undefined;

    let active = true;
    let pollTimer: number | undefined;
    const startPolling = () => {
      if (pollTimer !== undefined) return;
      pollTimer = window.setInterval(() => {
        getObdSnapshot(profileId)
          .then((snapshot) => {
            if (active) {
              setDashboard((state) => ({ ...state, snapshot }));
            }
          })
          .catch(() => undefined);
      }, OBD_POLL_INTERVAL_MS);
    };

    if (typeof EventSource !== "undefined") {
      const stream = new EventSource(makeObdStreamUrl(profileId));
      stream.addEventListener("snapshot", (event) => {
        try {
          setDashboard((state) => ({ ...state, snapshot: JSON.parse((event as MessageEvent).data) }));
        } catch {
          // Ignore malformed stream events and keep the last known snapshot.
        }
      });
      stream.onerror = () => {
        stream.close();
        if (active) {
          startPolling();
        }
      };
      return () => {
        active = false;
        stream.close();
        if (pollTimer !== undefined) {
          window.clearInterval(pollTimer);
        }
      };
    }

    startPolling();

    return () => {
      active = false;
      if (pollTimer !== undefined) {
        window.clearInterval(pollTimer);
      }
    };
  }, [dashboard.profile?.id]);

  const apiLabel = useMemo(() => {
    if (apiStatus === "checking") return "Connecting";
    if (apiStatus === "online") return `API online - v${version}`;
    return "Demo mode";
  }, [apiStatus, version]);

  return (
    <main className="shell">
      <section className="dashboard-stage" aria-label="AssetIQ valuation dashboard">
        <div className="stage-border" />
        <header className="stage-topbar">
          <span className="wordmark">
            <span className="wordmark-spark" data-testid="wordmark-star" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M12 2.5l2.35 7.15 7.15 2.35-7.15 2.35L12 21.5l-2.35-7.15L2.5 12l7.15-2.35L12 2.5z" />
              </svg>
            </span>
            AssetIQ
            <span className="wordmark-sub">for Mercedes-Benz</span>
          </span>
          <span className={`api-pill api-pill--${apiStatus}`} data-testid="api-status">
            {apiLabel}
          </span>
        </header>

        <ValueHeader
          profile={dashboard.profile}
          prediction={dashboard.prediction}
          predictionUnavailable={dashboard.predictionUnavailable}
          market={dashboard.market}
        />

        <div className="orbit-hint">Drag to orbit - Scroll to zoom</div>
        <TelemetryRail snapshot={dashboard.snapshot} faults={dashboard.faults} />
        <ComponentDock selected={selectedComponent} onSelect={setSelectedComponent} />

        <section className="car-stage" aria-label="Interactive Mercedes 3D valuation model">
          <CarScene selected={selectedComponent} onSelect={setSelectedComponent} />
        </section>

        <ComponentDetail
          selected={selectedComponent}
          profile={dashboard.profile}
          snapshot={dashboard.snapshot}
          faults={dashboard.faults}
          market={dashboard.market}
        />

        <div className="cta-cluster">
          <div className="cta-actions">
            <button className="inspection-button" type="button" onClick={() => setBookingOpen(true)}>
              {activeBooking?.status === "sent"
                ? "Awaiting booking confirmation"
                : activeBooking?.status === "booked"
                  ? "Booked"
                  : "Book certified inspection"}
              <span>
                {activeBooking?.status === "sent"
                  ? `Booking #${activeBooking.booking_id}`
                  : activeBooking?.status === "booked"
                    ? "Confirmed"
                    : "Step 1 of 2"}
              </span>
            </button>
            <button className="advisory-button" type="button" onClick={() => setAdvisoryOpen(true)}>
              <span aria-hidden="true">AI</span>
              Advisory
            </button>
          </div>
          <p>Next official slot - Fri 10 Jul - Hap Seng Star KL</p>
        </div>

        <DepreciationChart
          points={dashboard.depreciation?.points ?? null}
          unavailable={dashboard.depreciationUnavailable}
        />
      </section>

      <BookingModal
        open={bookingOpen}
        profile={dashboard.profile}
        activeBooking={activeBooking}
        onBookingChange={setActiveBooking}
        onClose={() => setBookingOpen(false)}
        onSubmit={(form) =>
          createBooking({
            profile_id: dashboard.profile?.id ?? 1,
            ...form,
          })
        }
        onGetAvailability={getBookingAvailability}
        onCheckReply={checkBookingReply}
      />
      <AdvisoryModal
        open={advisoryOpen}
        profile={dashboard.profile}
        prediction={dashboard.prediction}
        depreciation={dashboard.depreciation?.points ?? null}
        snapshot={dashboard.snapshot}
        faults={dashboard.faults}
        market={dashboard.market}
        onClose={() => setAdvisoryOpen(false)}
        onBookInspection={() => {
          setAdvisoryOpen(false);
          setBookingOpen(true);
        }}
      />
    </main>
  );
}
