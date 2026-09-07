"""Nexus-Alpha — Painel de Controle Semântico (Dashboard técnico, modo escuro).

Design System:
- Fundo Grafite (#0F172A)
- Verde Neon (#10B981) — Verificado / Ativo
- Roxo Elétrico (#8B5CF6) — Processando / Chain-of-Thought
- Âmbar (#F59E0B) — Quarentena / Suspeita

3 telas (tab):
1. Painel Semântico — métricas + atividade em tempo real
2. Auto-Reflexão — histórico de raciocínio (reasoning_engine)
3. Quarentena — tabela de triangulação + ação humana (approve/discard)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st

# Design System: dark mandatory, color accents
st.set_page_config(page_title="Nexus-Alpha — Painel Semântico", layout="wide", initial_sidebar_state="collapsed")

# CSS: dark background, neon borders, clean typography
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .stMetric { background-color: #1E293B; border-radius: 12px; padding: 16px; }
    .stMetric div[data-testid="stMetricValue"] { color: #10B981; font-weight: 700; }
    .stSubheader { color: #F8FAFC; border-bottom: 2px solid #8B5CF6; }
    .tab-content { background: #1E293B; border-radius: 8px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 Nexus-Alpha — Painel de Controle Semântico")
st.caption("Modo Escuro Obrigatório | Infraestrutura Parasita Gratuita | Pipeline Ativo")

from src.cognition.memory import LocalMemory
from src.miner.quarantine import QuarantineStore
from src.miner.security_protocol import SecurityProtocol
from src.cognition.reflection import ReflectionWorker
from src.cognition.reasoning_engine import ReasoningEngine


@st.cache_resource
def _memory() -> LocalMemory:
    return LocalMemory()


@st.cache_resource
def _quarantine() -> QuarantineStore:
    return QuarantineStore()


@st.cache_resource
def _security() -> SecurityProtocol:
    return SecurityProtocol()


memory = _memory()
quarantine = _quarantine()
security = _security()

# --- Painel Semântico (Tab 1) ---
tabs = st.tabs(["📊 Painel Semântico", "🧠 Auto-Reflexão (CoT)", "🛡️ Quarentena & Triangulação"])

with tabs[0]:
    st.subheader("Memória de Conhecimento — Estado Atual")
    col1, col2, col3 = st.columns(3)
    stats = memory.stats()
    col1.metric("Fatos Verificados (Neo4j)", str(stats["concepts"]), delta="+0", delta_color="normal")
    col2.metric("Vetores Indexados (Qdrant)", str(stats["relations"]), delta="+0", delta_color="normal")
    col3.metric("Ameaças Bloqueadas (Quarentena)", len(quarantine.list_all()), delta="0", delta_color="inverse")

    st.markdown("---")
    st.subheader("Atividade em Tempo Real — Pipeline")
    # Mock timeline based on pipeline status
    timeline = [
        ("Há 2 min", "Minerando wikipedia.org — Status: 200 OK", "#10B981"),
        ("Há 7 min", "Triangulação: 3 fontes — Confiança 0.92", "#10B981"),
        ("Há 12 min", "NLP Extractor — 2 tripletas extraídas", "#8B5CF6"),
        ("Há 30 min", "RAG Ativo — Knowlege gap detectado", "#F59E0B"),
        ("Há 1h", "Auto-Reflexão — 1 contradição resolvida", "#10B981"),
    ]
    for time_label, desc, color in timeline:
        with st.container():
            c1, c2 = st.columns([1, 5])
            with c1:
                st.markdown(f"<span style='color:{color}; font-weight:bold;'>●</span> <b>{time_label}</b>", unsafe_allow_html=True)
            with c2:
                st.markdown(desc)

    st.markdown("---")
    st.subheader("Grafo de Conhecimento — Mapa Vivo")
    st.info("Renderização 2D leve (vis.js / Cytoscape.js) — clique em um nó para ver conexões e fontes.")
    # Placeholder for graph visualization
    st.markdown("```json\n{\"conceito\": \"IA\", \"conexoes\": 4, \"fontes\": [\"wikipedia.org\", \"edu.org\"]}\n```")

# --- Auto-Reflexão (Tab 2) ---
with tabs[1]:
    st.subheader("Janela de Auto-Reflexão — Auditagem Cognitiva")
    st.caption("Leitura do histórico do módulo reasoning_engine.py (Chain-of-Thought oculto)")
    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("Inteligência Artificial", internal_facts=["fato1", "fato2"])
    st.markdown("### Plano de Ação Gerado")
    st.json({
        "decisão": plan.decision,
        "queries": plan.target_queries,
        "etapas": [
            {"passo": str(i+1), "raciocínio": t.deduction, "timestamp": t.timestamp}
            for i, t in enumerate(plan.chain_of_thought)
        ]
    })
    st.markdown("---")
    st.subheader("Contradições Detectadas (Neo4j)")
    try:
        from src.database.graph_connector import GraphConnector
        gc = GraphConnector()
        contradictions = asyncio.get_event_loop().run_until_complete(gc.detect_contradictions())
        if contradictions:
            st.dataframe(contradictions[:10], use_container_width=True)
        else:
            st.info("Nenhuma contradição detectada no momento.")
    except Exception as exc:
        st.warning(f"Neo4j indisponível para auditagem: {exc}")

# --- Quarentena (Tab 3) ---
with tabs[2]:
    st.subheader("Área de Quarentena — Triangulação de Fontes")
    st.caption("Dados interceptados pelo filtro triangulation.py. Ação humana opcional.")
    records = quarantine.list_all()
    if records:
        for idx, r in enumerate(records[-10:][::-1]):
            col_a, col_b, col_c, col_d = st.columns([2, 1, 2, 1])
            with col_a:
                st.markdown(f"**Fonte:** `{r.get('payload', {}).get('source_url', 'N/A')}`")
                st.markdown(f"**Motivo:** `{r.get('reason', 'N/A')}`")
                st.markdown(f"**Score:** `{r.get('score', 0)}`")
            with col_b:
                st.markdown(f"**Registro:** `{r.get('timestamp', '')[:19]}`")
            with col_c:
                # Ação humana
                if st.button("✅ Aprovar Forçadamente", key=f"approve_{idx}"):
                    removed = quarantine.approve_at(-idx - 1)  # approximate index
                    st.success(f"Aprovado: {removed['payload']['source_url'] if removed else '?'}")
                    st.rerun()
                if st.button("❌ Descartar Definitivamente", key=f"discard_{idx}"):
                    quarantine.discard_at(-idx - 1)
                    st.info("Fato descartado permanentemente.")
                    st.rerun()
            with col_d:
                st.markdown("**Status:** 🟡 Quarentena")
    else:
        st.info("Quarentena vazia. Nenhum dado suspeito interceptado.")

st.markdown("---")
st.caption("Nexus-Alpha — Arquitetura de IA autônoma baseada em RAG + Grafo de Conhecimento + Auto-Reflexão. Infraestrutura gratuita: Hugging Face + GitHub Actions + Qdrant Cloud + Neo4j AuraDB.")