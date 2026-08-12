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
