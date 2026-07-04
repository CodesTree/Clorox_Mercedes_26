const rm = new Intl.NumberFormat("en-MY", {
  style: "currency",
  currency: "MYR",
  maximumFractionDigits: 0,
});

export function formatRm(value: number) {
  return rm.format(value).replace("MYR", "RM");
}

export function formatCompactRm(value: number) {
  if (value >= 1000000) return `RM ${(value / 1000000).toFixed(1)}M`;
  return `RM ${Math.round(value / 1000)}K`;
}
