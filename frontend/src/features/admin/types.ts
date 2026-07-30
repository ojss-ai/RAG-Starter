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
