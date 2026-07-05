import type { MarketCompsOut, PredictOut, VehicleProfile } from "../api/client";
import { formatCompactRm, formatRm } from "./format";

interface ValueHeaderProps {
  profile: VehicleProfile | null;
  prediction: PredictOut | null;
  predictionUnavailable: boolean;
  market: MarketCompsOut | null;
}

export function ValueHeader({ profile, prediction, predictionUnavailable, market }: ValueHeaderProps) {
  const delta = market?.delta_pct;

  return (
    <section className="value-header" aria-label="Valuation summary">
      <p className="eyebrow">Predicted resale value</p>
      <h1>{prediction ? formatRm(prediction.value_rm) : "Model not trained yet"}</h1>
      <p className="value-header__band">
        {prediction ? (
          <>
            {formatCompactRm(prediction.low_rm)} - {formatCompactRm(prediction.high_rm)} -{" "}
            {Math.round(prediction.confidence * 100)}% confidence
          </>
        ) : predictionUnavailable ? (
          "Train the ML model to activate live resale valuation"
        ) : (
          "Loading valuation signal"
        )}
        {delta !== null && delta !== undefined ? (
          <span className="market-delta">
            {delta >= 0 ? "▲ " : "▼ "}
            {Math.abs(delta * 100).toFixed(1)}% vs market
          </span>
        ) : null}
      </p>
      {profile ? (
        <p className="value-header__vehicle">
          {profile.year} - {profile.name} - {profile.mileage.toLocaleString()} km
        </p>
      ) : null}
    </section>
  );
}
