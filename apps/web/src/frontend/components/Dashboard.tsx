import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Variantes de animação de mola (Spring) ultra-leves e fluidas
const fadeInSpring = {
  hidden: { opacity: 0, y: 15 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 100, damping: 15 }
  }
};

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState({ facts: 0, vectors: 0, quarantine: 0 });

  // Simulação de carregamento rápido (Lazy Loading) do Dashboard
  useEffect(() => {
    const timer = setTimeout(() => {
      setMetrics({ facts: 1420, vectors: 8940, quarantine: 12 });
      setLoading(false);
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4 md:p-8 font-sans overflow-x-hidden">
      {/* Header do Sistema */}
      <header className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">Nexus-Alpha</h1>
          <p className="text-xs md:text-sm text-slate-400">Plataforma Autônoma de Auditoria Cognitiva</p>
        </div>
        <div className="flex items-center gap-2 bg-slate-800 px-3 py-1.5 rounded-full text-xs font-mono border border-slate-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          CORE OPERACIONAL
        </div>
      </header>

      {/* Grid de Métricas Principais */}
      <main className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
        <AnimatePresence mode="wait">
          {loading ? (
            // Esqueleto de Carregamento (Skeletons)
            Array.from({ length: 3 }).map((_, idx) => (
              <div key={idx} className="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 space-y-4 animate-pulse">
                <div className="h-4 bg-slate-700 rounded w-1/3" />
                <div className="h-8 bg-slate-700 rounded w-1/2" />
                <div className="h-3 bg-slate-700 rounded w-3/4" />
              </div>
            ))
          ) : (
            // Cards de Métricas Reais Animados com Motion
            <>
              <motion.div variants={fadeInSpring} initial="hidden" animate="visible" className="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 hover:border-violet-500/50 transition-colors">
                <p className="text-xs md:text-sm font-semibold text-slate-400 uppercase tracking-wider">Fatos Verificados</p>
                <p className="text-3xl md:text-4xl font-extrabold text-white mt-2 font-mono">{metrics.facts}</p>
                <p className="text-xs text-emerald-400 mt-2">✓ Mapeados no Neo4j</p>
              </motion.div>

              <motion.div variants={fadeInSpring} initial="hidden" animate="visible" className="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 hover:border-violet-500/50 transition-colors">
                <p className="text-xs md:text-sm font-semibold text-slate-400 uppercase tracking-wider">Memória Vetorial</p>
                <p className="text-3xl md:text-4xl font-extrabold text-white mt-2 font-mono">{metrics.vectors}</p>
                <p className="text-xs text-violet-400 mt-2">⚡ Indexados no Qdrant</p>
              </motion.div>

              <motion.div variants={fadeInSpring} initial="hidden" animate="visible" className="bg-slate-800 p-6 rounded-2xl border border-slate-700/50 hover:border-amber-500/50 transition-colors">
                <p className="text-xs md:text-sm font-semibold text-slate-400 uppercase tracking-wider">Quarentena de Segurança</p>
                <p className="text-3xl md:text-4xl font-extrabold text-amber-500 mt-2 font-mono">{metrics.quarantine}</p>
                <p className="text-xs text-amber-400/80 mt-2">⚠ Triangulações pendentes</p>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
