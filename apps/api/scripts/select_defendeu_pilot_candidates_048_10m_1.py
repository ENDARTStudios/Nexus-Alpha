"""Seletor determinístico do piloto DEFENDEU (#048.10M.1) — read-only.

Lê o atlas read-only (``reports/expansion_defendeu_atlas_048_10m.json``), aplica
os critérios de elegibilidade do Operador e emite a seleção do piloto (6–10
candidatos) + o registry de expected facts. Não escreve em Neo4j/Qdrant, não
ativa seeds, não roda worker, não chama /api/ingest.

Conservadorismo (#048.10M.1 §6): candidatos com homonímia alta não resolvida por
alias ou com múltiplos clubes na carreira são EXCLUÍDOS (não corrigidos).
"""
from __future__ import annotations

import json
from pathlib import Path

ATLAS_PATH = (Path(__file__).resolve().parents[1] / "reports" / "expansion_defendeu_atlas_048_10m.json")
SELECTION_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_candidate_selection_048_10m_1.json")
EXPECTED_FACTS_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_expected_facts_048_10m_1.json")

ALLOWED_DOMAINS = {
    "pt.wikipedia.org",
    "en.wikipedia.org",
    "rsssf.org",
    "www.rsssf.org",
    "rsssfbrasil.com",
    "www.rsssfbrasil.com",
}
WIKIMEDIA_DOMAINS = {"pt.wikipedia.org", "en.wikipedia.org"}

MIN_SELECTED = 6
MAX_SELECTED = 10

# Exclusões conservadoras com causa registrada (#048.10M.1 §6.1 critério 18 e
# priorização §6.2 — homonímia alta não resolvida por alias / múltiplos clubes).
EXCLUSION_REASONS = {
    "defendeu_arthurantunescoimbra_004": (
        "Cenario E (junk/risco semantico): probe read-only 0/2 nas paginas "
        "canonicas (pt/en 200 OK sem mencao ao objeto) — fato "
        "RIVELLINO --DEFENDEU--> FLAMENGO nao corroboravel; possivel erro fatico "
        "no atlas. Excluido por conservadorismo; atlas nao e corrigido neste task"
    ),
    "defendeu_niltonreisdossantos_008": (
        "D1_PLAYER_NAME_AMBIGUITY: homonímia jogador×estádio não resolvida por "
        "alias existente — excluído por conservadorismo"
    ),
    "defendeu_ronaldoluisnazariodelima_009": (
        "D1_PLAYER_NAME_AMBIGUITY (nome comum) + D3_LOAN_VS_DEFENDED + múltiplos "
        "clubes na carreira — excluído por conservadorismo"
    ),
    "defendeu_denilsondeoliveiraaraujo_010": (
        "D1_PLAYER_NAME_AMBIGUITY (homonímia comum) + D3_LOAN_VS_DEFENDED + "
        "múltiplos clubes na carreira — excluído por conservadorismo"
    ),
    "defendeu_gustavonery_011": (
        "D2_CLUB_NAME_AMBIGUITY: nome comum sem alias forte de homonímia — "
        "excluído por conservadorismo"
    ),
}

FORBIDDEN_OBJECTS = [
    "CIDADE", "ESTADIO", "BAIRRO", "PAIS", "ESTADO", "ENDERECO", "COORDENADA",
    "CLAUSULA", "GENERICO", "SELECAO_AMBIGUA", "COMPETICAO",
    "EMPRESTIMO_NAO_SUPORTADO", "BASE_JUVENTUDE_NAO_SUPORTADA",
]
FORBIDDEN_PREDICATES = [
    "DISPUTOU", "POSSUIR", "SER", "RESULTS", "DESCREVER", "REPRESENTAR",
]


def is_eligible_structure(candidate: dict) -> bool:
    """Critérios estruturais 1–17 do Operador (§6.1)."""
    domains = [d for d in candidate.get("required_domains", []) if d in ALLOWED_DOMAINS]
    return (
        candidate.get("predicate") == "DEFENDEU"
        and bool(str(candidate.get("subject", "")).strip())
        and bool(str(candidate.get("object", "")).strip())
        and candidate.get("requires_ontology_change") is False
        and candidate.get("risk_level") in {"low", "medium"}
        and candidate.get("source_policy") == "allowed"
        and len(domains) >= 3
        and any(d not in WIKIMEDIA_DOMAINS for d in domains)
    )


