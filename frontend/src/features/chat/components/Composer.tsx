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
