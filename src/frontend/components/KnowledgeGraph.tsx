import React, { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';

// Força o carregamento dinâmico (Lazy Loading) do cliente para evitar quebras de SSR (Server-Side Rendering)
const ForceGraph2D = React.lazy(() =>
  import('react-force-graph').then((mod) => ({ default: mod.ForceGraph2D }))
);

interface GraphData {
  nodes: { id: string; group: number; val: number }[];
  links: { source: string; target: string; label: string }[];
}

export default function KnowledgeGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const graphRef = useRef<any>();

  // Simula a busca de dados estruturados do Neo4j via API do Space
  useEffect(() => {
    const fetchGraph = async () => {
      // Mock dinâmico simulando nós minerados pelo robô
      const mockData: GraphData = {
        nodes: [
          { id: "Inteligência Artificial", group: 1, val: 25 },
          { id: "Redes Neurais", group: 1, val: 15 },
          { id: "GitHub Actions", group: 2, val: 12 },
          { id: "Nexus-Alpha", group: 3, val: 20 },
          { id: "Neo4j AuraDB", group: 3, val: 10 }
        ],
        links: [
          { source: "Inteligência Artificial", target: "Redes Neurais", label: "UTILIZA" },
          { source: "GitHub Actions", target: "Nexus-Alpha", label: "EXECUTA" },
          { source: "Nexus-Alpha", target: "Inteligência Artificial", label: "EVOLUI" },
          { source: "Nexus-Alpha", target: "Neo4j AuraDB", label: "PERSISTE_EM" }
        ]
      };

      // Simula a latência de rede para exibir o esqueleto visual
      setTimeout(() => setGraphData(mockData), 1200);
    };
    fetchGraph();
  }, []);

  return (
    <div className="w-full h-[500px] bg-slate-950 rounded-2xl border border-slate-800/80 overflow-hidden relative">
      <div className="absolute top-4 left-4 z-10 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/50 text-xs text-slate-300 font-mono">
        🧠 Córtex Semântico: Mapeamento Relacional Vivo
      </div>

      <React.Suspense fallback={
        // Skeleton de carregamento perfeitamente alinhado ao Design System
        <div className="w-full h-full flex flex-col items-center justify-center bg-slate-950 space-y-4 animate-pulse">
          <div className="w-12 h-12 rounded-full border-4 border-t-violet-500 border-slate-800 animate-spin" />
          <p className="text-xs font-mono text-slate-500">Renderizando topologia de rede...</p>
        </div>
      }>
        {graphData ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="w-full h-full"
          >
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeLabel="id"
              nodeAutoColorBy="group"
              linkDirectionalParticles={2}
              linkDirectionalParticleSpeed={0.005}
              linkColor={() => "#334155"}
              backgroundColor="#020617"
              width={window.innerWidth > 768 ? 800 : window.innerWidth - 32}
              height={500}
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const label = node.id;
                const fontSize = 12 / globalScale;
                ctx.font = `${fontSize}px JetBrains Mono, monospace`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = node.color || '#8B5CF6';
                ctx.beginPath();
                ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
                ctx.fill();
                ctx.fillStyle = '#94A3B8';
                ctx.fillText(label, node.x, node.y + 10);
              }}
            />
          </motion.div>
        ) : null}
      </React.Suspense>
    </div>
  );
}
