import assert from "node:assert/strict";
import { test } from "node:test";
import { authHeaders, extractDetail } from "../src/lib/api";

test("authHeaders with and without token", () => {
  assert.deepEqual(authHeaders("abc"), { Authorization: "Bearer abc" });
  assert.deepEqual(authHeaders(undefined), {});
});

test("extractDetail reads FastAPI error shape", () => {
  assert.equal(extractDetail({ detail: "Invalid credentials" }, "x"), "Invalid credentials");
  assert.equal(extractDetail({ detail: { nested: true } }, "fallback"), "fallback");
  assert.equal(extractDetail(undefined, "fallback"), "fallback");
  assert.equal(extractDetail("weird", "fallback"), "fallback");
});
