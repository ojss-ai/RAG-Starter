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
