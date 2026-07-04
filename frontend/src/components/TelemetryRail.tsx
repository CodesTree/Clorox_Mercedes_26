import type { FaultOut, ObdSnapshotOut } from "../api/client";

interface TelemetryRailProps {
  snapshot: ObdSnapshotOut | null;
  faults: FaultOut[];
}

export function TelemetryRail({ snapshot, faults }: TelemetryRailProps) {
  return (
    <aside className="telemetry-rail" aria-label="Live OBD-II rail">
      <div className="rail-title">
        <span className="live-dot" />
        <span>Live OBD-II</span>
      </div>
      <div className="telemetry-stat">
        <span>Engine RPM</span>
        <strong>{snapshot?.rpm ?? "--"}</strong>
      </div>
      <div className="telemetry-stat">
        <span>Coolant C</span>
        <strong>{snapshot ? Math.round(snapshot.coolant_c) : "--"}</strong>
      </div>
      <div className="telemetry-stat">
        <span>Battery V</span>
        <strong>{snapshot ? snapshot.battery_v.toFixed(1) : "--"}</strong>
      </div>
      <div className="telemetry-stat">
        <span>Health</span>
        <strong className="health-value">
          {snapshot?.health ?? "--"}
          <small>/100</small>
        </strong>
      </div>
      <div className="telemetry-footnote">
        {faults.length} ODX signal{faults.length === 1 ? "" : "s"} - simulated stream
      </div>
    </aside>
  );
}
