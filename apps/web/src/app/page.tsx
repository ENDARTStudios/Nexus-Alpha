"use client";

import React from "react";

import ChatWidget from "@/components/ChatWidget";
import BrainPanel from "@/components/BrainPanel";
import KnowledgeGraph from "@/components/KnowledgeGraph";

export default function AuditPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 flex flex-col justify-between">
      {/* Container de Controle Central */}
      <div className="max-w-7xl w-full mx-auto space-y-8 flex-1">
        <header className="border-b border-slate-900 pb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold tracking-widest text-violet-400 uppercase">
                Ambiente de Auditoria
              </span>
              <span className="bg-violet-950/50 text-violet-400 text-[10px] font-mono px-2 py-0.5 rounded border border-violet-800/30">
                PRO MODE
              </span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight mt-1">
              Nexus-Alpha Core
            </h1>
          </div>
          <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-full text-xs font-mono border border-slate-800">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            CÓRTEX INTEGRADO E SEGURO
          </div>
        </header>

        {/* Workspace Central onde a malha de Grafos se expande */}
        <section className="grid grid-cols-1 gap-6">
          <div className="bg-slate-900/40 border border-slate-900 rounded-3xl p-4 md:p-6 backdrop-blur-sm">
            <h2 className="text-sm font-semibold text-slate-400 font-mono mb-4 flex items-center gap-2">
              <span>⊙</span> Topologia Ativa do Grafo Vivo
            </h2>
            <KnowledgeGraph />
          </div>
        </section>

        {/* Painel do Cérebro (read-only) */}
        <BrainPanel />
      </div>

      {/* Roda do Sistema */}
      <footer className="max-w-7xl w-full mx-auto border-t border-slate-900 mt-12 pt-4 flex flex-col sm:flex-row justify-between items-center text-xs text-slate-500 gap-2 font-mono">
        <p>© 2026 ENDARTStudios / Nexus-Alpha Ecosystem.</p>
        <p>Status: Ativo | Quórum de Triangulação Operacional</p>
      </footer>

      {/* Widget Interativo de Atendimento e Consulta */}
      <ChatWidget />
    </div>
  );
}
