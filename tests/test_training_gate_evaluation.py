"""#060 — testes do avaliador read-only do gate de treino (sem rede/grafo)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "evaluate_training_gate", str(ROOT / "scripts" / "evaluate_training_gate.py")
)
etg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(etg)


def test_publisher_mapping():
    assert etg._publisher_for("pt.wikipedia.org") == "Wikimedia"
    assert etg._publisher_for("en.wikipedia.org") == "Wikimedia"
    assert etg._publisher_for("rsssf.org") == "RSSSF"
    assert etg._publisher_for("gazetadoparana.com.br") == "gazetadoparana.com.br"


def test_validate_jsonl_detects_invalid_and_secrets(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text(
        '{"instruction":"i","input":"x","output":"o"}\n'
        '{"instruction":"i2","input":"y","output":""}\n'
        'NOT JSON\n',
        encoding="utf-8",
    )
    info = etg._validate_jsonl(p)
    assert info["lines"] == 3
    assert info["valid"] == 2
    assert info["invalid"] == 1
    assert info["empty_output"] == 1


def test_jsonl_char_stats(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text(
        '{"instruction":"abcd","input":"x","output":"xy"}\n'
        '{"instruction":"ab","input":"y","output":"xyz"}\n',
        encoding="utf-8",
    )
    stats = etg._jsonl_char_stats(p)
    assert stats["avg_instruction_chars"] == 3.0
    assert stats["avg_output_chars"] == 2.5
    assert stats["max_output_chars"] == 3


def test_secret_regex_flags_credentials():
    assert etg.SECRET_RE.search("Authorization: Bearer abc")
    assert etg.SECRET_RE.search("hf_abcdefghijklmnop")
    assert etg.SECRET_RE.search("neo4j://user:pass@host")
    assert not etg.SECRET_RE.search("BOTAFOGO VENCEU COPA LIBERTADORES")


def test_date_and_clause_object_detection():
    assert etg.DATE_RE.search("2024")
    assert etg.CLAUSE_RE.search("won the title when he played")
    assert not etg.CLAUSE_RE.search("COPA LIBERTADORES")
