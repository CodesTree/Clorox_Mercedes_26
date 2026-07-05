import type { FaultOut, MarketCompsOut, ObdSnapshotOut, VehicleProfile } from "../api/client";
import { getComponent, type ComponentId } from "./componentConfig";
import { formatRm } from "./format";

interface ComponentDetailProps {
  selected: ComponentId;
  profile: VehicleProfile | null;
  snapshot: ObdSnapshotOut | null;
  faults: FaultOut[];
  market: MarketCompsOut | null;
}

export function ComponentDetail({
  selected,
  profile,
  snapshot,
  faults,
  market,
}: ComponentDetailProps) {
  const component = getComponent(selected);
  const impactClass = component.positive ? "impact-positive" : "impact-negative";

  return (
    <section
      key={component.id}
      className={`component-callout component-callout--${component.anchor}`}
      aria-label="Selected component detail"
    >
      <div className="component-callout__code">{component.code}</div>
      <div className="component-callout__main">
        <h2>{component.label}</h2>
        {selected === "engine" ? (
          <p>
            {profile?.engine_size.toFixed(1) ?? "--"}L {profile?.fuel_type ?? "powertrain"} -{" "}
            {snapshot ? `${snapshot.rpm} rpm` : "OBD pending"} - {profile?.transmission ?? "transmission pending"}
          </p>
        ) : null}
        {selected === "battery" ? (
          <p>
            Battery voltage {snapshot ? `${snapshot.battery_v.toFixed(1)} V` : "pending"} - coolant{" "}
            {snapshot ? `${Math.round(snapshot.coolant_c)} C` : "pending"}
          </p>
        ) : null}
        {selected === "brakes" ? (
          <p>
            Brakes and suspension inferred from health score {snapshot?.health ?? "--"}/100 and diagnostic signals.
          </p>
        ) : null}
        {selected === "fuel" ? (
          <p>
            {profile?.fuel_type ?? "Fuel type pending"} - {profile?.mpg ? `${profile.mpg} mpg` : "consumption pending"}
          </p>
        ) : null}
        {selected === "mileage" ? (
          <p>
            {snapshot ? snapshot.odo_km.toLocaleString() : "--"} km from OBD - profile{" "}
            {profile ? profile.mileage.toLocaleString() : "--"} km
          </p>
        ) : null}
        {selected === "diagnostics" ? (
          <div className="fault-summary">
            {faults.length ? (
              faults.map((fault) => (
                <p key={fault.code}>
                  <strong>{fault.code}</strong> - {fault.description} - {fault.severity} - {fault.system}
                </p>
              ))
            ) : (
              <p>No ODX faults returned</p>
            )}
          </div>
        ) : null}
        {selected === "service" ? (
          <p>
            {profile?.service_history_count ?? 0}/{profile?.service_history_total ?? profile?.service_history_max ?? "?"}{" "}
            records captured. Assumption adjustment only, not market truth.
          </p>
        ) : null}
        {selected !== "diagnostics" ? (
          <p className="component-callout__sub">
            {component.value} - {component.sub}
            {market?.median_rm ? ` - Market median ${formatRm(market.median_rm)}` : ""}
          </p>
        ) : null}
      </div>
      <strong className={`component-callout__impact ${impactClass}`}>{component.impact}</strong>
    </section>
  );
}