def selection_reason(candidate: dict) -> str:
    if candidate.get("notes", "").startswith("entidade existente no grafo"):
        return "low risk com fato DEFENDEU unverified já no grafo (evidência local)"
    if candidate.get("risk_level") == "medium":
        return (
            "medium risk mitigado: subject canônico inequívoco, carreira de clube "
            "único sem empréstimos na frase-alvo"
        )
    return "low risk, 3 domínios permitidos plausíveis, sem homonímia alta"


def select_pilot(atlas: dict) -> dict:
    candidates = atlas.get("candidates", [])
    selected, excluded = [], []
    for candidate in candidates:
        cid = candidate.get("candidate_id", "")
        if cid in EXCLUSION_REASONS:
            excluded.append({"candidate_id": cid, "reason": EXCLUSION_REASONS[cid]})
            continue
        if not is_eligible_structure(candidate):
            excluded.append({
                "candidate_id": cid,
                "reason": "falha em critério estrutural de elegibilidade (#048.10M.1 §6.1)",
            })
            continue
        selected.append({
            "candidate_id": cid,
            "subject": candidate["subject"],
            "subject_aliases": candidate.get("subject_aliases", []),
            "predicate": "DEFENDEU",
            "object": candidate["object"],
            "object_aliases": candidate.get("object_aliases", []),
            "risk": candidate["risk_level"],
            "risks": candidate.get("risks", []),
            "required_domains": candidate.get("required_domains", []),
            "source_policy": "allowed",
            "requires_ontology_change": False,
            "selection_reason": selection_reason(candidate),
            "exclusion_reason": None,
        })
    selected.sort(key=lambda s: (0 if s["risk"] == "low" else 1, s["candidate_id"]))
    selected = selected[:MAX_SELECTED]
    low = sum(1 for s in selected if s["risk"] == "low")
    medium = sum(1 for s in selected if s["risk"] == "medium")
    return {
        "audit_id": "defendeu_pilot_candidate_selection_048_10m_1",
        "mode": "read_only",
        "atlas_total": len(candidates),
        "selected_count": len(selected),
        "selected": selected,
        "excluded": excluded,
        "summary": {
            "low_risk_selected": low,
            "medium_risk_selected": medium,
            "high_risk_selected": 0,
            "ontology_blockers": 0,
            "source_policy_blockers": 0,
            "ready_for_dry_run": MIN_SELECTED <= len(selected) <= MAX_SELECTED,
        },
    }


def build_expected_facts(selection: dict) -> dict:
    expected = []
    for item in selection["selected"]:
        expected.append({
            "candidate_id": item["candidate_id"],
            "fact": f"{item['subject']} --DEFENDEU--> {item['object']}",
            "subject": item["subject"],
            "predicate": "DEFENDEU",
            "object": item["object"],
            "required_domains": item["required_domains"],
            "min_domain_count": 3,
            "must_be_verified": True,
            "evidence_strength": None,  # preenchido pelo dry-run/probe
            "source_evidence_refs": [],
            "risk": item["risk"],
            "ontology_change_required": False,
            "source_policy": "allowed",
        })
    return {
        "audit_id": "defendeu_pilot_expected_facts_048_10m_1",
        "batch": "defendeu_pilot_048_10m_1",
        "status": "planned_not_active",
        "expected_facts": expected,
        "forbidden_objects": FORBIDDEN_OBJECTS,
        "forbidden_predicates": FORBIDDEN_PREDICATES,
    }


def main() -> int:
    atlas = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    selection = select_pilot(atlas)
    expected = build_expected_facts(selection)
    SELECTION_PATH.write_text(
        json.dumps(selection, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    EXPECTED_FACTS_PATH.write_text(
        json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "selected_count": selection["selected_count"],
        "excluded_count": len(selection["excluded"]),
        "ready_for_dry_run": selection["summary"]["ready_for_dry_run"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
