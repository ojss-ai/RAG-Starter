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
