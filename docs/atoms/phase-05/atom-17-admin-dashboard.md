# atom-17-admin-dashboard

- Status: COMMITTED
- Phase: phase-05-clients (`docs/plans/phase-05-clients.md`, item §05.4)
- Traces: FR-6 (UI), FR-7 (UI), FR-20 (UI)
- Depends on: atom-16
- Mode: normal
- Created: 2026-07-12

## Purpose

The admin dashboard exists (admin-only route): metric stat tiles (documents, vectors, error
rate), a documents-by-status breakdown (dataviz-skill compliant: status palette validated on
the dark surface — CVD ΔE 16.4, contrast ≥3:1 — every bar direct-labeled with text + count,
never color alone; thin marks, rounded data ends, per-mark hover), a drag-drop upload zone
(single files + zip), and the searchable paginated document ledger with confirm-delete.

## Files

| Path | Action |
|---|---|
| `frontend/src/features/admin/types.ts`, `api.ts`, `format.ts` | create |
| `frontend/src/features/admin/hooks/useMetrics.ts`, `useDocuments.ts` | create |
| `frontend/src/features/admin/components/StatTile.tsx`, `StatusBars.tsx`, `UploadDropzone.tsx`, `DocumentTable.tsx`, `AdminDashboard.tsx` | create |
| `frontend/app/admin/layout.tsx`, `app/admin/page.tsx` | create |
| `frontend/tests/admin.test.ts` | create |

## Implementation

```typescript file=frontend/src/features/admin/types.ts
export interface Metrics {
  documents_by_status: Record<string, number>;
  documents_total: number;
  chunks_total: number;
  vector_backend: string;
  vectors_total: number;
  http_requests: number;
  http_errors: number;
  error_rate: number;
}

export interface DocumentRow {
  id: string;
  filename: string;
  status: "PENDING" | "PROCESSING" | "INDEXED" | "FAILED";
  error: string | null;
  size_bytes: number;
  created_at: string;
}

export interface DocumentList {
  total: number;
  documents: DocumentRow[];
}

export interface UploadResult {
  documents: Array<{ id: string; filename: string; status: string; duplicate: boolean }>;
  rejected: string[];
}
```

```typescript file=frontend/src/features/admin/api.ts
import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/token";
import type { DocumentList, Metrics, UploadResult } from "./types";

export function fetchMetrics(): Promise<Metrics> {
  return apiFetch<Metrics>("/api/v1/admin/metrics", {}, getToken());
}

export function fetchDocuments(
  q: string,
  offset: number,
  limit: number,
): Promise<DocumentList> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q) params.set("q", q);
  return apiFetch<DocumentList>(`/api/v1/admin/documents?${params}`, {}, getToken());
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/admin/documents/${id}`, { method: "DELETE" }, getToken());
}

export function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<UploadResult>("/api/v1/admin/upload", { method: "POST", body: form },
    getToken());
}
```

```typescript file=frontend/src/features/admin/format.ts
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
```

```typescript file=frontend/src/features/admin/hooks/useMetrics.ts
"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchMetrics } from "../api";
import type { Metrics } from "../types";

export function useMetrics(refreshMs = 10_000): {
  metrics: Metrics | undefined;
  refresh: () => Promise<void>;
} {
  const [metrics, setMetrics] = useState<Metrics | undefined>(undefined);

  const refresh = useCallback(async () => {
    setMetrics(await fetchMetrics());
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), refreshMs);
    return () => clearInterval(timer);
  }, [refresh, refreshMs]);

  return { metrics, refresh };
}
```

```typescript file=frontend/src/features/admin/hooks/useDocuments.ts
"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteDocument, fetchDocuments, uploadFile } from "../api";
import type { DocumentRow, UploadResult } from "../types";

const PAGE_SIZE = 20;

export interface UseDocuments {
  documents: DocumentRow[];
  total: number;
  page: number;
  pages: number;
  query: string;
  setQuery: (q: string) => void;
  setPage: (p: number) => void;
  remove: (id: string) => Promise<void>;
  upload: (files: FileList | File[]) => Promise<UploadResult[]>;
  refresh: () => Promise<void>;
}

