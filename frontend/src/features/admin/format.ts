import type { Metrics } from "./types";

/** Status display spec — dataviz skill: reserved status palette (validated on slate-900:
 * CVD pairs ≥12 ΔE, contrast ≥3:1); PENDING is a neutral queue state, not an alert, so it
 * wears neutral slate. Meaning never rides on color alone — every row is text-labeled. */
export const STATUS_ORDER = ["INDEXED", "PROCESSING", "PENDING", "FAILED"] as const;

export const STATUS_COLOR: Record<(typeof STATUS_ORDER)[number], string> = {
  INDEXED: "#0ca30c",   // good
  PROCESSING: "#fab219", // warning (in flight)
  PENDING: "#64748b",   // neutral slate-500
  FAILED: "#d03b3b",    // critical
};

export interface StatusRow {
  status: (typeof STATUS_ORDER)[number];
  count: number;
  fraction: number; // of the max row, for bar width
  color: string;
}

export function statusRows(metrics: Pick<Metrics, "documents_by_status">): StatusRow[] {
  const counts = STATUS_ORDER.map(
    (s) => [s, metrics.documents_by_status[s] ?? 0] as const,
  );
  const max = Math.max(1, ...counts.map(([, n]) => n));
  return counts.map(([status, count]) => ({
    status,
    count,
    fraction: count / max,
    color: STATUS_COLOR[status],
  }));
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatPercent(rate: number): string {
  return `${(rate * 100).toFixed(2)}%`;
}
