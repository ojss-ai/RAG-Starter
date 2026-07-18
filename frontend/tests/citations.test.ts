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
