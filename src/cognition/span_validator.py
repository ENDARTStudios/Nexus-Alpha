"""Nexus-Alpha — Validador determinístico de span de entidade (#050).

Impede que fragmentos sintáticos (datas, orações, locuções preposicionais/
adverbiais, pronomes, quantificadores) virem ``subject``/``object`` de ``:Fato``.

Puro e determinístico — sem LLM, sem embedding, sem dependências externas.
Deve rodar sobre o **span bruto** (antes de UPPER) para usar caixa/pontuação.

Whitelist: entidades conhecidas do dicionário canônico passam mesmo que a regra
estrutural as pegaria (ver ``known_entities``).
"""
from __future__ import annotations

import re
import unicodedata
from typing import AbstractSet, Literal, Optional

Role = Literal["subject", "object"]

MAX_TOKENS = 8
MAX_CHARS = 60

_PUNCT = set(".,;:!?()[]{}\"'`-")
_CODE_CHARS = set("{}[]<>|\\/=_@#~^`")

# Locução temporal / ano / século / década.
_DATE_RE = re.compile(
    r"^(em |de |do |da |dos |das |no |na |por )?"
    r"(\d{1,4}|s[eé]culo(\s+[ivxlcdm]+)?|d[eé]cada(\s+de\s+\d{4})?|anos(\s+\d{1,3})?)$"
)

# Preposições/advérbios/conectivos que NÃO iniciam uma entidade.
_START_PREP = frozenset({
    "em", "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "com", "sem",
    "para", "por", "pelos", "pelas", "ao", "aos", "ate", "desde", "contra", "traz",
    "como", "mediante", "conforme", "segundo", "alem", "apesar", "embora", "quando",
    "onde", "enquanto", "porque", "pois", "assim", "portanto", "entre", "sob", "sobre",
    "apos", "antes", "durante",
})

# Advérbios temporais → locução adverbial.
_ADVERBIAL_START = frozenset({
    "apos", "antes", "durante", "quando", "onde", "enquanto", "desde", "ate",
})

_PRONOUNS = frozenset({
    "isso", "isto", "aquilo", "este", "esta", "esse", "essa", "aquele", "aquela",
    "ele", "ela", "eles", "elas", "tal", "qual", "quem", "seu", "sua", "seus",
    "suas", "lhe", "lhes", "que",
})

_QUANTIFIERS = frozenset({
    "maioria", "minoria", "alguns", "algumas", "muitos", "muitas", "poucos",
    "poucas", "todo", "toda", "todos", "todas", "cada", "nenhum", "nenhuma",
    "qualquer", "quaisquer",
})

_CLAUSE_MARKERS = (
    " de modo que", " de forma que", " para que", " porque", " pois ", " embora ",
    " quando ", " onde ", " enquanto ",
)


def fold_span(span: str) -> str:
    """Minúsculas, sem acentos, sem pontuação de borda, espaços colapsados."""
    folded = unicodedata.normalize("NFKD", str(span or "").strip().lower())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = re.sub(r"[^a-z0-9\s]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def reject_reason_for_span(
    span: str,
    role: Role = "object",
    known_entities: Optional[AbstractSet[str]] = None,
) -> Optional[str]:
    """Motivo de rejeição do span, ou ``None`` se for entidade plausível."""
    raw = str(span or "").strip()
    folded = fold_span(raw)
    prefix = "subject" if role == "subject" else "object"

    if not folded or len(folded) < 2:
        return f"{prefix}_generic_phrase"
    if known_entities and folded in known_entities:
        return None

    if raw[:1] in _PUNCT or any(ch in _CODE_CHARS for ch in raw):
        return "object_punctuated" if role == "object" else f"{prefix}_generic_phrase"

    tokens = folded.split()
    first = tokens[0]

    if re.fullmatch(r"[\d\s]+", folded):
        return "object_numeric_only" if role == "object" else f"{prefix}_generic_phrase"

    if _DATE_RE.match(folded):
        return "object_date_like" if role == "object" else f"{prefix}_generic_phrase"

    if first in _QUANTIFIERS:
        return f"{prefix}_quantifier_phrase" if role == "subject" else f"{prefix}_generic_phrase"

    if folded in _PRONOUNS or (len(tokens) > 1 and first in _PRONOUNS):
        return "object_pronoun" if role == "object" else f"{prefix}_generic_phrase"

    if folded.startswith(("que ", "o que", "para que", "porque")) or any(
        marker in f" {folded} " for marker in _CLAUSE_MARKERS
    ):
        return f"{prefix}_clause_fragment" if role == "object" else f"{prefix}_generic_phrase"

    if first in _START_PREP:
        if role == "object":
            return "object_adverbial_phrase" if first in _ADVERBIAL_START else "object_prepositional_phrase"
        return "subject_starts_with_stopword"

    if len(tokens) > MAX_TOKENS or len(raw) > MAX_CHARS:
        return f"{prefix}_too_long"

    return None


def validate_entity_span(
    span: str,
    role: Role = "object",
    known_entities: Optional[AbstractSet[str]] = None,
) -> tuple[bool, Optional[str]]:
    """Devolve ``(True, None)`` ou ``(False, motivo)`` para o span."""
    reason = reject_reason_for_span(span, role, known_entities)
    return (reason is None), reason
