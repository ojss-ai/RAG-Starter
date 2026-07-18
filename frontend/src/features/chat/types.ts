export interface Source {
  n: number;
  document_id: string;
  chunk_id: string;
  filename: string;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  streaming?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}
