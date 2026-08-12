# atom-16-chat-ui

- Status: COMMITTED
- Phase: phase-05-clients (`docs/plans/phase-05-clients.md`, item §05.3)
- Traces: FR-9 (UI), FR-10 (UI), FR-11 (UI)
- Depends on: atom-15
- Mode: normal
- Created: 2026-07-12

## Purpose

The chat surface exists: SSE tokens render live into the transcript, inline `[n]` citations
become interactive chips resolving to source metadata (filename + snippet on hover), and the
session sidebar lists, creates, and clears sessions. All chat logic lives in `useChat`;
components stay presentational (react skill).

## Files

| Path | Action |
|---|---|
| `frontend/src/lib/sse.ts` | create |
| `frontend/src/features/chat/types.ts`, `api.ts`, `hooks/useChat.ts` | create |
| `frontend/src/features/chat/components/CitationText.tsx`, `MessageList.tsx`, `Composer.tsx`, `SessionSidebar.tsx`, `ChatWindow.tsx` | create |
| `frontend/app/chat/layout.tsx`, `app/chat/page.tsx` | create |
| `frontend/tests/sse.test.ts`, `tests/citations.test.ts` | create |

## Implementation

```typescript file=frontend/src/lib/sse.ts
export interface SSEEvent {
  event: string;
  data: unknown;
}

export interface SSEParser {
  feed: (chunk: string) => SSEEvent[];
}

/** Incremental SSE frame parser: frames are separated by a blank line; each frame has
 * `event:` and `data:` lines. Partial frames stay buffered until complete. */
export function createSSEParser(): SSEParser {
  let buffer = "";
  return {
    feed(chunk: string): SSEEvent[] {
      buffer += chunk;
      const events: SSEEvent[] = [];
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        let event = "message";
        let data = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event: ")) event = line.slice(7);
          else if (line.startsWith("data: ")) data += line.slice(6);
        }
        if (data === "") continue;
        try {
          events.push({ event, data: JSON.parse(data) as unknown });
        } catch {
          events.push({ event, data });
        }
      }
      return events;
    },
  };
}
```

```typescript file=frontend/src/features/chat/types.ts
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
```

```typescript file=frontend/src/features/chat/api.ts
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
```

```typescript file=frontend/src/features/chat/hooks/useChat.ts
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/token";
import {
  clearSession,
  createSession,
  fetchHistory,
  listSessions,
  streamChat,
} from "../api";
import type { ChatMessage, ChatSession } from "./../types";

export interface UseChat {
  sessions: ChatSession[];
  activeId: string | undefined;
  messages: ChatMessage[];
  streaming: boolean;
  error: string | undefined;
  send: (text: string) => Promise<void>;
  select: (id: string) => Promise<void>;
  startNew: () => void;
  clear: (id: string) => Promise<void>;
}

let localId = 0;
const nextId = (): string => `local-${++localId}`;

export function useChat(): UseChat {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const activeRef = useRef<string | undefined>(undefined);

  const refreshSessions = useCallback(async () => {
    setSessions(await listSessions(getToken()));
  }, []);

  useEffect(() => {
    refreshSessions().catch(() => setError("could not load sessions"));
  }, [refreshSessions]);

  const select = useCallback(async (id: string) => {
    setActiveId(id);
    activeRef.current = id;
    const history = await fetchHistory(id, getToken());
    setMessages(
      history.map((m) => ({
        id: String(m.id),
        role: m.role,
        content: m.content,
        sources: m.sources,
      })),
    );
  }, []);

  const startNew = useCallback(() => {
    setActiveId(undefined);
    activeRef.current = undefined;
    setMessages([]);
  }, []);

  const clear = useCallback(
    async (id: string) => {
      await clearSession(id, getToken());
      if (activeRef.current === id) startNew();
      await refreshSessions();
    },
    [refreshSessions, startNew],
  );

  const send = useCallback(
    async (text: string) => {
      if (streaming || text.trim() === "") return;
      setError(undefined);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: text, sources: [] },
        { id: nextId(), role: "assistant", content: "", sources: [], streaming: true },
      ]);
      setStreaming(true);
      try {
        await streamChat(text, activeRef.current, getToken(), {
          onSession: (sessionId) => {
            if (!activeRef.current) {
              activeRef.current = sessionId;
              setActiveId(sessionId);
              void refreshSessions();
            }
          },
          onToken: (t) =>
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last) return prev;
              return [...prev.slice(0, -1), { ...last, content: last.content + t }];
            }),
          onSources: (sources) =>
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last) return prev;
              return [...prev.slice(0, -1), { ...last, sources }];
            }),
          onDone: () =>
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last) return prev;
              return [...prev.slice(0, -1), { ...last, streaming: false }];
            }),
          onError: setError,
        });
      } finally {
        setStreaming(false);
      }
    },
    [streaming, refreshSessions],
  );

  return { sessions, activeId, messages, streaming, error, send, select, startNew, clear };
}
```

