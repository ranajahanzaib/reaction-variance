export const pct = (v: number | null | undefined) =>
  v == null ? "Unavailable" : `${v.toFixed(1)}%`;
