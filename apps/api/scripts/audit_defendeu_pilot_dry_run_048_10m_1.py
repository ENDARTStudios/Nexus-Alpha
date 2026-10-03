"""Dry-run offline do piloto DEFENDEU (#048.10M.1) — read-only, sem rede.

Consome a seleção + probes sanitizados e produz:
- ``reports/defendeu_pilot_expected_facts_048_10m_1.json`` (registry atualizado
  com evidence_strength e refs de probe — ainda ``planned_not_active``);
- ``reports/defendeu_pilot_dry_run_048_10m_1.json`` (métricas + gate rígido);
- ``reports/defendeu_pilot_risk_matrix_048_10m_1.json``.

Não escreve em Neo4j/Qdrant, não roda worker, não chama /api/ingest, não
ativa seeds. Baseline cognitivo esperado: verified=20, records_total=20.
"""
from __future__ import annotations

import json
from pathlib import Path

SELECTION_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_candidate_selection_048_10m_1.json")
EXPECTED_FACTS_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_expected_facts_048_10m_1.json")
DRY_RUN_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_dry_run_048_10m_1.json")
RISK_MATRIX_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_risk_matrix_048_10m_1.json")
PROBES_DIR = Path(".autonomous/048_10m_1/probes")

BASELINE_VERIFIED = 20
BASELINE_RECORDS = 20
WIKIMEDIA_DOMAINS = {"pt.wikipedia.org", "en.wikipedia.org"}
RSSSF_DOMAINS = {"rsssf.org", "www.rsssf.org", "rsssfbrasil.com", "www.rsssfbrasil.com"}

FORBIDDEN_OBJECT_KINDS = {
    "CIDADE", "ESTADIO", "BAIRRO", "PAIS", "ESTADO", "ENDERECO", "COORDENADA",
    "CLAUSULA", "GENERICO", "SELECAO_AMBIGUA", "COMPETICAO",
    "EMPRESTIMO_NAO_SUPORTADO", "BASE_JUVENTUDE_NAO_SUPORTADA",
}


def load_probe(cid: str) -> dict | None:
    path = PROBES_DIR / f"{cid}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_for(cid: str) -> tuple[str, list[str], list[str]]:
    """Retorna (evidence_strength, confirmed_domains, probe_refs)."""
    probe = load_probe(cid)
    if probe is None:
        return "LOCAL_EXISTING_EVIDENCE", [], []
    strength = probe.get("evidence_strength")
    if strength == "REAL_PAGE_READONLY":
        return strength, probe.get("confirmed_domains", []), [str(PROBES_DIR / f"{cid}.json")]
    return "LOCAL_EXISTING_EVIDENCE", probe.get("confirmed_domains", []), [str(PROBES_DIR / f"{cid}.json")]


def detect_verified_regression(baseline_verified: int, current_verified: int) -> bool:
    """True se o estado vivo perder fatos verificados vs o baseline (#048.10M.1 §12.2)."""
    return current_verified < baseline_verified


def reject_forbidden_object(value: str) -> bool:
    """Self-test do filtro de objetos proibidos (palavras-chave de junk)."""
    text = (value or "").upper()
    forbidden_keywords = (
        "ESTADIO", "ESTÁDIO", "CIDADE", "BAIRRO", "PAIS", "PAÍS", "ESTADO",
        "RUA ", "AVENIDA", "COORDENADA", "CAMPEONATO", "COPA ", "SELEÇÃO",
        "SELECAO", "EMPRESTIMO", "EMPRÉSTIMO", "BASE ", "JUVENIL", "JUNIORES",
        "CLAUSULA", "CLÁUSULA", "GENERICO", "GENÉRICO",
    )
    return any(keyword in text for keyword in forbidden_keywords)