```tsx file=frontend/src/features/chat/components/CitationText.tsx
import type { ReactNode } from "react";
import type { Source } from "../types";

export function splitCitations(text: string): Array<string | number> {
  const parts: Array<string | number> = [];
  const re = /\[(\d+)\]/g;
  let last = 0;
  for (let m = re.exec(text); m !== null; m = re.exec(text)) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(Number(m[1]));
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function CitationText({ text, sources }: { text: string; sources: Source[] }) {
  const parts = splitCitations(text);
  return (
    <span className="whitespace-pre-wrap">
      {parts.map((part, i) =>
        typeof part === "string" ? (
          <span key={`t-${i}`}>{part}</span>
        ) : (
          <CitationChip key={`c-${i}`} n={part} source={sources.find((s) => s.n === part)} />
        ),
      )}
    </span>
  );
}

function CitationChip({ n, source }: { n: number; source: Source | undefined }): ReactNode {
  return (
    <span className="group relative inline-block">
      <sup className="mx-0.5 cursor-help rounded bg-sky-900/80 px-1 py-0.5 text-[10px] font-semibold text-sky-200">
        {n}
      </sup>
      {source ? (
        <span className="pointer-events-none absolute bottom-full left-0 z-10 hidden w-72 rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs shadow-xl group-hover:block">
          <span className="mb-1 block font-semibold text-sky-300">{source.filename}</span>
          <span className="block text-slate-300">{source.snippet}…</span>
        </span>
      ) : null}
    </span>
  );
}
```

```tsx file=frontend/src/features/chat/components/MessageList.tsx
"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { CitationText } from "./CitationText";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.length === 0 ? (
        <p className="mt-16 text-center text-sm text-slate-500">
          Ask anything about your documents — answers cite their sources.
        </p>
      ) : null}
      {messages.map((m) => (
        <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex"}>
          <div
            className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user" ? "bg-sky-800 text-white" : "bg-slate-800 text-slate-100"
            }`}
          >
            <CitationText text={m.content} sources={m.sources} />
            {m.streaming === true ? (
              <span className="ml-1 inline-block h-3 w-1.5 animate-pulse bg-slate-400" />
            ) : null}
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
```

```tsx file=frontend/src/features/chat/components/Composer.tsx
"use client";

import { useState, type FormEvent } from "react";

export function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (text.trim() === "") return;
    onSend(text);
    setText("");
  }

  return (
    <form onSubmit={submit} className="flex gap-2 border-t border-slate-800 p-3">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ask a question…"
        aria-label="Chat message"
        className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-slate-400"
      />
      <button
        type="submit"
        disabled={disabled}
        className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}
```

```tsx file=frontend/src/features/chat/components/SessionSidebar.tsx
"use client";

import type { ChatSession } from "../types";

export function SessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onClear,
}: {
  sessions: ChatSession[];
  activeId: string | undefined;
  onSelect: (id: string) => void;
  onNew: () => void;
  onClear: (id: string) => void;
}) {
  return (
    <aside className="flex w-64 flex-col border-r border-slate-800 bg-slate-900/60">
      <button
        onClick={onNew}
        className="m-3 rounded-lg border border-slate-700 py-2 text-sm font-medium hover:bg-slate-800"
      >
        + New chat
      </button>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`group flex items-center rounded-lg text-sm ${
              s.id === activeId ? "bg-slate-800" : "hover:bg-slate-800/60"
            }`}
          >
            <button
              onClick={() => onSelect(s.id)}
              className="flex-1 truncate px-3 py-2 text-left text-slate-200"
              title={s.title}
            >
              {s.title}
            </button>
            <button
              onClick={() => onClear(s.id)}
              aria-label={`Clear session ${s.title}`}
              className="hidden px-2 text-slate-500 hover:text-red-400 group-hover:block"
            >
              ✕
            </button>
          </div>
        ))}
      </nav>
    </aside>
  );
}
```

```tsx file=frontend/src/features/chat/components/ChatWindow.tsx
"use client";

