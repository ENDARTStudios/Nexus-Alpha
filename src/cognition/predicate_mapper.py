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
    # #045.1 — vocabulário esportivo (lista fechada; sem JOGOU_POR/DISPUTOU_TITULO)
    "DEFENDEU",     # relação jogador↔clube (defendeu / jogou por / vestiu / joined)
    "VENCEU",       # título/competição (venceu / ganhou / conquistou / won)
    "LOCALIZADO_EM",  # clube/estádio↔cidade (fica em / sediado em / located in)
    "DISPUTOU",     # competição (disputou / participou / competed)
    "TREINOU",      # técnico↔clube (treinou / comandou / coached)
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
    # POSSUIR (posse/atribuição básica)
    "ter": "POSSUIR",
    "tem": "POSSUIR",
    "tinha": "POSSUIR",
    "teve": "POSSUIR",
    "temos": "POSSUIR",
    "terei": "POSSUIR",
    "teria": "POSSUIR",
    "terao": "POSSUIR",
    "possuir": "POSSUIR",
    # CONTIENE (composição/membership)
    "incluir": "CONTIENE",
    "inclui": "CONTIENE",
    "incluiu": "CONTIENE",
    "incluindo": "CONTIENE",
    "incluido": "CONTIENE",
    "incluem": "CONTIENE",
    # UTILIZA (uso/aplicação de método, tecnologia, modelo)
    "aplicar": "UTILIZA",
    "aplica": "UTILIZA",
    "aplicou": "UTILIZA",
    "aplicando": "UTILIZA",
    "aplicado": "UTILIZA",
    "aplicam": "UTILIZA",
    # PRODUZ (produção de artigo/documento e de artefato)
    "publicar": "PRODUZ",
    "publica": "PRODUZ",
    "publicou": "PRODUZ",
    "publicando": "PRODUZ",
    "publicado": "PRODUZ",
    "publicam": "PRODUZ",
    "desenvolver": "PRODUZ",
    "desenvolve": "PRODUZ",
    "desenvolveu": "PRODUZ",
    "desenvolvendo": "PRODUZ",
    "desenvolvido": "PRODUZ",
    "desenvolvem": "PRODUZ",
    # SER (passado de "ser" — em DEFAULT_PREDICATES; alta confiança #045.1)
    "foi": "SER",
    "era": "SER",
    "eram": "SER",
    "was": "SER",
    "were": "SER",
    # CONECTA_A (EN)
    "connects": "CONECTA_A",
    "connected": "CONECTA_A",
    "connect": "CONECTA_A",
    # EXECUTA (processa/processam — DEFAULT_PREDICATES; alta confiança)
    "processa": "EXECUTA",
    "processam": "EXECUTA",
    "process": "EXECUTA",
    "processes": "EXECUTA",
    "processed": "EXECUTA",
    # --- #045.1 — verbos esportivos (mapeamento conservador; sem equívoco vago) ---
    # DEFENDEU — relação jogador↔clube
    "defendeu": "DEFENDEU",
    "defende": "DEFENDEU",
    "defender": "DEFENDEU",
    "defenderam": "DEFENDEU",
    "jogou por": "DEFENDEU",
    "joga por": "DEFENDEU",
    "jogou pelo": "DEFENDEU",
    "joga pelo": "DEFENDEU",
    "jogou": "DEFENDEU",
    "joga": "DEFENDEU",
    "jogar": "DEFENDEU",
    "vestiu": "DEFENDEU",
    "veste": "DEFENDEU",
    "vestiram": "DEFENDEU",
    "vestir": "DEFENDEU",
    "played for": "DEFENDEU",
    "play for": "DEFENDEU",
    "plays for": "DEFENDEU",
    "playing for": "DEFENDEU",
    "joined": "DEFENDEU",
    "joins": "DEFENDEU",
    "join": "DEFENDEU",
    "joining": "DEFENDEU",
    # VENCEU — título/competição
    "venceu": "VENCEU",
    "vence": "VENCEU",
    "vencer": "VENCEU",
    "venceram": "VENCEU",
    "ganhou": "VENCEU",
    "ganha": "VENCEU",
    "ganharam": "VENCEU",
    "ganhar": "VENCEU",
    "conquistou": "VENCEU",
    "conquista": "VENCEU",
    "conquistaram": "VENCEU",
    "conquistar": "VENCEU",
    "won": "VENCEU",
    "wins": "VENCEU",
    "win": "VENCEU",
    # LOCALIZADO_EM — clube/estádio↔cidade
    "localiza se em": "LOCALIZADO_EM",
    "localiza em": "LOCALIZADO_EM",
    "localizado em": "LOCALIZADO_EM",
    "localizada em": "LOCALIZADO_EM",
    "localizam se em": "LOCALIZADO_EM",
    "fica em": "LOCALIZADO_EM",
    "ficam em": "LOCALIZADO_EM",
    "ficara em": "LOCALIZADO_EM",
    "situado em": "LOCALIZADO_EM",
    "situada em": "LOCALIZADO_EM",
    "sediado em": "LOCALIZADO_EM",
    "sediada em": "LOCALIZADO_EM",
    "located in": "LOCALIZADO_EM",
    "based in": "LOCALIZADO_EM",
    # DISPUTOU — competição
    "disputou": "DISPUTOU",
    "disputa": "DISPUTOU",
    "disputar": "DISPUTOU",
    "disputaram": "DISPUTOU",
    "participou": "DISPUTOU",
    "participa": "DISPUTOU",
    "participar": "DISPUTOU",
    "participaram": "DISPUTOU",
    "competed": "DISPUTOU",
    "competes": "DISPUTOU",
    "compete": "DISPUTOU",
    # TREINOU — técnico↔clube
    "treinou": "TREINOU",
    "treina": "TREINOU",
    "treinar": "TREINOU",
    "treinaram": "TREINOU",
    "comandou": "TREINOU",
    "comanda": "TREINOU",
    "comandar": "TREINOU",
    "comandaram": "TREINOU",
    "coached": "TREINOU",
    "coaches": "TREINOU",
    "coach": "TREINOU",
    "coaching": "TREINOU",
}

