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
