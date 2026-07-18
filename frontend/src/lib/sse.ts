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
