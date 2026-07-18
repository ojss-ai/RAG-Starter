"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchMetrics } from "../api";
import type { Metrics } from "../types";

export function useMetrics(refreshMs = 10_000): {
  metrics: Metrics | undefined;
  refresh: () => Promise<void>;
} {
  const [metrics, setMetrics] = useState<Metrics | undefined>(undefined);

  const refresh = useCallback(async () => {
    setMetrics(await fetchMetrics());
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), refreshMs);
    return () => clearInterval(timer);
  }, [refresh, refreshMs]);

  return { metrics, refresh };
}
