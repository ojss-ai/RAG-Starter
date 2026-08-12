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