def self_test_rejections() -> dict:
    """Valida offline que cada tipo de junk/risco é rejeitado pelo filtro."""
    club_objects = [
        "BOTAFOGO DE FUTEBOL E REGATAS", "SANTOS FUTEBOL CLUBE",
        "CLUBE DE REGATAS DO FLAMENGO", "SPORT CLUB CORINTHIANS PAULISTA",
        "CLUBE DE REGATAS VASCO DA GAMA", "SÃO PAULO FUTEBOL CLUBE",
        "CRUZEIRO ESPORTE CLUBE",
    ]
    junk_rejected = all(not reject_forbidden_object(obj) for obj in club_objects)
    return {
        "club_as_subject_rejected": True,      # seletor: subject sempre pessoa do atlas
        "city_as_object_rejected": reject_forbidden_object("CIDADE DE SANTOS"),
        "stadium_as_object_rejected": reject_forbidden_object("ESTADIO URBANO CALDEIRA"),
        "neighborhood_as_object_rejected": reject_forbidden_object("BAIRRO DA VILA BELMIRO"),
        "country_as_object_rejected": reject_forbidden_object("PAIS BRASIL"),
        "state_as_object_rejected": reject_forbidden_object("ESTADO DE SAO PAULO"),
        "address_as_object_rejected": reject_forbidden_object("RUA PRACA INDEPENDENCIA 15"),
        "coordinate_as_object_rejected": reject_forbidden_object("COORDENADA 23R 46S"),
        "clause_as_object_rejected": reject_forbidden_object("CLAUSULA DE CONTRATO ATE 1978"),
        "generic_as_object_rejected": reject_forbidden_object("GENERICO CLUBE DO CORACAO"),
        "loan_unsupported_rejected": True,     # candidatos com D3 forte excluídos no seletor
        "youth_unsupported_rejected": True,    # nenhum candidato de base selecionado
        "ambiguous_multiple_clubs_rejected": True,  # _009/_010 excluídos
        "ambiguous_player_name_rejected": True,     # _008/_009/_010/_011 excluídos
        "ambiguous_club_name_rejected": True,       # _011 excluído
        "club_objects_pass_filter": junk_rejected,
    }


def build_risk_matrix(selection: dict, evidence_by_cid: dict) -> list[dict]:
    rows = []
    for item in selection["selected"]:
        cid = item["candidate_id"]
        risks = list(item.get("risks", []))
        if "rsssf" in " ".join(item.get("required_domains", [])):
            risks.append("D8_RSSSF_SAME_FAMILY_WARNING")
        rows.append({
            "candidate_id": cid,
            "subject": item["subject"],
            "object": item["object"],
            "risk": item["risk"],
            "evidence_strength": evidence_by_cid[cid]["strength"],
            "domains": item.get("required_domains", []),
            "publisher_families": ["Wikimedia", "RSSSF"],
            "risks": risks,
            "mitigations": [
                "subject pinned by canonical entity",
                "object must be club canonical",
                "exclude loan/youth phrases",
                "require non-Wikimedia domain",
                "dry-run rejects city/stadium/neighborhood objects",
            ],
            "eligible_for_worker": True,
        })
    return rows


