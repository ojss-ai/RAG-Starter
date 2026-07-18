import { statusRows } from "../format";
import type { Metrics } from "../types";

const BAR_H = 8; // thin mark
const ROW_H = 28;
const CHART_W = 260;

export function StatusBars({ metrics }: { metrics: Metrics }) {
  const rows = statusRows(metrics);
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        Documents by status
      </p>
      <div className="mt-3 space-y-1">
        {rows.map((row) => (
          <div key={row.status} className="flex items-center gap-3 text-sm">
            <span className="w-24 shrink-0 text-slate-300">{row.status}</span>
            <svg
              width={CHART_W}
              height={ROW_H}
              role="img"
              aria-label={`${row.status}: ${row.count} documents`}
              className="shrink-0"
            >
              <title>{`${row.status}: ${row.count}`}</title>
              {/* recessive track so zero-count rows still read as rows */}
              <rect x="0" y={(ROW_H - BAR_H) / 2} width={CHART_W} height={BAR_H}
                    rx="4" fill="#1e293b" />
              {row.count > 0 ? (
                <rect x="0" y={(ROW_H - BAR_H) / 2}
                      width={Math.max(BAR_H, row.fraction * CHART_W)} height={BAR_H}
                      rx="4" fill={row.color} />
              ) : null}
            </svg>
            <span className="tabular-nums text-slate-400">{row.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
