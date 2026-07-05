import type { DepreciationPoint } from "../api/client";

interface DepreciationChartProps {
  points: DepreciationPoint[] | null;
  unavailable: boolean;
}

const fallbackPoints: DepreciationPoint[] = [
  { year: 2021, value_rm: 100, retained_pct: 1 },
  { year: 2023, value_rm: 68, retained_pct: 0.68 },
  { year: 2026, value_rm: 41, retained_pct: 0.41 },
  { year: 2028, value_rm: 36, retained_pct: 0.36 },
];

function makePath(points: DepreciationPoint[]) {
  const min = Math.min(...points.map((point) => point.retained_pct));
  const max = Math.max(...points.map((point) => point.retained_pct));
  const range = Math.max(0.01, max - min);
  return points
    .map((point, index) => {
      const x = 16 + index * (608 / Math.max(1, points.length - 1));
      const y = 12 + (1 - (point.retained_pct - min) / range) * 118;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

export function DepreciationChart({ points, unavailable }: DepreciationChartProps) {
  const data = points?.length ? points : fallbackPoints;
  const path = makePath(data);
  const current = data[Math.min(data.length - 1, Math.max(0, data.findIndex((point) => point.year >= 2026)))];
  const retained = Math.round((current?.retained_pct ?? 0.41) * 100);

  return (
    <section className="depreciation-panel" aria-label="Depreciation forecast">
      <div className="panel-heading">
        <span>Depreciation forecast</span>
        <strong>{retained}% retained</strong>
      </div>
      <svg width="100%" height="76" viewBox="0 0 640 150" preserveAspectRatio="none" role="img" aria-label="Retained value curve">
        <path d={`${path} L 624 148 L 16 148 Z`} className="chart-area" />
        <path d={path} className="chart-line" />
        <line x1="450" y1="10" x2="450" y2="146" className="chart-today" />
        <circle cx="450" cy="104" r="6" className="chart-dot" />
      </svg>
      <div className="chart-years">
        <span>2021</span>
        <span>2023</span>
        <span>Today</span>
        <span>2028</span>
      </div>
      {points?.length ? null : (
        <p className="panel-note">
          {unavailable ? "Forecast unavailable until the ML model is trained" : "Loading forecast"}
        </p>
      )}
    </section>
  );
}
