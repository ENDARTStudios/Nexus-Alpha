"use client";

import React from "react";

import { useBrainEpisodes, useBrainStats } from "../lib/brain";

const STATUS_STYLES: Record<string, string> = {
  consolidado: "bg-violet-950/50 text-violet-300 border-violet-800/40",
  repetido: "bg-amber-950/40 text-amber-300 border-amber-800/40",
  novo: "bg-slate-800/60 text-slate-300 border-slate-700/50",
};

function Metric({ label, value, hint, accent }: { label: string; value: string | number; hint?: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-900/60 p-3">
      <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-extrabold font-mono ${accent ?? "text-slate-100"}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[10px] text-slate-500">{hint}</p>}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 animate-pulse">
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="h-20 rounded-xl border border-slate-800/70 bg-slate-900/60" />
      ))}
    </div>
  );
}

export default function BrainPanel() {
  const { data: stats, loading, error } = useBrainStats(60000);
  const { data: episodes } = useBrainEpisodes(10, 60000);

  return (
    <section className="bg-slate-900/40 border border-slate-900 rounded-3xl p-4 md:p-6 backdrop-blur-sm">
      <h2 className="text-sm font-semibold text-slate-400 font-mono mb-4 flex items-center gap-2">
        <span>◉</span> Cérebro / Memória Ativa
      </h2>

      {loading && !stats ? (
        <Skeleton />
      ) : error && !stats ? (
        <p className="text-xs font-mono text-amber-400">
          Córtex offline ({error}). O painel é read-only e tolera indisponibilidade.
        </p>
      ) : stats ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric
              label="Working slots"
              value={`${stats.working_memory.active_slots}/${stats.working_memory.capacity}`}
              hint={stats.working_memory.region}
              accent="text-emerald-300"
            />
            <Metric
              label="Episódios"
              value={stats.episodic_memory.episodes}
              hint={stats.episodic_memory.region}
            />
            <Metric
              label="Consolidação"
              value={`${stats.consolidation.consolidated}/${stats.consolidation.candidates}`}
              hint={`min_replays=${stats.consolidation.min_replays}`}
              accent="text-violet-300"
            />
            <Metric
              label="Hebbian pairs"
              value={stats.graph.hebbian_pairs}
              hint="co-ativações"
            />
            <Metric label="Conceitos" value={stats.graph.concepts} />
            <Metric label="Fatos" value={stats.graph.facts} />
            <Metric
              label="Verificados"
              value={stats.graph.verified_facts}
              accent="text-emerald-300"
            />
            <Metric label="Vetores" value={stats.vectors.count} accent="text-violet-300" />
          </div>

          <div className="mt-5">
            <p className="mb-2 text-[10px] font-mono uppercase tracking-wider text-slate-500">
              Episódios recentes (hipocampo)
            </p>
            <div className="overflow-x-auto rounded-xl border border-slate-800/70">
              <table className="w-full text-left text-[11px] font-mono">
                <thead className="bg-slate-950/60 text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Quando</th>
                    <th className="px-3 py-2">Fonte</th>
                    <th className="px-3 py-2">Fato</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2 text-right">Replays</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {(episodes?.items ?? []).map((episode) => (
                    <tr key={episode.id} className="border-t border-slate-800/60">
                      <td className="px-3 py-2 whitespace-nowrap text-slate-500">
                        {new Date(episode.created_at).toLocaleTimeString("pt-BR")}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-slate-400">
                        {episode.source_domain ?? episode.kind ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        {episode.subject} <span className="text-slate-500">--[{episode.predicate}]--&gt;</span>{" "}
                        {episode.object}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10px] ${
                            STATUS_STYLES[episode.status] ?? STATUS_STYLES.novo
                          }`}
                        >
                          {episode.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-slate-400">{episode.replays}</td>
                    </tr>
                  ))}
                  {(episodes?.items ?? []).length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-center text-slate-500">
                        Nenhum episódio registrado ainda.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