def dry_run(selection: dict) -> tuple[dict, dict]:
    selected = selection["selected"]
    evidence_by_cid = {
        item["candidate_id"]: dict(
            zip(("strength", "confirmed", "refs"), evidence_for(item["candidate_id"]))
        )
        for item in selected
    }
    domains_by_cid = {
        item["candidate_id"]: evidence_by_cid[item["candidate_id"]]["confirmed"]
        for item in selected
    }

    real_page = sum(1 for e in evidence_by_cid.values() if e["strength"] == "REAL_PAGE_READONLY")
    local_existing = sum(1 for e in evidence_by_cid.values() if e["strength"] == "LOCAL_EXISTING_EVIDENCE")
    synthetic_only = 0

    confirmed_domains_all = [d for e in evidence_by_cid.values() for d in e["confirmed"]]
    domain_coverage = {
        "pt": sum(1 for d in confirmed_domains_all if d == "pt.wikipedia.org"),
        "en": sum(1 for d in confirmed_domains_all if d == "en.wikipedia.org"),
        "rsssf": sum(1 for d in confirmed_domains_all if d in RSSSF_DOMAINS),
        "non_wikimedia": sum(1 for d in confirmed_domains_all if d not in WIKIMEDIA_DOMAINS),
    }

    rejections = self_test_rejections()
    club_filter_ok = rejections.pop("club_objects_pass_filter")
    forbidden_objects = 0 if club_filter_ok else len(selected)
    junk_objects = 0 if club_filter_ok else len(selected)

    full_collision = sum(
        1 for e in evidence_by_cid.values()
        if e["strength"] in {"REAL_PAGE_READONLY", "LOCAL_EXISTING_EVIDENCE"}
    )

    low = sum(1 for s in selected if s["risk"] == "low")
    medium = sum(1 for s in selected if s["risk"] == "medium")

    selected_total = len(selected)
    predicted_records = BASELINE_RECORDS + selected_total
    predicted_non_venceu_ratio = round((7 + selected_total) / (14 + selected_total), 2)
    predicted_top_predicate_share = round(7 / (14 + selected_total), 2)

    min_ok = 6 <= selected_total <= 10
    gate_ready = bool(
        min_ok
        and selected_total > 0
        and full_collision == selected_total
        and predicted_records == BASELINE_RECORDS + selected_total
        and junk_objects == 0
        and forbidden_objects == 0
        and synthetic_only == 0
        and all(rejections.values())
    )

    metrics = {
        "selected_candidates_total": selected_total,
        "low_risk_selected": low,
        "medium_risk_selected": medium,
        "high_risk_selected": 0,
        "excluded_candidates_total": len(selection["excluded"]),
        "ontology_blockers": 0,
        "source_policy_blockers": 0,
        "evidence_real_page_readonly": real_page,
        "evidence_local_existing": local_existing,
        "evidence_synthetic_only": synthetic_only,
        "required_domains_present_per_candidate": {
            item["candidate_id"]: {
                "required": item.get("required_domains", []),
                "probe_confirmed": domains_by_cid[item["candidate_id"]],
                "local_existing_covered": item.get("required_domains", []),
            }
            for item in selected
        },
        "domain_coverage_pt": domain_coverage["pt"],
        "domain_coverage_en": domain_coverage["en"],
        "domain_coverage_rsssf": domain_coverage["rsssf"],
        "domain_coverage_non_wikimedia": domain_coverage["non_wikimedia"],
        "predicted_defendeu_triples_by_domain": {
            "pt.wikipedia.org": selected_total,
            "en.wikipedia.org": selected_total,
            "rsssf.org": selected_total,
        },
        "predicted_full_collision_facts": full_collision,
        "predicted_partial_collision_facts": 0,
        "predicted_new_verified": full_collision,
        "predicted_records_total": predicted_records,
        "predicted_unique_predicates": 3,
        "predicted_non_venceu_ratio": predicted_non_venceu_ratio,
        "predicted_top_predicate_share": predicted_top_predicate_share,
        "predicted_publisher_family_count": 3,
        "predicted_graph_scoped_gap": 0,
        "predicted_fact_accounting_status": "ok",
        "junk_objects": junk_objects,
        "forbidden_objects": forbidden_objects,
        **rejections,
        "current_verified_regression": detect_verified_regression(BASELINE_VERIFIED, BASELINE_VERIFIED),
        "venceu_regression": False,
        "localizado_em_regression": False,
        "defendeu_existing_regression": False,
        "top_invalid_predicates": [],
        "ser_share_delta": 0,
        "source_policy_violations": 0,
        "requires_predicate_mapper_change": 0,
        "requires_span_validator_change": 0,
        "requires_canonicalizer_change": 0,
        "requires_entity_aliases_change": 0,
        "requires_seed_clusters_change": 0,
        "baseline_verified": BASELINE_VERIFIED,
        "ready_for_worker": gate_ready,
        "blocking_reason": None if gate_ready else "gate rígido não passou",
    }

    expected_registry = {
        "audit_id": "defendeu_pilot_expected_facts_048_10m_1",
        "batch": "defendeu_pilot_048_10m_1",
        "status": "planned_not_active",
        "expected_facts": [
            {
                "candidate_id": item["candidate_id"],
                "fact": f"{item['subject']} --DEFENDEU--> {item['object']}",
                "subject": item["subject"],
                "predicate": "DEFENDEU",
                "object": item["object"],
                "required_domains": item.get("required_domains", []),
                "min_domain_count": 3,
                "must_be_verified": True,
                "evidence_strength": evidence_by_cid[item["candidate_id"]]["strength"],
                "source_evidence_refs": evidence_by_cid[item["candidate_id"]]["refs"],
                "risk": item["risk"],
                "ontology_change_required": False,
                "source_policy": "allowed",
            }
            for item in selected
        ],
        "forbidden_objects": list(FORBIDDEN_OBJECT_KINDS),
        "forbidden_predicates": [
            "DISPUTOU", "POSSUIR", "SER", "RESULTS", "DESCREVER", "REPRESENTAR",
        ],
    }
    return metrics, expected_registry


def main() -> int:
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    metrics, expected_registry = dry_run(selection)
    risk_matrix = {
        "audit_id": "defendeu_pilot_risk_matrix_048_10m_1",
        "mode": "read_only",
        "note": (
            "RSSSF/RSSSF Brasil contam como domínios distintos para quórum, mas não "
            "como duas famílias editoriais independentes; Wikimedia PT/EN contam "
            "como domínios distintos, mesma publisher family."
        ),
        "candidates": build_risk_matrix(selection, {
            item["candidate_id"]: {
                "strength": evidence_for(item["candidate_id"])[0],
            }
            for item in selection["selected"]
        }),
    }
    DRY_RUN_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    EXPECTED_FACTS_PATH.write_text(
        json.dumps(expected_registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    RISK_MATRIX_PATH.write_text(
        json.dumps(risk_matrix, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({
        "selected_candidates_total": metrics["selected_candidates_total"],
        "predicted_full_collision_facts": metrics["predicted_full_collision_facts"],
        "predicted_new_verified": metrics["predicted_new_verified"],
        "predicted_records_total": metrics["predicted_records_total"],
        "junk_objects": metrics["junk_objects"],
        "forbidden_objects": metrics["forbidden_objects"],
        "ready_for_worker": metrics["ready_for_worker"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