export function useDocuments(): UseDocuments {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [query, setQueryState] = useState("");

  const refresh = useCallback(async () => {
    const list = await fetchDocuments(query, page * PAGE_SIZE, PAGE_SIZE);
    setDocuments(list.documents);
    setTotal(list.total);
  }, [query, page]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setQuery = useCallback((q: string) => {
    setQueryState(q);
    setPage(0);
  }, []);

  const remove = useCallback(
    async (id: string) => {
      await deleteDocument(id);
      await refresh();
    },
    [refresh],
  );

  const upload = useCallback(
    async (files: FileList | File[]) => {
      const results: UploadResult[] = [];
      for (const file of Array.from(files)) {
        results.push(await uploadFile(file));
      }
      await refresh();
      return results;
    },
    [refresh],
  );

  return {
    documents,
    total,
    page,
    pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
    query,
    setQuery,
    setPage,
    remove,
    upload,
    refresh,
  };
}
```

```tsx file=frontend/src/features/admin/components/StatTile.tsx
export function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string | undefined; // exactOptionalPropertyTypes: callers pass explicit undefined
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-100">{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}
```

```tsx file=frontend/src/features/admin/components/StatusBars.tsx
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
```

```tsx file=frontend/src/features/admin/components/UploadDropzone.tsx
"use client";

import { useRef, useState, type DragEvent } from "react";
import type { UploadResult } from "../types";

export function UploadDropzone({
  onUpload,
}: {
  onUpload: (files: FileList | File[]) => Promise<UploadResult[]>;
}) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<string | undefined>(undefined);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handle(files: FileList | File[]) {
    setBusy(true);
    setReport(undefined);
    try {
      const results = await onUpload(files);
      const accepted = results.reduce((n, r) => n + r.documents.length, 0);
      const dups = results.reduce(
        (n, r) => n + r.documents.filter((d) => d.duplicate).length, 0);
      const rejected = results.flatMap((r) => r.rejected);
      setReport(
        `${accepted} accepted${dups ? ` (${dups} duplicate)` : ""}` +
          (rejected.length ? ` · rejected: ${rejected.join(", ")}` : ""),
      );
    } catch (err) {
      setReport(err instanceof Error ? err.message : "upload failed");
    } finally {
      setBusy(false);
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length > 0) void handle(event.dataTransfer.files);
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`rounded-xl border-2 border-dashed p-6 text-center text-sm transition-colors ${
        dragging ? "border-sky-500 bg-sky-950/30" : "border-slate-700 bg-slate-900/40"
      }`}
    >
      <p className="text-slate-300">
        Drop PDF / TXT / MD files or a .zip batch here, or{" "}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="font-semibold text-sky-400 hover:underline"
          disabled={busy}
        >
          browse
        </button>
      </p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.md,.zip"
        className="hidden"
        aria-label="Upload documents"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) void handle(e.target.files);
          e.target.value = "";
        }}
      />
      {busy ? <p className="mt-2 text-xs text-slate-400">Uploading…</p> : null}
      {report ? <p className="mt-2 text-xs text-slate-400">{report}</p> : null}
    </div>
  );
}
```

```tsx file=frontend/src/features/admin/components/DocumentTable.tsx
"use client";

import { useState } from "react";
import { STATUS_COLOR, formatBytes } from "../format";
import type { DocumentRow } from "../types";
import type { UseDocuments } from "../hooks/useDocuments";

function StatusBadge({ status, error }: { status: DocumentRow["status"]; error: string | null }) {
  return (
    <span className="inline-flex items-center gap-1.5" title={error ?? undefined}>
      <span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLOR[status] }} />
      <span className="text-xs text-slate-300">{status}</span>
    </span>
  );
}

