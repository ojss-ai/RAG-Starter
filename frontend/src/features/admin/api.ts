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
