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
