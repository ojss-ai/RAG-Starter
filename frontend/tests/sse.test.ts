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
