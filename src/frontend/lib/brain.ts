"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_NEXUS_API_URL ?? "";

export interface BrainStats {
  working_memory: {
    active_slots: number;
    active_concepts: string[];
    capacity: number;
    decay_policy: string;
    region: string;
  };
  episodic_memory: {
    episodes: number;
    last_episode_at: string | null;
    region: string;
  };
  consolidation: {
    candidates: number;
    consolidated: number;
    min_replays: number;
    region: string;
  };
  graph: {
    concepts: number;
    facts: number;
    verified_facts: number;
    hebbian_pairs: number;
  };
  vectors: { count: number };
}

export interface BrainEpisode {
  id: string;
  created_at: string;
  kind: string | null;
  source_domain: string | null;
  subject: string;
  predicate: string;
  object: string;
  status: string;
  replays: number;
  weight: number;
  entities: number;
}

interface HookState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

function usePolling<T>(path: string, intervalMs: number): HookState<T> & { refresh: () => void } {
  const [state, setState] = useState<HookState<T>>({ data: null, loading: true, error: null });

  const load = useCallback(async () => {
    try {
      const data = await fetchJson<T>(path);
      setState({ data, loading: false, error: null });
    } catch (error) {
      setState((prev) => ({
        data: prev.data,
        loading: false,
        error: error instanceof Error ? error.message : "offline",
      }));
    }
  }, [path]);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      if (alive) await load();
    };
    void run();
    const id = setInterval(() => void run(), intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [load, intervalMs]);

  return { ...state, refresh: () => void load() };
}

export function useBrainStats(intervalMs = 60000) {
  return usePolling<BrainStats>("/api/brain/stats", intervalMs);
}

export function useBrainEpisodes(limit = 10, intervalMs = 60000) {
  return usePolling<{ items: BrainEpisode[] }>(
    `/api/brain/episodes?limit=${limit}`,
    intervalMs,
  );
}