# Modais: expressam modalidade/possibilidade, não afirmam fato → nunca mapear.
MODAL_PREDICATES = frozenset({
    "poder", "pode", "podia", "poderia", "poderao", "podem", "puder", "podendo",
    "dever", "deve", "devia", "deveria", "devem", "devera", "deverao", "devendo",
})

# Ambíguos: genéricos demais sem objeto/contexto → rejeitar com motivo próprio.
AMBIGUOUS_PREDICATES = frozenset({
    "passar", "passa", "passou", "passando", "passam",
    "aumentar", "aumenta", "aumentou", "aumentando", "aumentam",
})

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
    if key in MODAL_PREDICATES or _singularize(key) in MODAL_PREDICATES:
        return None, "modal_predicate"
    if key in AMBIGUOUS_PREDICATES or _singularize(key) in AMBIGUOUS_PREDICATES:
        return None, "ambiguous_predicate"
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
    # Verbos causais legítimos em DEFAULT_PREDICATES sem canônico claro → quarentena
    # (flexões: o guard recebe a forma crua, não o infinitivo)
    "causa", "causes", "causar", "resulta", "results", "resultar", "result",
    # #045.1 — verbos esportivos legítimos sem mapeamento claro → quarentena
    # (infinitivo + pretérito: o guard fallback recebe a forma flexionada crua)
    "contratar", "contratou", "liderar", "liderou", "atuuar", "atuou", "marcar",
    "pontuar", "campeoar", "assinar", "assinou", "transferir", "transferiu",
    # EN
    "be", "is", "are", "have", "has", "do", "make", "use", "utilize", "employ",
    "adopt", "create", "produce", "generate", "execute", "process", "connect",
    "associate", "link", "belong", "contain", "include", "define", "learn",
    "distribute", "influence", "possess", "derive", "allow", "represent",
    "constitute", "publish", "describe", "pass", "train", "optimize", "reduce",
    "increase", "improve", "apply", "build", "develop", "implement", "require",
    "recognize", "identify", "classify", "predict", "detect", "transform",
    "combine", "divide", "analyze", "run", "support", "provide", "enable",
    # #045.1 — EN sport verbs sem mapeamento claro → quarentena
    "score", "scored", "captain", "captained", "sign", "signed", "transfer",
})


def validate_predicate(raw: str) -> tuple[Optional[str], str]:
    """Guard determinístico: decide se ``raw`` pode ser predicado de uma tripla.

    Retorna ``(canonical | None, reason)`` com ``reason`` em:
    ``ok``, ``numeric_predicate``, ``url_or_code_predicate``, ``stopword_predicate``,
    ``nonverbal_predicate``, ``modal_predicate``, ``ambiguous_predicate``,
    ``unmapped_predicate``, ``invalid_predicate``.
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

    # 3) Modais/ambíguos têm motivo próprio (nunca mapeados).
    if key in MODAL_PREDICATES or _singularize(key) in MODAL_PREDICATES:
        return None, "modal_predicate"
    if key in AMBIGUOUS_PREDICATES or _singularize(key) in AMBIGUOUS_PREDICATES:
        return None, "ambiguous_predicate"

    # 4) Verbo legítimo fora do vocabulário (backlog #045) vs lixo.
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