import { useChat } from "../hooks/useChat";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { SessionSidebar } from "./SessionSidebar";

export function ChatWindow() {
  const chat = useChat();

  return (
    <div className="flex min-h-0 flex-1">
      <SessionSidebar
        sessions={chat.sessions}
        activeId={chat.activeId}
        onSelect={(id) => void chat.select(id)}
        onNew={chat.startNew}
        onClear={(id) => void chat.clear(id)}
      />
      <section className="flex min-w-0 flex-1 flex-col">
        <MessageList messages={chat.messages} />
        {chat.error ? (
          <p className="px-4 py-1 text-xs text-red-400">{chat.error}</p>
        ) : null}
        <Composer disabled={chat.streaming} onSend={(t) => void chat.send(t)} />
      </section>
    </div>
  );
}
```

```tsx file=frontend/app/chat/layout.tsx
import type { ReactNode } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { Nav } from "@/components/Nav";

export default function ChatLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex h-screen flex-col">
        <Nav />
        {children}
      </div>
    </AuthGuard>
  );
}
```

```tsx file=frontend/app/chat/page.tsx
import { ChatWindow } from "@/features/chat/components/ChatWindow";

export default function ChatPage() {
  return <ChatWindow />;
}
```

## Tests (normal mode: must exist before validate)

```typescript file=frontend/tests/sse.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { createSSEParser } from "../src/lib/sse";

test("parses complete frames", () => {
  const p = createSSEParser();
  const events = p.feed('event: token\ndata: {"t":"hi "}\n\nevent: done\ndata: {}\n\n');
  assert.deepEqual(events, [
    { event: "token", data: { t: "hi " } },
    { event: "done", data: {} },
  ]);
});

test("buffers partial frames across feeds", () => {
  const p = createSSEParser();
  assert.deepEqual(p.feed('event: token\ndata: {"t":"he'), []);
  const events = p.feed('llo"}\n\n');
  assert.deepEqual(events, [{ event: "token", data: { t: "hello" } }]);
});

test("sources event carries arrays", () => {
  const p = createSSEParser();
  const [evt] = p.feed(
    'event: sources\ndata: [{"n":1,"filename":"a.txt","document_id":"d","chunk_id":"c","snippet":"s"}]\n\n',
  );
  assert.equal(evt?.event, "sources");
  assert.equal((evt?.data as Array<{ n: number }>)[0]?.n, 1);
});

test("non-JSON data falls back to string", () => {
  const p = createSSEParser();
  assert.deepEqual(p.feed("event: raw\ndata: plain\n\n"), [
    { event: "raw", data: "plain" },
  ]);
});
```

```typescript file=frontend/tests/citations.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { splitCitations } from "../src/features/chat/components/CitationText";

test("splits text and citation markers", () => {
  assert.deepEqual(splitCitations("Answer per [1] and [2]."), [
    "Answer per ",
    1,
    " and ",
    2,
    ".",
  ]);
});

test("no markers → single text part", () => {
  assert.deepEqual(splitCitations("plain answer"), ["plain answer"]);
});

test("adjacent and leading markers", () => {
  assert.deepEqual(splitCitations("[1][2] combined"), [1, 2, " combined"]);
});
```

Notes: `useChat` keeps the active session in a ref as well as state — the stream's
`onSession` callback fires inside the fetch loop where state would be stale. The
citation hover panel is pure CSS (`group-hover`) — no portal/library needed.

## Verification

1. `cd frontend && npm run typecheck && npm test && npm run build` → green.
2. Manual: with API + seeded docs: send a question → tokens stream live, `[1]` chips hover to source snippets, sidebar lists the session, ✕ clears it.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (SSE contract matches atom-12 as landed: session/token/sources/done events, {"t": ...} token shape; sessions API matches atom-13; lib/api + token helpers as landed in atom-15), completeness ✓, traceability ✓ (FR-9/10/11 UI / plan §05.3). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom, zero deviations. Oracle: `tsc --noEmit` clean,
  `npm test` 9/9 (sse parser incl. partial-frame buffering; citation splitting),
  `next build` clean (/chat route present).
- 2026-07-17 — VALIDATED. All oracle legs green; SSE parser verified against the exact
  frame format the backend emits (tested in atom-12). No OPEN findings. review-change clean.