export function DocumentTable({ docs }: { docs: UseDocuments }) {
  const [confirming, setConfirming] = useState<string | undefined>(undefined);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900">
      <div className="flex items-center gap-3 border-b border-slate-800 p-3">
        <input
          value={docs.query}
          onChange={(e) => docs.setQuery(e.target.value)}
          placeholder="Search filenames…"
          aria-label="Search documents"
          className="w-64 rounded border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm outline-none focus:border-slate-400"
        />
        <span className="ml-auto text-xs text-slate-500">{docs.total} documents</span>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2 font-medium">File</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Size</th>
            <th className="px-3 py-2 font-medium">Added</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {docs.documents.map((d) => (
            <tr key={d.id} className="border-t border-slate-800/60 hover:bg-slate-800/30">
              <td className="max-w-xs truncate px-3 py-2 text-slate-200" title={d.filename}>
                {d.filename}
              </td>
              <td className="px-3 py-2"><StatusBadge status={d.status} error={d.error} /></td>
              <td className="px-3 py-2 tabular-nums text-slate-400">
                {formatBytes(d.size_bytes)}
              </td>
              <td className="px-3 py-2 text-slate-400">
                {new Date(d.created_at).toLocaleString()}
              </td>
              <td className="px-3 py-2 text-right">
                {confirming === d.id ? (
                  <span className="space-x-2 text-xs">
                    <button onClick={() => void docs.remove(d.id)}
                            className="font-semibold text-red-400 hover:underline">
                      Confirm delete
                    </button>
                    <button onClick={() => setConfirming(undefined)}
                            className="text-slate-400 hover:underline">
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirming(d.id)}
                    aria-label={`Delete ${d.filename}`}
                    className="text-xs text-slate-500 hover:text-red-400"
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
          {docs.documents.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-3 py-8 text-center text-sm text-slate-500">
                No documents{docs.query ? " match the search" : " yet — upload some above"}.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
      <div className="flex items-center justify-end gap-2 border-t border-slate-800 p-2 text-xs">
        <button onClick={() => docs.setPage(Math.max(0, docs.page - 1))}
                disabled={docs.page === 0}
                className="rounded px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40">
          ← Prev
        </button>
        <span className="text-slate-500">page {docs.page + 1} / {docs.pages}</span>
        <button onClick={() => docs.setPage(Math.min(docs.pages - 1, docs.page + 1))}
                disabled={docs.page >= docs.pages - 1}
                className="rounded px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40">
          Next →
        </button>
      </div>
    </div>
  );
}
```

```tsx file=frontend/src/features/admin/components/AdminDashboard.tsx
"use client";

import { formatPercent } from "../format";
import { useDocuments } from "../hooks/useDocuments";
import { useMetrics } from "../hooks/useMetrics";
import { DocumentTable } from "./DocumentTable";
import { StatTile } from "./StatTile";
import { StatusBars } from "./StatusBars";
import { UploadDropzone } from "./UploadDropzone";

export function AdminDashboard() {
  const { metrics, refresh } = useMetrics();
  const docs = useDocuments();

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <h1 className="text-lg font-semibold">Admin dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Documents" value={String(metrics?.documents_total ?? "—")}
                  sub={`${metrics?.chunks_total ?? 0} chunks`} />
        <StatTile label="Vectors" value={String(metrics?.vectors_total ?? "—")}
                  sub={metrics ? `backend: ${metrics.vector_backend}` : undefined} />
        <StatTile label="API error rate"
                  value={metrics ? formatPercent(metrics.error_rate) : "—"}
                  sub={metrics ? `${metrics.http_errors} of ${metrics.http_requests} requests` : undefined} />
        {metrics ? <StatusBars metrics={metrics} /> : <div />}
      </div>
      <UploadDropzone
        onUpload={async (files) => {
          const results = await docs.upload(files);
          await refresh();
          return results;
        }}
      />
      <DocumentTable docs={docs} />
    </main>
  );
}
```

```tsx file=frontend/app/admin/layout.tsx
import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { Nav } from "@/components/Nav";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard adminOnly>
      <div className="flex min-h-screen flex-col">
        <Nav />
        {children}
      </div>
    </AuthGuard>
  );
}
```

```tsx file=frontend/app/admin/page.tsx
import { AdminDashboard } from "@/features/admin/components/AdminDashboard";

export default function AdminPage() {
  return <AdminDashboard />;
}
```

## Tests (normal mode: must exist before validate)

```typescript file=frontend/tests/admin.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  STATUS_ORDER,
  formatBytes,
  formatPercent,
  statusRows,
} from "../src/features/admin/format";

test("statusRows fixed order, fractions of max, colors attached", () => {
  const rows = statusRows({
    documents_by_status: { INDEXED: 8, FAILED: 2, PENDING: 0 },
  });
  assert.deepEqual(rows.map((r) => r.status), [...STATUS_ORDER]);
  const indexed = rows.find((r) => r.status === "INDEXED");
  const failed = rows.find((r) => r.status === "FAILED");
  assert.equal(indexed?.fraction, 1);
  assert.equal(failed?.fraction, 0.25);
  assert.equal(rows.find((r) => r.status === "PROCESSING")?.count, 0);
  assert.ok(rows.every((r) => r.color.startsWith("#")));
});

test("statusRows empty corpus never divides by zero", () => {
  const rows = statusRows({ documents_by_status: {} });
  assert.ok(rows.every((r) => r.fraction === 0 && r.count === 0));
});

test("formatBytes and formatPercent", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(2048), "2.0 KB");
  assert.equal(formatBytes(5 * 1024 * 1024), "5.0 MB");
  assert.equal(formatPercent(0.0123), "1.23%");
  assert.equal(formatPercent(0), "0.00%");
});
```

Notes: dataviz compliance recap — stat values wear text ink (slate-100), never series color;
the breakdown is one measure on one implicit axis; bars are 8px thin with 4px rounded data
ends on a recessive track; every row pairs color with a text label + count (status is never
color-alone; FAILED rows expose `error` via badge tooltip in the ledger); `<title>` gives
per-mark hover. Zero-count rows keep their track so the set of states stays legible.

## Verification

1. `cd frontend && npm run typecheck && npm test && npm run build` → green.
2. Manual: as admin — tiles populate, status bars match ledger counts, drag-drop a zip → report line + ledger refresh, delete with confirm works; as plain user — /admin redirects to /chat.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (metrics/documents/upload API shapes match atoms 09/10 as landed: MetricsOut fields, DocumentList {total, documents}, UploadResponse {documents, rejected}; apiFetch FormData path exists), completeness ✓, traceability ✓ (FR-6/7/20 UI / plan §05.4). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom. One deviation (atom updated): StatTile `sub?: string`
  rejects explicit undefined under exactOptionalPropertyTypes; widened to
  `string | undefined`. Oracle: `tsc --noEmit` clean, `npm test` 12/12, `next build`
  clean with /admin, /chat, /login routes.
- 2026-07-17 — VALIDATED. All oracle legs green; status palette + direct labels per
  dataviz notes; admin-only guard wired via AuthGuard adminOnly. No OPEN findings.
  review-change clean.
