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
