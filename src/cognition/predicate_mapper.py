"""Nexus-Alpha — Mapeador determinístico de predicados (v1.13.0 item 3.1).

Converte verbos/expressões variantes para o **vocabulário controlado** sem
embedding, sem NLP externo (spaCy etc.) e sem baixar o quórum de verificação.

Regras de projeto:
- cada predicado canônico é explícito e testado (``tests/test_predicate_mapper.py``);
- o vocabulário controlado é pequeno e auditável (<= ``MAX_CONTROLLED_PREDICATES``);
- na dúvida, **rejeitar** (``None``) em vez de criar predicado ambíguo;
- nunca inferir predicado por similaridade vaga.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .canonicalizer import CONTROLLED_PREDICATES as BASE_PREDICATES


# --- Vocabulário controlado (auditável) ------------------------------------
# Extensões à base do canonicalizer. Cada item precisa de justificativa + teste.
EXTRA_PREDICATES: tuple[str, ...] = (
    "PRESERVA",     # X preserva Y (ex.: regularização preserva generalização)
    "TEORIZA",      # X teoriza Y (texto acadêmico)
    "É_AMIGÁVEL",   # X é amigável a Y (tech/docs: friendly, user-friendly)
)

CONTROLLED_PREDICATES: tuple[str, ...] = tuple(BASE_PREDICATES) + EXTRA_PREDICATES

# Teto do vocabulário controlado (risco de inflar demais).
MAX_CONTROLLED_PREDICATES = 30

# --- Entradas explícitas (chave = já normalizada por _normalize) ------------
EXTRA_MAP: dict[str, str] = {
    # PRESERVA
    "preserva": "PRESERVA",
    "preservam": "PRESERVA",
    "preservar": "PRESERVA",
    "preservado": "PRESERVA",
    "preservada": "PRESERVA",
    "preservacao": "PRESERVA",
    "preservir": "PRESERVA",
    "preserve": "PRESERVA",
    "preserves": "PRESERVA",
    "preserved": "PRESERVA",
    # TEORIZA
    "teoriza": "TEORIZA",
    "teorizam": "TEORIZA",
    "teorizar": "TEORIZA",
    "teoricar": "TEORIZA",
    "teorizacao": "TEORIZA",
    "teoriza se": "TEORIZA",
    # É_AMIGÁVEL
    "amigavel": "É_AMIGÁVEL",
    "amigaveis": "É_AMIGÁVEL",
    "friendly": "É_AMIGÁVEL",
    "user friendly": "É_AMIGÁVEL",
    "userfriendly": "É_AMIGÁVEL",
    # CONECTA_A (voz reflexiva — "conecta-se a" é a forma dominante em texto minerado;
    # o fold de _normalize apaga o hífen, então a chave explícita é obrigatória)
    "conecta se": "CONECTA_A",
    "conecta se a": "CONECTA_A",
    # UTILIZA (voz reflexiva — "utiliza-se"; "usa-se" já vem do canonicalizer)
    "utiliza se": "UTILIZA",
}

_PREDICATE_MAP: Optional[dict[str, str]] = None


def _normalize(raw: str) -> str:
    """minúsculas, sem acentos, sem pontuação, whitespace colapsado."""
    text = unicodedata.normalize("NFKD", (raw or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def _singularize(key: str) -> str:
    """Plural básico → singular (só quando seguro)."""
    if key.endswith("s") and len(key) > 3 and not key.endswith("ss"):
        return key[:-1]
    return key


def predicate_map() -> dict[str, str]:
    """Mapa completo (buckets do canonicalizer + extensões), chaves normalizadas."""
    global _PREDICATE_MAP
    if _PREDICATE_MAP is None:
        from .canonicalizer import SemanticCanonicalizer

        base = SemanticCanonicalizer().predicate_synonyms
        merged = {**base, **EXTRA_MAP}
        _PREDICATE_MAP = {_normalize(k): v for k, v in merged.items()}
    return _PREDICATE_MAP


def normalize_predicate_key(raw: str) -> str:
    """Chave normalizada de um predicado (exposta para testes/auditoria)."""
    return _normalize(raw)


def map_predicate(raw: str) -> tuple[Optional[str], str]:
    """Mapeia ``raw`` para o vocabulário controlado.

    Retorna ``(canonical, reason)``:
    - ``(PREDICADO, "ok")`` quando há equivalência clara;
    - ``(None, "unmapped_predicate")`` quando fora do vocabulário.
    """
    key = _normalize(raw)
    if not key:
        return None, "unmapped_predicate"

    canonical = _lookup(key)
    if canonical in CONTROLLED_PREDICATES:
        return canonical, "ok"
    return None, "unmapped_predicate"


def _lookup(key: str) -> Optional[str]:
    mapping = predicate_map()
    canonical = mapping.get(key)
    if canonical is None:
        canonical = mapping.get(_singularize(key))
    return canonical


# --- Guard determinístico de predicado (#043) ------------------------------
# Rejeita tokens que NUNCA são predicado (numérico, URL/código, stopword,
# não-verbal evidente) antes de virar tripla. Distingue "verbo legítimo fora do
# vocabulário" (unmapped → backlog #044) de "lixo" (invalid → descartado).

_URL_CODE_RE = re.compile(
    r"(https?://|www\.|\.(com|org|net|io|dev|py|js|json|html|md)\b"
    r"|[\\/@#]|[_=<>{}()\[\]|]|::|=>|->)"
)

_NUMERIC_RE = re.compile(
    r"^(\d+|s[eé]culo(\s+[ivxlcdm\d]+)?|century|d[eé]cada|decade)$"
)

# Preposições/artigos/auxiliares isolados (PT/EN). "é/são/is/are" NÃO entram aqui:
# são mapeados para SER pelo dicionário.
STOPWORD_PREDICATES = frozenset({
    "the", "a", "an", "of", "in", "on", "at", "by", "for", "with", "from", "to",
    "and", "or", "as", "than", "into", "over", "under", "about", "after",
    "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "com", "para", "sem", "sobre",
    "entre", "ao", "aos", "que", "e", "ou", "se", "como", "mais", "menos",
})

# Tokens claramente não-verbais observados em produção (spaCy PT sobre EN/misto).
NONVERBAL_TOKENS = frozenset({
    "year", "years", "through", "story", "stories", "coder", "deepr", "deep",
    "code", "data", "thing", "things", "people", "time", "way", "day", "work",
    "part", "number", "world", "life", "hand", "place", "week", "case", "point",
})

# Lemas verbais comuns (PT/EN) — usados só para CLASSIFICAR (não para mapear).
# Um token aqui fora do vocabulário vira "unmapped_predicate" (candidato ao #044).
KNOWN_VERB_LEMMAS = frozenset({
    # PT
    "ser", "estar", "ter", "haver", "fazer", "poder", "dever", "ir", "vir", "dar",
    "ver", "saber", "querer", "usar", "utilizar", "empregar", "adotar", "criar",
    "produzir", "gerar", "executar", "processar", "conectar", "associar", "vincular",
    "pertencer", "conter", "incluir", "definir", "aprender", "distribuir", "difundir",
    "popularizar", "influenciar", "impactar", "possuir", "derivar", "permitir",
    "representar", "constituir", "publicar", "descrever", "passar", "treinar",
    "otimizar", "reduzir", "aumentar", "melhorar", "aplicar", "construir",
    "desenvolver", "implementar", "requerer", "precisar", "reconhecer",
    "identificar", "classificar", "prever", "detectar", "transformar", "combinar",
    "dividir", "analisar", "preservar", "teorizar",
    # EN
    "be", "is", "are", "have", "has", "do", "make", "use", "utilize", "employ",
    "adopt", "create", "produce", "generate", "execute", "process", "connect",
    "associate", "link", "belong", "contain", "include", "define", "learn",
    "distribute", "influence", "possess", "derive", "allow", "represent",
    "constitute", "publish", "describe", "pass", "train", "optimize", "reduce",
    "increase", "improve", "apply", "build", "develop", "implement", "require",
    "recognize", "identify", "classify", "predict", "detect", "transform",
    "combine", "divide", "analyze", "run", "support", "provide", "enable",
})


def validate_predicate(raw: str) -> tuple[Optional[str], str]:
    """Guard determinístico: decide se ``raw`` pode ser predicado de uma tripla.

    Retorna ``(canonical | None, reason)`` com ``reason`` em:
    ``ok``, ``numeric_predicate``, ``url_or_code_predicate``, ``stopword_predicate``,
    ``nonverbal_predicate``, ``unmapped_predicate``, ``invalid_predicate``.
    """
    text = (raw or "").strip()
    if not text:
        return None, "invalid_predicate"

    key = _normalize(text)

    # 1) Mapeamento controlado tem precedência: nomes canônicos contêm "_"
    #    (CONECTA_A, PERTENCE_A, É_AMIGÁVEL) e não podem ser confundidos com
    #    artefatos de código pelo regex de URL/código.
    upper = text.upper()
    if upper in CONTROLLED_PREDICATES:
        return upper, "ok"
    canonical = _lookup(key) if key else None
    if canonical in CONTROLLED_PREDICATES:
        return canonical, "ok"

    # 2) Rejeições estruturais.
    if _NUMERIC_RE.match(text.lower()):
        return None, "numeric_predicate"
    if _URL_CODE_RE.search(text):
        return None, "url_or_code_predicate"
    if not key or len(key) < 2:
        return None, "invalid_predicate"
    if key in STOPWORD_PREDICATES:
        return None, "stopword_predicate"
    if key in NONVERBAL_TOKENS:
        return None, "nonverbal_predicate"

    # 3) Verbo legítimo fora do vocabulário (backlog #044) vs lixo.
    if key in KNOWN_VERB_LEMMAS or _singularize(key) in KNOWN_VERB_LEMMAS:
        return None, "unmapped_predicate"
    return None, "invalid_predicate"


# Motivos que caracterizam predicado INVÁLIDO (o extrator descarta na origem).
# ``unmapped_predicate`` fica de fora: verbo legítimo fora do vocabulário segue
# para o servidor (quarentena) e alimenta o backlog #044.
INVALID_PREDICATE_REASONS = frozenset({
    "numeric_predicate",
    "url_or_code_predicate",
    "stopword_predicate",
    "nonverbal_predicate",
    "invalid_predicate",
})
