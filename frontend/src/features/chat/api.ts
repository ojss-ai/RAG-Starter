import { apiFetch, apiUrl, authHeaders } from "@/lib/api";
import { createSSEParser } from "@/lib/sse";
import type { ChatSession, Source } from "./types";

interface HistoryMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
}

export function listSessions(token: string | undefined): Promise<ChatSession[]> {
  return apiFetch<ChatSession[]>("/api/v1/chat/sessions", {}, token);
}

export function createSession(token: string | undefined): Promise<ChatSession> {
  return apiFetch<ChatSession>("/api/v1/chat/sessions", { method: "POST" }, token);
}

export function clearSession(id: string, token: string | undefined): Promise<void> {
  return apiFetch<void>(`/api/v1/chat/sessions/${id}`, { method: "DELETE" }, token);
}

export function fetchHistory(
  id: string,
  token: string | undefined,
): Promise<HistoryMessage[]> {
  return apiFetch<HistoryMessage[]>(`/api/v1/chat/history/${id}`, {}, token);
}

export interface StreamHandlers {
  onSession: (sessionId: string) => void;
  onToken: (token: string) => void;
  onSources: (sources: Source[]) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export async function streamChat(
  message: string,
  sessionId: string | undefined,
  token: string | undefined,
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`${apiUrl()}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ message, ...(sessionId ? { session_id: sessionId } : {}) }),
  });
  if (!response.ok || response.body === null) {
    handlers.onError(`stream failed (${response.status})`);
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const evt of parser.feed(decoder.decode(value, { stream: true }))) {
      if (evt.event === "session")
        handlers.onSession((evt.data as { session_id: string }).session_id);
      else if (evt.event === "token")
        handlers.onToken((evt.data as { t: string }).t);
      else if (evt.event === "sources") handlers.onSources(evt.data as Source[]);
      else if (evt.event === "done") handlers.onDone();
    }
  }
}
