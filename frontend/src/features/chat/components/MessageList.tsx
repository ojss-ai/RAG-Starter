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
