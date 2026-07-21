import type {
  DepreciationPoint,
  FaultOut,
  MarketCompsOut,
  ObdSnapshotOut,
  PredictOut,
  VehicleProfile,
} from "../api/client";
import { formatCompactRm, formatRm } from "./format";
import { VoiceAdvisor } from "./VoiceAdvisor";

interface AdvisoryModalProps {
  open: boolean;
  profile: VehicleProfile | null;
  prediction: PredictOut | null;
  depreciation: DepreciationPoint[] | null;
  snapshot: ObdSnapshotOut | null;
  faults: FaultOut[];
  market: MarketCompsOut | null;
  pendingVoiceAction: "greet" | "demo" | null;
  onPendingVoiceActionHandled: () => void;
  onClose: () => void;
  onBookInspection: () => void;
}

const repairBundle = [
  { label: "Battery health check", costRm: 4200, urgency: "Low" },
  { label: "Brake wear service", costRm: 7800, urgency: "Medium" },
  { label: "Cooling system inspection", costRm: 6400, urgency: "Medium" },
];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function AdvisoryModal({
  open,
  profile,
  prediction,
  depreciation,
  snapshot,
  faults,
  market,
  pendingVoiceAction,
  onPendingVoiceActionHandled,
  onClose,
  onBookInspection,
}: AdvisoryModalProps) {
  if (!open) return null;

  const totalRepairCost = repairBundle.reduce(
    (sum, item) => sum + item.costRm,
    0,
  );
  const currentValue = prediction?.value_rm ?? 738000;
  const comparisonMonths = 36;
  const comparisonPoint =
    depreciation?.[Math.min(depreciation.length - 1, 2)] ??
    ({
      year: 2028,
      value_rm: Math.round(currentValue * 0.86),
      retained_pct: 0.86,
    } satisfies DepreciationPoint);
  const depreciationLoss = Math.max(0, currentValue - comparisonPoint.value_rm);
  const advantage = Math.max(0, depreciationLoss - totalRepairCost);
  const health = snapshot?.health ?? 87;
  const confidence = clamp(
    Math.round((prediction?.confidence ?? 0.72) * 78 + health * 0.22),
    55,
    92,
  );
  const recommendation =
    advantage > 0 && health >= 65 ? "Sell or inspect first" : "Repair & keep";
  const marketSignal =
    market?.delta_pct !== null && market?.delta_pct !== undefined
      ? `${Math.abs(market.delta_pct * 100).toFixed(1)}% ${market.delta_pct >= 0 ? "above" : "below"} market`
      : "market signal pending";

  return (
    <div className="modal-backdrop advisory-backdrop" role="presentation">
      <section
        className="advisory-modal"
        role="dialog"
        aria-modal="true"
        aria-label="AssetIQ advisory"
      >
        <div className="modal-header advisory-modal__header">
          <div>
            <span className="wordmark advisory-wordmark">
              <span className="wordmark-spark" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path d="M12 2.5l2.35 7.15 7.15 2.35-7.15 2.35L12 21.5l-2.35-7.15L2.5 12l7.15-2.35L12 2.5z" />
                </svg>
              </span>
              AssetIQ Advisory
            </span>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close advisory"
          >
            x
          </button>
        </div>

        <VoiceAdvisor
          pendingVoiceAction={pendingVoiceAction}
          onPendingVoiceActionHandled={onPendingVoiceActionHandled}
        />

        <div className="advisory-hero">
          <div className="advisory-hero__badge" aria-hidden="true">
            <svg
              className="advisory-hero__emblem"
              viewBox="0 0 96 96"
              focusable="false"
            >
              <circle cx="48" cy="48" r="38" />
              <path d="M48 17v35" />
              <path d="M48 52 22 70" />
              <path d="M48 52 74 70" />
              <path d="M36 48 44 56 61 37" />
            </svg>
          </div>
          <div>
            <span className="eyebrow">Keep vs sell analysis</span>
            <h2>
              {recommendation} <span>for {comparisonMonths} months</span>
            </h2>
            <div className="advisory-metrics">
              <strong>{confidence}% confidence</strong>
              <strong>{formatCompactRm(40000)} advantage</strong>
              <span>{marketSignal}</span>
            </div>
          </div>
        </div>

        <div className="advisory-grid">
          <section
            className="advisory-card advisory-chart"
            aria-label="Repair cost versus vehicle value"
          >
            <h3>Repair Cost vs Vehicle Value</h3>
            <div className="advisory-chart__toolbar">
              <span>RM (Thousands)</span>
              <div className="advisory-chart__legend" aria-hidden="true">
                <span>
                  <i className="legend-resale" />
                  Resale value
                </span>
                <span>
                  <i className="legend-repair" />
                  Repair cost
                </span>
                <span>
                  <i className="legend-net" />
                  Net keep value
                </span>
              </div>
            </div>
            <svg
              viewBox="0 0 720 240"
              role="img"
              aria-label="Mock advisory value graph"
            >
              {[800, 600, 400, 200, 0].map((tick, index) => (
                <g key={tick}>
                  <line
                    x1="58"
                    x2="650"
                    y1={42 + index * 34}
                    y2={42 + index * 34}
                    className="advisory-grid-line"
                  />
                  <text x="24" y={47 + index * 34} className="advisory-tick">
                    {tick}
                  </text>
                </g>
              ))}
              {[0, 6, 12, 18, 24, 30, 36].map((month) => {
                const x = 58 + (month / 36) * 592;
                return (
                  <g key={month}>
                    <line
                      x1={x}
                      x2={x}
                      y1="42"
                      y2="178"
                      className="advisory-grid-line advisory-grid-line--vertical"
                    />
                    <text
                      x={x}
                      y="206"
                      textAnchor="middle"
                      className="advisory-tick"
                    >
                      {month}
                    </text>
                  </g>
                );
              })}

              <line
                x1="58"
                y1="178"
                x2="650"
                y2="178"
                className="advisory-axis"
              />
              <line
                x1="58"
                y1="42"
                x2="58"
                y2="178"
                className="advisory-axis"
              />
              <path
                d="M 58 53 C 150 64 202 84 264 96 C 352 112 424 128 492 139 C 550 149 602 154 650 158"
                className="advisory-line advisory-line--resale"
              />
              <path
                d="M 58 178 C 130 175 190 160 258 145 C 350 124 444 110 538 101 C 594 97 624 95 650 94"
                className="advisory-line advisory-line--repair"
              />
              <path
                d="M 58 67 C 154 82 232 102 300 116 C 382 134 460 151 532 165 C 586 175 622 182 650 187"
                className="advisory-line advisory-line--net"
              />

              <line
                x1="270"
                y1="42"
                x2="270"
                y2="178"
                className="advisory-review-line"
              />
              <circle cx="270" cy="96" r="8" className="advisory-dot" />
              <circle
                cx="270"
                cy="116"
                r="6"
                className="advisory-dot advisory-dot--muted"
              />
              <rect
                x="300"
                y="54"
                width="184"
                height="34"
                rx="8"
                className="advisory-callout-box"
              />
              <text x="316" y="76" className="advisory-callout">
                Break-even: Month 14
              </text>

              <text
                x="354"
                y="232"
                textAnchor="middle"
                className="advisory-axis-label advisory-axis-label--months"
              >
                Months
              </text>
            </svg>
          </section>

          <section
            className="advisory-card advisory-insight"
            aria-label="Gemini insight"
          >
            <div className="panel-heading">
              <span>Gemini insight</span>
            </div>
            <p>
              Repairing now is projected to protect resale value over the next{" "}
              {comparisonMonths} months. The estimated repair bundle is lower
              than the expected depreciation loss.
            </p>
            <p>
              Watch battery and brake wear first. Current vehicle health is{" "}
              {health}/100 with {faults.length} ODX signal
              {faults.length === 1 ? "" : "s"}.
            </p>
            <div className="advisory-tags">
              <span>Low short-term risk</span>
              <span>Service first</span>
              <span>Review at month 18</span>
            </div>
          </section>
        </div>

        <div className="advisory-actions">
          <button
            type="button"
            className="advisory-action"
            onClick={onBookInspection}
          >
            <strong>Book inspection</strong>
            <span>Schedule certified inspection at nearest workshop.</span>
          </button>
          <button
            type="button"
            className="advisory-action advisory-action--repair"
          >
            <strong>View repair priorities</strong>
            <span>
              {formatRm(totalRepairCost)} bundle from hard-coded telemetry
              assumptions.
            </span>
          </button>
          <button type="button" className="advisory-action">
            <strong>Book trade-in appointment</strong>
            <span>Compare trade-in timing against repair costs.</span>
          </button>
        </div>

        <div className="advisory-footnote">
          {profile
            ? `${profile.year} ${profile.name}`
            : "Demo Mercedes profile"}{" "}
          - mock advisory output for frontend review
        </div>
      </section>
    </div>
  );
}
