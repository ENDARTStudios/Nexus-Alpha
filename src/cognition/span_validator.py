"""Nexus-Alpha — Validador determinístico de span de entidade (#050, v2 #058.2).

Impede que fragmentos sintáticos (datas, orações, locuções preposicionais/
adverbiais, pronomes, quantificadores, palavras fechadas PT/EN, relativas
internas) virem ``subject``/``object`` de ``:Fato``.

Puro e determinístico — sem LLM, sem embedding, sem dependências externas.
Deve rodar sobre o **span bruto** (antes de UPPER) para usar caixa/pontuação.

Whitelist: entidades conhecidas do dicionário canônico passam mesmo que a regra
estrutural as pegaria (ver ``known_entities``).

v2 (#058.2, evidência Inspection 2): rejeita spans só de palavras fechadas
(``E O``, ``AND``, ``BUT THERE``), inícios EN (``ALTHOUGH``, ``TO``, ``MY``),
discurso solto (``ENFIM``, ``PRIMEIRO``) e relativa interna multi-token
(``REGRA GERAL QUE MAPEIA``).
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

# Preposições/advérbios/conectivos que NÃO iniciam uma entidade (PT + EN).
_START_PREP = frozenset({
    "em", "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "com", "sem",
    "para", "por", "pelos", "pelas", "ao", "aos", "ate", "desde", "contra", "traz",
    "como", "mediante", "conforme", "segundo", "alem", "apesar", "embora", "quando",
    "onde", "enquanto", "porque", "pois", "assim", "portanto", "entre", "sob", "sobre",
    "apos", "antes", "durante",
    "and", "but", "or", "of", "to", "in", "on", "at", "for", "with", "by", "from",
    "as", "into", "onto", "upon", "about", "against", "between", "through",
    "during", "before", "after", "above", "below", "under", "over",
    "although", "though", "while", "whereas", "because", "since", "unless",
    "however", "therefore", "moreover", "furthermore", "nevertheless",
})

# Advérbios temporais → locução adverbial.
_ADVERBIAL_START = frozenset({
    "apos", "antes", "durante", "quando", "onde", "enquanto", "desde", "ate",
    "before", "after", "during", "when", "where", "while", "since", "until",
})

_PRONOUNS = frozenset({
    "isso", "isto", "aquilo", "este", "esta", "esse", "essa", "aquele", "aquela",
    "ele", "ela", "eles", "elas", "tal", "qual", "quem", "seu", "sua", "seus",
    "suas", "lhe", "lhes", "que",
    "this", "that", "these", "those", "he", "she", "it", "they", "we", "you",
    "i", "him", "her", "them", "us", "which", "who", "whom", "whose", "what",
    "whatever", "whoever", "anything", "something", "nothing", "everything",
    "everyone", "someone", "nobody", "everybody",
    "my", "his", "her", "our", "their", "your", "its", "mine", "ours", "yours",
    "theirs", "myself", "yourself", "itself", "themselves",
})

# Palavras fechadas (det/prep/conj/pron/adv discurso) — span só com estas = ruído H3.
_FUNCTION_WORDS = frozenset({
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "e", "ou", "mas", "que",
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em", "com",
    "sem", "por", "para", "ao", "aos", "as", "se", "lhe", "lhes", "seu", "sua",
    "seus", "suas", "este", "esta", "estes", "estas", "esse", "essa", "esses",
    "essas", "aquele", "aquela", "isso", "isto", "aquilo", "ele", "ela", "eles",
    "elas", "eu", "tu", "nos", "vos", "me", "te", "se",
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "as", "into", "it", "its", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those", "he", "she", "they",
    "we", "you", "i", "him", "her", "them", "us", "which", "who", "whom", "what",
    "there", "here", "then", "than", "if", "when", "while", "because", "although",
    "though", "so", "not", "no", "do", "does", "did", "have", "has", "had",
})

# Marcadores de discurso/advérbios soltos — nunca entidade (#058.2).
# Ordinais só rejeitam como span inteiro (multi-token com "primeira ..." é legítimo).
_DISCOURSE = frozenset({
    "enfim", "portanto", "logo", "assim", "pois", "contudo", "todavia",
    "entretanto", "aliás", "alias", "obviamente", "claro", "primeiro",
    "primeira", "segundo", "terceiro", "próximo", "proximo",
    "finally", "however", "therefore", "thus", "indeed", "first", "second",
    "third", "next", "anyway", "anyways",
})

# Só faz sentido como início de span multi-token (#058.2).
_DISCOURSE_START = frozenset({
    "enfim", "portanto", "logo", "contudo", "todavia", "entretanto",
    "obviamente", "finally", "however", "therefore", "indeed", "anyway",
    "anyways", "thus",
})

_QUANTIFIERS = frozenset({
    "maioria", "minoria", "alguns", "algumas", "muitos", "muitas", "poucos",
    "poucas", "todo", "toda", "todos", "todas", "cada", "nenhum", "nenhuma",
    "qualquer", "quaisquer",
})

_CLAUSE_MARKERS = (
    " de modo que", " de forma que", " para que", " porque", " pois ", " embora ",
    " quando ", " onde ", " enquanto ",
    " that ", " which ", " who ", " whom ",
)

# Relativa interna (PT "que" / EN "that|which|who" no meio do span) → fragmento.
_RELATIVE_MID_RE = re.compile(
    r"\b(que|that|which|who|whom|whose)\b", re.IGNORECASE
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

    if folded in _DISCOURSE or (len(tokens) > 1 and tokens[0] in _DISCOURSE_START):
        return f"{prefix}_generic_phrase"

    if first in _QUANTIFIERS:
        return f"{prefix}_quantifier_phrase" if role == "subject" else f"{prefix}_generic_phrase"

    if folded in _PRONOUNS or (len(tokens) > 1 and first in _PRONOUNS):
        return "object_pronoun" if role == "object" else f"{prefix}_generic_phrase"

    if folded.startswith(("que ", "o que", "para que", "porque")) or any(
        marker in f" {folded} " for marker in _CLAUSE_MARKERS
    ):
        return f"{prefix}_clause_fragment" if role == "object" else f"{prefix}_generic_phrase"

    # Relativa interna multi-token (ex.: "REGRA GERAL QUE MAPEIA") — span v2 #058.2.
    if len(tokens) >= 3:
        rel_match = _RELATIVE_MID_RE.search(folded)
        if rel_match and rel_match.start() > 0 and rel_match.end() < len(folded):
            return f"{prefix}_clause_fragment" if role == "object" else f"{prefix}_generic_phrase"

    if first in _START_PREP:
        if role == "object":
            return "object_adverbial_phrase" if first in _ADVERBIAL_START else "object_prepositional_phrase"
        return "subject_starts_with_stopword"

    # Span composto só por palavras fechadas (ex.: "E O") — H3, após regras mais específicas.
    if all(tok in _FUNCTION_WORDS for tok in tokens):
        return f"{prefix}_generic_phrase"

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
