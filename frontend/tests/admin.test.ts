import assert from "node:assert/strict";
import { test } from "node:test";
import {
  STATUS_ORDER,
  formatBytes,
  formatPercent,
  statusRows,
} from "../src/features/admin/format";

test("statusRows fixed order, fractions of max, colors attached", () => {
  const rows = statusRows({
    documents_by_status: { INDEXED: 8, FAILED: 2, PENDING: 0 },
  });
  assert.deepEqual(rows.map((r) => r.status), [...STATUS_ORDER]);
  const indexed = rows.find((r) => r.status === "INDEXED");
  const failed = rows.find((r) => r.status === "FAILED");
  assert.equal(indexed?.fraction, 1);
  assert.equal(failed?.fraction, 0.25);
  assert.equal(rows.find((r) => r.status === "PROCESSING")?.count, 0);
  assert.ok(rows.every((r) => r.color.startsWith("#")));
});

test("statusRows empty corpus never divides by zero", () => {
  const rows = statusRows({ documents_by_status: {} });
  assert.ok(rows.every((r) => r.fraction === 0 && r.count === 0));
});

test("formatBytes and formatPercent", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(2048), "2.0 KB");
  assert.equal(formatBytes(5 * 1024 * 1024), "5.0 MB");
  assert.equal(formatPercent(0.0123), "1.23%");
  assert.equal(formatPercent(0), "0.00%");
});
