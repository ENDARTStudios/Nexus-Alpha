"""Nexus-Alpha — Extrator de entidades (sujeito/predicado/objeto) baseado em spaCy.

Implementa a Etapa 2 do plano de conclusão:
- Carrega um modelo spaCy leve (pt/en).
- Decompõe sentenças em tripletas {subject, predicate, object}.
- Atribui score de confiança baseado em clareza gramatical.

Fallback: se o modelo spaCy não estiver instalado/baixado, opera em modo
regex-heurístico para que o pipeline continue funcional.
"""
from __future__ import annotations

import collections
import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Optional

from .canonicalizer import SemanticCanonicalizer
from .predicate_mapper import INVALID_PREDICATE_REASONS, validate_predicate
from .span_validator import fold_span
from .triple_refiner import _known_entities

logger = logging.getLogger(__name__)

# #047 — boundary fix: conectivos iniciais (H3) e caudas verbais EN/PT.
_LEADING_CONNECTIVE_RE = re.compile(
    r"^(?:although|though|while|whereas|and|but|or|however|therefore|"
    r"e|ou|mas|embora|apesar(?:\s+de)?|entretanto|contudo)\s+",
    re.IGNORECASE,
)
_VERBAL_TAIL_RE = re.compile(
    r"\s+(?:said|says|say|told|tells|claimed|claims|announced|reported|"
    r"was|were|is|are|has|have|had|"
    r"disse|diz|afirma|afirmou|anunciou|era|foi)"
    r"(?:\s+(?:that\s+)?(?:he|she|it|they|we|you|him|her|them|us|"
    r"ele|ela|eles|elas|isso|isto|aquilo))?"
    r"\s*$",
    re.IGNORECASE,
)
def strip_boundary_noise(term: str) -> str:
    """Remove conectivo inicial e cauda verbal de span cru (#047 boundary)."""
    text = (term or "").strip()
    if not text:
        return ""
    prev = None
    while prev != text:
        prev = text
        text = _LEADING_CONNECTIVE_RE.sub("", text).strip()
        text = _VERBAL_TAIL_RE.sub("", text).strip()
    return text


def rescue_truncated_toponym(term: str, full_text: str) -> str:
    """Resgata topônimo ``São <Term>`` quando o span veio truncado só ``<Term>``."""
    cleaned = (term or "").strip()
    if not cleaned or " " in cleaned or not full_text:
        return cleaned
    pattern = re.compile(rf"\bS[ãa]o\s+{re.escape(cleaned)}\b")
    match = pattern.search(full_text)
    if match:
        return match.group(0)
    return cleaned


def is_function_word_span(term: str) -> bool:
    """Span composto só por palavras fechadas (ex.: ``E O``) — nunca entidade (#047)."""
    tokens = (term or "").lower().split()
    if not tokens:
        return True
    function_words = {
        "e", "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da",
        "dos", "das", "em", "no", "na", "nos", "nas", "com", "sem", "por", "para",
        "ao", "aos", "à", "às", "que", "se", "lhe", "eles", "elas",
        "and", "or", "but", "of", "to", "in", "on", "at", "for", "with", "by",
        "from", "as", "the", "a", "an", "it", "its", "is", "are", "was", "were",
        "be", "been", "this", "that", "he", "she", "they", "we", "you",
    }
    return all(tok in function_words for tok in tokens)


# #058.11.1 (F3) — filtro determinístico de candidatos a sentença.
# Objetivo: remover fragmentos evidentes (títulos de wiki, refs, captions,
# linhas de tabela/infobox, números soltos) ANTES da extração, sem tocar na
# regra de root verbal e sem análise sintática profunda. Conservador na
# direção errada: prefere deixar passar lixo a bloquear frase nominal
# legítima (combustível do F1 #058.11.2).
_ALPHA_TOKEN_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
_DIGIT_TOKEN_RE = re.compile(r"\d+")

# Marcadores duros de ruído: nunca são proposição, mesmo com verbo.
_HARD_NOISE_RES = (
    re.compile(r"[\u200b\u2060\ufeff]"),  # zero-width/BOM (colagem de infobox)
    re.compile(r"(?i)wikipédia,?\s*a\s*enciclopédia\s*livre"),
    re.compile(r"(?i)^.{0,60}\bwikipedia\b"),
    re.compile(r"(?i)\bimage\s+(?:source|caption)\b"),
    re.compile(r"(?i)\bfigure\s+caption\b"),
    re.compile(r"(?i)\bshare\s+close\s+panel\b"),
    re.compile(r"(?i)\bshare\s+page\b"),
    re.compile(r"(?i)\bcopy\s+link\b"),
    re.compile(r"(?i)\blive\s+reporting\b"),
    re.compile(r"(?i)\breport\s*\(active\)"),
    re.compile(r"(?i)^\W*\d{4}\s*\)"),  # linha de infobox com ano
    re.compile(r"(?i)^\s*(?:retrieved|archived)\s+\d"),
    re.compile(r"(?i)\bcs1\s+(?:maint|doi)"),
    re.compile(r"(?i)\bjump\s+(?:up|to)\b"),
)

# Marcadores de navegação/label: rejeitados só quando não há verbo.
_NAV_NOISE_RES = (
    re.compile(r"(?i)^\s*(?:see\s+also|external\s+links?|further\s+reading|"
               r"bibliography|contents|notes?|ver\s+também|refer[êe]ncias|"
               r"links?\s+externos|notas)\b"),
    re.compile(r"(?i)^\s*edit(?:ar)?\s*$"),
    re.compile(r"(?i)^\s*(?:full\s+name|nickname|date\s+of\s+birth|place\s+of\s+birth|"
               r"relatives|parents|personal\s+information)\b"),
)

# Indício de proposição (fraco, determinístico): copulas/auxiliares EN,
# formas irregulares comuns EN, desinências conjugadas PT e EN (-ed/-ing).
_VERB_HINT_RE = re.compile(
    r"(?:"
    r"\b(?:is|are|was|were|am|be|been|being|has|have|had|do|does|did|"
    r"will|would|shall|should|can|could|may|might|must|"
    r"won|win|wins|played|play|plays|held|hold|holds|took|take|takes|"
    r"led|lead|leads|made|make|makes|went|go|goes|came|come|comes|"
    r"began|begin|became|become|becomes|signed|sign|signs|scored|score|scores|"
    r"defended|defend|defends|joined|join|joins|founded|found|returns|returned|"
    r"return|moved|move|moves|left|leave|leaves|known|called|born|based|"
    r"features|feature|includes|include|remains|remain|lives|live|"
    r"uses|use|uses|needs|need|says|said|claim|claimed|reported|report|"
    r"consists|consist|provides|provide|offers|offer|attracts|attract|"
    r"celebrates|celebrate|appeared|appear|started|start|ended|end|"
    r"playing|played)\b"
    r"|(?:[a-zà-ÿ]{2,}(?:ed|ing)\b)"
    r"|(?:[a-zà-ÿ]{2,}(?:ou|eu|iu|ui|ei|amos|emos|imos|ava|avam|iam|"
    r"aram|eram|iram|ando|endo|indo|ado|ido|ada|ida)\b)"
    r"|\b(?:é|era|eram|foi|foram|está|estão|estao|estava|estavam|"
    r"tem|tinha|tinham|havia|ser|estar|possui|possuem|disputa|disputam|"
    r"venceu|jogou|defendeu|conquistou|nasceu|sagrou|liderou|atuou|"
    r"representou|iniciou|encerrou|retornou|mudou|chegou|saiu|deixou|"
    r"ganhou|perdeu|tornou|passou|faz|fazem|diz|dizem|afirma|afirmou|disse)\b"
    # "são" só como copula: não casa "São <Nome>" (nome próprio).
    r"|\b(?:são|sao)(?-i:(?!\s+[A-ZÁÂÃÉÊÍÓÔÕÚ]))\b"
    r")",
    re.IGNORECASE,
)


def classify_sentence_candidate(text: str) -> Optional[str]:
    """Motivo de rejeição de um candidato a sentença, ou ``None`` se aceito.

    Regras, nesta ordem (determinísticas, sem spaCy/LLM):
    1. menos de 3 tokens alfabéticos (cobre numérico puro, pontuação, ``[1]``);
    2. marcador duro de ruído (título wiki, caption, ref, infobox, zero-width);
    3. indício de proposição (copula/auxiliar/desinência) → aceita;
    4. marcador de navegação/label → rejeita;
    5. >= 2 tokens numéricos sem verbo (linha de tabela/placar/infobox);
    6. >= 4 tokens alfabéticos com vírgula (aposto) ou >= 2 termos
       capitalizados (entidades nomeadas) → aceita (frase nominal p/ F1);
    7. caso contrário → rejeita.
    """
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    alpha_tokens = _ALPHA_TOKEN_RE.findall(cleaned)
    if len(alpha_tokens) < 3:
        return "too_short"
    for pattern in _HARD_NOISE_RES:
        if pattern.search(cleaned):
            return "noise_marker"
    has_verb_hint = bool(_VERB_HINT_RE.search(cleaned))
    if has_verb_hint:
        return None
    for pattern in _NAV_NOISE_RES:
        if pattern.search(cleaned):
            return "noise_marker"
    if len(_DIGIT_TOKEN_RE.findall(cleaned)) >= 2:
        return "non_propositional_fragment"
    if len(alpha_tokens) >= 4:
        tokens = cleaned.split()
        mid_capitals = sum(
            1 for tok in tokens[1:] if tok[:1].isalpha() and tok[:1].isupper()
        )
        if "," in cleaned or mid_capitals >= 2:
            return None
    return "non_propositional_fragment"


def is_propositional_sentence(text: str) -> bool:
    """``True`` se o candidato sobrevive ao filtro F3 de input."""
    return classify_sentence_candidate(text) is None


# #058.11.2 (F1) — extração nominal/copular gateada.
# O modelo PT sobre texto EN produz parses sem ``cop``/``nsubj`` utilizáveis,
# então relações nominais EN são casadas por frames regex determinísticos no
# texto da sentença; o caminho dep-SER (root NOUN/PROPN + ``cop``) cobre PT.
# Regra de ouro: só emite tripla quando sujeito+objeto passam o gate de
# entidade forte (anti-inflação de SER e anti-objeto genérico).

# Substantivos genéricos: span contendo algum destes nunca é entidade forte.
_GENERIC_NOUNS = frozenset({
    "club", "clubs", "team", "teams", "side", "squad", "player", "players",
    "footballer", "striker", "goalkeeper", "defender", "midfielder", "coach",
    "manager", "crowd", "fans", "fan", "city", "country", "state", "region",
    "father", "son", "daughter", "mother", "brother", "year", "years",
    "season", "game", "match", "title",
    "clube", "clubes", "time", "times", "equipe", "elenco", "jogador",
    "jogadores", "futebolista", "goleiro", "zagueiro", "tecnico", "torcida",
    "cidade", "pais", "estado", "regiao", "pai", "filho", "filha", "mae",
    "irmao", "ano", "anos", "temporada", "jogo", "jogos", "partida",
    "partidas", "titulo", "titulos",
})

# Copulas PT que caracterizam o caminho dep-SER (nunca formas EN "is/was": o
# modelo PT sobre texto EN cospe lemma/texto errado — fora daqui, sem SER).
_PT_COPULA_FORMS = frozenset({
    "é", "era", "eram", "foi", "foram", "são", "sao",
    "está", "esta", "estão", "estao", "estava", "estavam", "estiveram",
})

# Caudas verbais/auxiliares no sujeito nominal (``Pelé began playing`` → ``Pelé``).
_NOMINAL_SUBJ_TAILS = frozenset({
    "began", "begin", "starts", "started", "start", "playing", "played",
    "plays", "play", "became", "become", "joins", "joined", "join",
    "signs", "signed", "sign", "returns", "returned", "return",
    "comes", "came", "come", "goes", "went", "go", "led", "leads", "made",
    "makes", "held", "holds", "scored", "scores", "defended", "defends",
    "founded", "found", "moved", "moves", "left", "leaves", "known",
    "called", "born", "based", "disputa", "disputou", "jogou", "joga",
    "defendeu", "conquistou", "venceu", "ganhou", "treinou", "assinou",
    "assina", "iniciou", "retornou", "chegou", "saiu", "fica", "ficam",
    "sediado", "sediada", "localizado", "localizada", "fundado", "fundada",
    "é", "foi", "era", "eram", "são", "is", "are", "was", "were",
    "be", "been", "being", "has", "have", "had",
    # participios/advérgios de atribuição (``Pelé também foi convidado a'' → ``Pelé'')
    "a", "ao", "à", "também", "ainda", "inicialmente", "convidado",
    "convidada", "convocado", "convocada", "contratado", "contratada",
    "transferido", "transferida", "emprestado", "emprestada",
})

# Frames nominais EN/PT: (predicado canônico, padrão). Primeiro frame que casa
# e passa os gates vence; sem frame, tenta dep-SER; sem nada, ``nominal_no_pattern``.
_NOMINAL_FRAMES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("LOCALIZADO_EM", re.compile(
        r"\b(?:based|located|situated)\s+(?:in|at)\b"
        r"|\b(?:sediad[oa]|localizad[oa]|situad[oa])\s+(?:em|no|na|nos|nas)\b"
        r"|\b(?:fica|ficam|ficava|ficavam)\s+(?:em|no|na|nos|nas)\b"
        r"|\bcom\s+sede\s+(?:em|no|na|nos|nas)\b",
        re.IGNORECASE,
    )),
    ("DEFENDEU", re.compile(
        r"\b(?:jogou|joga|jogar)\s+(?:pelo|pela|por|no|na|nos|nas)\b"
        r"|\batuou\s+(?:na|no|nas|nos|em|pelo|pela)\b"
        r"|\b(?:played|plays|playing|play)\b(?:\s+[\w'-]+){0,7}?\s+for\b"
        r"|\b(?:is|was|are|were)\s+(?:a|an)\s+[\w'-]+\s+for\b",
        re.IGNORECASE,
    )),
    ("POSSUIR", re.compile(
        r"\bhome\s+(?:ground|stadium|arena)\s+(?:is|was|are|were)\b",
        re.IGNORECASE,
    )),
    ("VENCEU", re.compile(
        r"\bwon\b|\bchampions?\s+of\b"
        r"|\b(?:foi|é|era|vira)\s+(?:o\s+|a\s+)?campe[ãa]o\b",
        re.IGNORECASE,
    )),
)

# Segmentos de sujeito: vírgula/ponto-e-vírgula, fim de sentença (``Stadium. The
# team's home ground...``) ou travessão espaçado.
_SUBJ_SEGMENT_SPLIT_RE = re.compile(
    r"\s*(?:,|;|(?<=\w)\.\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕ])|\s+[—–-]+)\s*"
)
# Corte de objeto: pontuação/parêntese — o complemento de frame é uma cláusula.
_OBJ_CUT_RE = re.compile(r"[.,;:!?()\[\]]")
# Corte "duro" (sem vírgula) para o candidato estendido: vírgula costuma
# fechar o span (``..., named in honor of ...``), mas às vezes a localização
# continua (``bairro X, na cidade do Rio de Janeiro``).
_OBJ_CUT_HARD_RE = re.compile(r"[.!?;:()\[\]]")
# Preposições/contracções iniciais de objeto: span_validator rejeita
# ``object_prepositional_phrase`` quando começa por prep (ex.: ``da Taça...``).
_OBJ_LEADING_PREP = frozenset({
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "num", "numa",
    "em", "por", "para", "com", "sem", "sob", "entre", "apos",
    "in", "of", "for", "at", "on", "with", "by", "from", "to", "into", "over",
    "after", "during", "between", "under", "near",
})
# Artigos EN internos ao sujeito (``Stadium The team's`` — heading colada).
_EN_ARTICLES = frozenset({"the", "a", "an"})
# Cauda preposicional + número/idade (``at age 15``, ``por 12 anos``).
_OBJ_TAIL_RE = re.compile(
    r"\s+(?:for|at|em|por|in|from|since|desde|during|between|no|na)"
    r"\s+(?:\d|age\b|idade\b)",
    re.IGNORECASE,
)
_POSSESSIVE_SUFFIX_RE = re.compile(r"['’]s$", re.IGNORECASE)


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EntityExtractor:
    """Extrator leve de tripletas semânticas a partir de texto limpo."""

    DEFAULT_PREDICATES = {
        "é", "são", "foi", "usa", "utiliza", "processa", "cria", "gera",
        "causa", "resulta", "conecta", "possui", "tem", "define",
        "is", "are", "was", "uses", "uses", "processes", "creates",
        "generates", "causes", "results", "connects", "has", "defines",
    }

    def __init__(
        self,
        model: str = "pt_core_news_sm",
        enable_fallback: bool = True,
        enable_nominal_copular: bool = True,
    ) -> None:
        self.model_name = model
        self.enable_fallback = enable_fallback
        self.enable_nominal_copular = enable_nominal_copular
        self._nlp = None
        self.rejection_reasons: collections.Counter = collections.Counter()
        # #058.11.2 — gates do caminho nominal, separados de
        # ``rejection_reasons`` (allowlist fixa em test_analyze_text).
        self.nominal_gate_reasons: collections.Counter = collections.Counter()
        try:
            import spacy  # type: ignore
            self._nlp = spacy.load(model)
            logger.info("spaCy carregado: %s", model)
        except Exception as exc:
            logger.warning("spaCy indisponível (%s) — usando fallback heurístico.", exc)
            self._nlp = None

    @staticmethod
    def _is_clean(token: str) -> bool:
        return bool(token) and len(token) > 1 and not token.isspace()

    @staticmethod
    def _confidence_for(subject: str, obj: str, predicate: str) -> float:
        if not subject or not obj or not predicate:
            return 0.0
        base = 0.5
        if len(subject.split()) <= 4:
            base += 0.15
        if len(obj.split()) <= 4:
            base += 0.15
        if predicate.lower() in EntityExtractor.DEFAULT_PREDICATES:
            base += 0.15
        return round(min(0.99, base), 3)

    PRONOUN_STARTS = {
        "que", "isso", "isto", "aquilo", "ele", "ela", "eles", "elas", "seu",
        "sua", "seus", "suas", "este", "esta", "estes", "estas", "esse", "essa",
        "esses", "essas", "lhe", "lhes", "me", "te", "nos", "vos", "o", "a",
        "os", "as", "algo", "tudo", "nada",
    }

    TRAILING_STOP = {
        "que", "em", "de", "da", "do", "das", "dos", "a", "o", "as", "os",
        "e", "ao", "aos", "com", "para", "por", "no", "na", "nos", "nas",
        "se", "como", "mais",
    }

    @classmethod
    def _phrase_text(cls, token, max_tokens: int = 6) -> str:
        tokens = [t for t in token.subtree if not t.is_punct and not t.is_space]
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
        while tokens and tokens[-1].lower_ in cls.TRAILING_STOP:
            tokens.pop()
        return " ".join(t.text for t in tokens).strip()

    NOISE_MARKERS = {
        "portal", "categoria", "wikipédia", "wikipedia", "editar", "código",
        "ver também", "commons", "wikcionário", "wikidata", "ficheiro",
    }

    LEADING_ARTICLES = {
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "the", "an",
        "this", "that", "these", "those",
    }

    @classmethod
    def _normalize_term(cls, term: str) -> str:
        """Remove artigos/determinantes iniciais para aumentar o cruzamento entre fontes."""
        tokens = term.split()
        while tokens and tokens[0].lower() in cls.LEADING_ARTICLES:
            tokens.pop(0)
        return " ".join(tokens).strip()

    @classmethod
    def _valid_term(cls, term: str) -> bool:
        if not term or len(term) < 3:
            return False
        if "|" in term:
            return False
        lowered = term.lower()
        if any(marker in lowered for marker in cls.NOISE_MARKERS):
            return False
        tokens = term.split()
        if len(tokens) > 5:
            return False
        if tokens[0].lower() in cls.PRONOUN_STARTS:
            return False
        # Assinatura de lista de links: 4+ tokens com 3+ capitalizados ("sopa" de nomes próprios)
        capitalized = sum(1 for t in tokens if t[:1].isupper())
        if len(tokens) >= 4 and capitalized >= 3:
            return False
        return any(ch.isalpha() for ch in term)

    # --- #058.11.2 (F1) — portas do caminho nominal/copular -----------------

    _KNOWN_ENTITIES: Optional[frozenset[str]] = None
    _ALIAS_PATTERN: Optional["re.Pattern[str]"] = None

    def _known_entity_set(self) -> frozenset[str]:
        """Whitelist do dicionário canônico (mesma do ``triple_refiner``)."""
        if EntityExtractor._KNOWN_ENTITIES is None:
            EntityExtractor._KNOWN_ENTITIES = _known_entities(SemanticCanonicalizer())
        return EntityExtractor._KNOWN_ENTITIES

    def _alias_pattern(self) -> Optional["re.Pattern[str]"]:
        """Regex única de aliases para containment (``the Brazilian club Santos``)."""
        if EntityExtractor._ALIAS_PATTERN is None:
            aliases = sorted(
                (a for a in self._known_entity_set() if len(a) >= 4 or " " in a),
                key=len,
                reverse=True,
            )
            if not aliases:
                return None
            EntityExtractor._ALIAS_PATTERN = re.compile(
                r"\b(?:" + "|".join(re.escape(a) for a in aliases) + r")\b"
            )
        return EntityExtractor._ALIAS_PATTERN

    def _entity_strength(self, span: str, predicate: str) -> str:
        """``strong | generic | weak`` — gate anti-inflação (#058.11.2).

        1) span inteiro no dicionário → forte; 2) containment de alias → forte
        (exceto ``SER``, onde só o span canônico inteiro vale); 3) substantivo
        genérico → ``generic``; 4) >= 2 tokens capitalizados → forte; senão
        ``weak``.
        """
        folded = fold_span(span)
        if not folded:
            return "weak"
        if folded in self._known_entity_set():
            return "strong"
        if predicate != "SER":
            pattern = self._alias_pattern()
            if pattern is not None and pattern.search(folded):
                return "strong"
        if any(token in _GENERIC_NOUNS for token in folded.split()):
            return "generic"
        # Span começando minúsculo (sem entidade conhecida/alias) nunca é
        # forte: mata sujeito-invertido tipo ``second consecutive World Cup``.
        span_tokens = span.split()
        if span_tokens and span_tokens[0][:1].islower():
            return "weak"
        caps = sum(
            1 for tok in span.split() if tok[:1].isalpha() and tok[:1].isupper()
        )
        return "strong" if caps >= 2 else "weak"

    @staticmethod
    def _trim_generic_prefix(text: str) -> str:
        """Corta prefixo genérico até a entidade (``the Brazilian team Botafogo``)."""
        tokens = text.split()
        gen_idx = next(
            (
                i for i, tok in enumerate(tokens)
                if tok.lower().strip(".,;:!?()") in _GENERIC_NOUNS
            ),
            None,
        )
        if gen_idx is None:
            return text
        for j in range(gen_idx + 1, len(tokens)):
            tok = tokens[j]
            if len(tok) > 1 and tok[:1].isalpha() and tok[:1].isupper():
                return " ".join(tokens[j:])
        return text

    @classmethod
    def _nominal_term_ok(cls, term: str) -> bool:
        """Como ``_valid_term`` sem a assinatura de lista de links.

        Objetos de frame são delimitados por pontuação (uma cláusula), então a
        regra de "sopa de nomes próprios" aqui cortaria entidades legítimas de
        4 tokens (``Estádio Olímpico Nilton Santos``).
        """
        if not term or len(term) < 3:
            return False
        if "|" in term:
            return False
        lowered = term.lower()
        if any(marker in lowered for marker in cls.NOISE_MARKERS):
            return False
        tokens = term.split()
        if len(tokens) > 5:
            return False
        if tokens[0].lower() in cls.PRONOUN_STARTS:
            return False
        # Inicial solta no início (``W Botafogo``, ``v Palmeiras``: tabelas/ placares)
        first = tokens[0].strip(".,;:!?()'\u2019\"")
        if first.isalnum() and len(first) == 1:
            return False
        # Dois+ tokens só-numérico (``Palmeiras 1 3 Serie``): resíduo de placar.
        # Um token numérico continua ok (``2024 Copa Libertadores``).
        if sum(1 for tok in tokens if tok.isdigit()) >= 2:
            return False
        return any(ch.isalpha() for ch in term)

    def _rescue_known_entity(self, text: str) -> Optional[str]:
        """Span inválido que contém entidade conhecida → usa a própria entidade.

        Ex.: sujeito-atribuição ``João Saldanha em Histórias do Futebol
        Garrincha`` (7 tokens, ``term_ok`` falso) → ``garrincha``. Só resgata
        entidades da whitelist curada — nunca inventa termo.
        """
        pattern = self._alias_pattern()
        if pattern is None or not text:
            return None
        match = pattern.search(fold_span(text))
        return match.group(0) if match else None

    def _finalize_nominal_subject(self, text: str, full_text: str, predicate: str) -> str:
        """Sujeito final: posesivo, artigo interno, cauda verbal, topônimo."""
        cleaned = _POSSESSIVE_SUFFIX_RE.sub("", (text or "").strip())
        cleaned = strip_boundary_noise(cleaned)
        # Heading colado: ``Stadium The team's`` → ``The team`` (corta o prefixo
        # fraco antes do artigo; mantém quando o prefixo é entidade forte).
        tokens = cleaned.split()
        art_idx = next(
            (
                i for i, tok in enumerate(tokens)
                if tok.lower().strip(".,;:!?()") in _EN_ARTICLES
            ),
            None,
        )
        if art_idx is not None and art_idx >= 1:
            prefix = " ".join(tokens[:art_idx])
            if self._entity_strength(prefix, predicate) != "strong":
                cleaned = " ".join(tokens[art_idx:])
                tokens = cleaned.split()
        while tokens and tokens[-1].lower().strip(".,;:!?()") in _NOMINAL_SUBJ_TAILS:
            tokens.pop()
            cleaned = " ".join(tokens)
        cleaned = rescue_truncated_toponym(cleaned.strip(), full_text)
        return self._normalize_term(cleaned).strip()

    def _clean_nominal_subject(self, prefix: str, predicate: str, full_text: str) -> str:
        """Sujeito = texto anterior ao frame; segmento forte vence (último→primeiro)."""
        text = re.sub(r"\s+", " ", (prefix or "")).strip()
        if not text:
            return ""
        text = strip_boundary_noise(text)
        segments = [
            seg for seg in _SUBJ_SEGMENT_SPLIT_RE.split(text) if seg and seg.strip()
        ]
        if len(segments) > 1:
            chosen = segments[-1].strip()
            for seg in reversed(segments):
                candidate = self._finalize_nominal_subject(seg, full_text, predicate)
                if candidate and self._entity_strength(candidate, predicate) == "strong":
                    chosen = seg.strip()
                    break
            text = chosen
        return self._finalize_nominal_subject(text, full_text, predicate)

    def _clean_nominal_object(self, suffix: str, predicate: str, full_text: str,
                              hard_cut: bool = False) -> str:
        """Objeto = complemento do frame; corte em pontuação/cauda preposicional."""
        text = re.sub(r"\s+", " ", (suffix or "")).strip()
        if not text:
            return ""
        cut = (_OBJ_CUT_HARD_RE if hard_cut else _OBJ_CUT_RE).search(text)
        if cut:
            text = text[:cut.start()]
        if hard_cut:
            # Vírgula espaçada (wikitext) é orfa — ``Noroeste , de Bauru`` →
            # ``Noroeste de Bauru``. Vírgula colada (``bairro, na cidade``)
            # é cadeia de localização e fica intacta.
            text = re.sub(r"\s,\s", " ", text)
        cut = _OBJ_TAIL_RE.search(text)
        if cut:
            text = text[:cut.start()]
        text = text.strip()
        if not text:
            return ""
        tokens = text.split()
        while tokens and tokens[0].lower().strip(".,;:!?()") in _OBJ_LEADING_PREP:
            tokens.pop(0)
        text = " ".join(tokens)
        if not text:
            return ""
        if predicate != "SER":
            text = self._trim_generic_prefix(text)
        text = strip_boundary_noise(text)
        text = rescue_truncated_toponym(text.strip(), full_text)
        return self._normalize_term(text).strip()

    def _build_nominal_triple(
        self, subject: str, obj: str, predicate: str
    ) -> Optional[Triple]:
        """Aplica os gates de entidade e constrói a tripla nominal (ou ``None``)."""
        if not subject or not obj:
            self.nominal_gate_reasons["nominal_empty_span"] += 1
            return None
        if is_function_word_span(subject) or is_function_word_span(obj):
            self.nominal_gate_reasons["nominal_function_word_span"] += 1
            return None
        if not self._nominal_term_ok(subject):
            rescued = self._rescue_known_entity(subject)
            if rescued:
                subject = rescued
                self.nominal_gate_reasons["nominal_subject_rescued"] += 1
            else:
                self.nominal_gate_reasons["nominal_invalid_term"] += 1
                return None
        if not self._nominal_term_ok(obj):
            rescued = self._rescue_known_entity(obj)
            if rescued:
                obj = rescued
                self.nominal_gate_reasons["nominal_object_rescued"] += 1
            else:
                self.nominal_gate_reasons["nominal_invalid_term"] += 1
                return None
        obj_strength = self._entity_strength(obj, predicate)
        if obj_strength == "generic":
            self.nominal_gate_reasons["nominal_object_generic"] += 1
            return None
        if obj_strength != "strong":
            self.nominal_gate_reasons["nominal_object_weak"] += 1
            return None
        subj_strength = self._entity_strength(subject, predicate)
        if subj_strength == "weak":
            self.nominal_gate_reasons["nominal_subject_weak"] += 1
            return None
        if subj_strength == "generic" and predicate == "SER":
            self.nominal_gate_reasons["nominal_generic_subject_ser"] += 1
            return None
        return Triple(
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=self._confidence_for(subject, obj, predicate),
        )

    def _nominal_from_frames(self, text: str, full_text: str) -> tuple[Optional[Triple], bool]:
        """Frames regex no texto da sentença. Retorna ``(tripla, algum_frame_casou)``.

        Objeto tem dois candidatos: corte na primeira pontuação (padrão) e
        corte só em fim de frase (``hard_cut``) — o segundo só é tentado quando
        o primeiro reprova nos gates (ex.: localização que continua após
        vírgula). Em sucesso, os contadores do candidato reprovado são
        desfeitos (só contam rejeições definitivas).
        """
        matched = False
        for predicate, pattern in _NOMINAL_FRAMES:
            match = pattern.search(text)
            if match is None:
                continue
            matched = True
            subject = self._clean_nominal_subject(
                text[:match.start()], predicate, full_text
            )
            suffix = text[match.end():]
            counters_before = dict(self.nominal_gate_reasons)
            obj = self._clean_nominal_object(suffix, predicate, full_text)
            triple = self._build_nominal_triple(subject, obj, predicate)
            if triple is None:
                obj_hard = self._clean_nominal_object(
                    suffix, predicate, full_text, hard_cut=True
                )
                if obj_hard != obj:
                    triple = self._build_nominal_triple(
                        subject, obj_hard, predicate
                    )
            if triple is not None:
                self.nominal_gate_reasons.clear()
                self.nominal_gate_reasons.update(counters_before)
                return triple, True
        return None, matched

    def _dep_ser_triple(self, sent, full_text: str) -> tuple[Optional[Triple], bool]:
        """dep-SER PT: root NOUN/PROPN + ``cop`` (forms PT) + ``nsubj``.

        Segundo elemento: ``True`` se o caminho foi estruturalmente aplicável
        (root + cop) — usado para não contar ``nominal_no_pattern`` quando o
        gate, e não o padrão, rejeitou.
        """
        root = next((t for t in sent if t.dep_ == "ROOT"), None)
        if root is None or root.pos_ not in ("NOUN", "PROPN"):
            return None, False
        cop = next(
            (
                c for c in root.children
                if c.dep_ == "cop" and c.text.lower() in _PT_COPULA_FORMS
            ),
            None,
        )
        if cop is None:
            return None, False
        subj_tok = next(
            (c for c in root.children if c.dep_ in ("nsubj", "nsubj:pass")), None
        )
        if subj_tok is None:
            self.nominal_gate_reasons["nominal_dep_ser_no_subject"] += 1
            return None, True
        subject = self._finalize_nominal_subject(
            self._phrase_text(subj_tok), full_text, "SER"
        )
        skip = {subj_tok.i, cop.i}
        obj_parts: list[str] = []
        for tok in root.subtree:
            if tok.i < root.i or tok.i in skip:
                continue
            if tok.is_punct or tok.is_space:
                break
            obj_parts.append(tok.text)
        obj = self._clean_nominal_object(" ".join(obj_parts), "SER", full_text)
        return self._build_nominal_triple(subject, obj, "SER"), True

    def _extract_nominal_copular(self, sent, full_text: str) -> Optional[Triple]:
        """Tenta frames e dep-SER numa sentença em que o caminho verbal falhou."""
        text = re.sub(r"\s+", " ", sent.text).strip()
        # O modelo PT quebra sentença no possessivo EN ("Botafogo" | "'s home
        # ground is ..."); cola o token anterior quando não há pontuação entre.
        if text.startswith(("'s", "’s")) and sent.start > 0:
            prev = sent.doc[sent.start - 1]
            if not prev.is_punct and prev.text.strip():
                text = f"{prev.text} {text}"
        if not text:
            return None
        triple, matched = self._nominal_from_frames(text, full_text)
        if triple is not None:
            return triple
        triple, dep_applicable = self._dep_ser_triple(sent, full_text)
        if triple is not None:
            return triple
        if not matched and not dep_applicable:
            self.nominal_gate_reasons["nominal_no_pattern"] += 1
        return None

    def _extract_verbal_sentence(self, sent, text: str) -> Optional[Triple]:
        """Caminho verbal original de ``extract_spacy`` (root VERB/AUX)."""
        root = next((t for t in sent if t.dep_ == "ROOT"), None)
        if root is None or root.pos_ not in ("VERB", "AUX"):
            return None
        predicate, predicate_reason = validate_predicate(root.lemma_)
        if predicate_reason in INVALID_PREDICATE_REASONS:
            self.rejection_reasons[predicate_reason] += 1
            return None
        if predicate is None:
            predicate = root.lemma_.strip().upper()
        subj_tok = next(
            (c for c in root.children if c.dep_ in ("nsubj", "nsubj:pass")), None
        )
        obj_tok = next(
            (
                c for c in root.children
                if c.dep_ in ("obj", "dobj", "iobj", "attr", "obl", "xcomp")
            ),
            None,
        )
        if subj_tok is None or obj_tok is None:
            return None
        subject = self._normalize_term(strip_boundary_noise(self._phrase_text(subj_tok)))
        obj = self._normalize_term(strip_boundary_noise(self._phrase_text(obj_tok)))
        subject = rescue_truncated_toponym(subject, text)
        obj = rescue_truncated_toponym(obj, text)
        if is_function_word_span(subject) or is_function_word_span(obj):
            return None
        if not self._valid_term(subject) or not self._valid_term(obj):
            return None
        return Triple(
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=self._confidence_for(subject, obj, predicate),
        )

    def extract_spacy(self, text: str, max_triples: int = 25) -> list[Triple]:
        if self._nlp is None:
            return []
        doc = self._nlp(text)
        triples: list[Triple] = []
        for sent in doc.sents:
            # #058.11.1 (F3): descarta fragmento não-proposicional antes da
            # árvore de decisão — a regra de root VERB/AUX abaixo não muda.
            if not is_propositional_sentence(sent.text):
                continue
            # #058.11.2 (F1): por sentença, verbal primeiro; se falhar e a flag
            # estiver ligada, tenta nominal (frames/dep-SER). Interleaved na
            # ordem do documento: sentenças-alvo tardias não esgotam o cap com
            # triplas verbais antes (a 2ª passada global nunca tinha slot).
            # Com a flag desligada o fluxo é byte-idêntico ao pré-F1 (verbal
            # append verbatim, sem dedup, como o HEAD).
            triple = self._extract_verbal_sentence(sent, text)
            if triple is None and self.enable_nominal_copular:
                triple = self._extract_nominal_copular(sent, text)
                if triple is not None:
                    key = (
                        triple.subject.casefold(),
                        triple.predicate.casefold(),
                        triple.object.casefold(),
                    )
                    existing = {
                        (t.subject.casefold(), t.predicate.casefold(), t.object.casefold())
                        for t in triples
                    }
                    if key in existing:
                        continue
            if triple is None:
                continue
            triples.append(triple)
            if len(triples) >= max_triples:
                break
        return triples

    def extract_fallback(self, text: str, max_triples: int = 10) -> list[Triple]:
        """Heurística regex para SVO sem dependências externas."""
        pattern = re.compile(
            r"([A-ZÁ-Ú][\wÀ-ſ\s]{2,40}?)\s+"
            r"(" + "|".join(re.escape(p) for p in self.DEFAULT_PREDICATES) + r")\s+"
            r"([\wÀ-ſ\s]{2,40})[\.\;\,]",
            re.IGNORECASE,
        )
        triples: list[Triple] = []
        for match in pattern.finditer(text):
            subj, pred, obj = (g.strip() for g in match.groups())
            subj = self._normalize_term(strip_boundary_noise(subj))
            obj = self._normalize_term(strip_boundary_noise(obj))
            subj = rescue_truncated_toponym(subj, text)
            obj = rescue_truncated_toponym(obj, text)
            if is_function_word_span(subj) or is_function_word_span(obj):
                continue
            predicate, predicate_reason = validate_predicate(pred)
            if predicate_reason in INVALID_PREDICATE_REASONS:
                self.rejection_reasons[predicate_reason] += 1
                continue
            if predicate is None:
                predicate = pred.strip().upper()
            triples.append(Triple(
                subject=subj,
                predicate=predicate,
                object=obj,
                confidence=self._confidence_for(subj, obj, predicate),
            ))
            if len(triples) >= max_triples:
                break
        return triples

    # #058.8 — banda sparse: com o modelo PT sobre texto EN, o spaCy devolve
    # 1–7 triplas (vs 13–25 do regex offline) e o antigo `if not triples`
    # nunca acionava o fallback. Corte empírico: wiki PT >= 12, EN
    # problemático <= 7. Condição estrita `<` (fronteira congelada em teste).
    SPACY_SPARSE_MIN = 10

    def extract(self, text: str, max_triples: int = 25) -> list[Triple]:
        spacy_triples = self.extract_spacy(text, max_triples=max_triples)
        # Caminho denso (>= min) ou fallback desabilitado: retorno verbatim,
        # idêntico ao anterior — o regex nem é calculado (lazy).
        if len(spacy_triples) >= self.SPACY_SPARSE_MIN or not self.enable_fallback:
            return spacy_triples
        fallback_triples = self.extract_fallback(text, max_triples=max_triples)
        # spaCy == 0: fallback puro, verbatim (banda 0 inalterada).
        if not spacy_triples:
            return fallback_triples
        # Banda sparse (1..9): fallback primeiro (determinístico e já
        # validado), depois as triplas só-spaCy; dedupe com casefold.
        seen: set[tuple[str, str, str]] = set()
        merged: list[Triple] = []
        for triple in fallback_triples + spacy_triples:
            key = (
                triple.subject.casefold(),
                triple.predicate.casefold(),
                triple.object.casefold(),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(triple)
        return merged[:max_triples]

    def enrich_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Adiciona extracted_entities ao NexusPayload a partir do conteúdo minerado."""
        text = payload.get("content") or payload.get("title") or ""
        triples = self.extract(text)
        payload["extracted_entities"] = [t.to_dict() for t in triples]
        rejected = sum(self.rejection_reasons.values())
        logger.info(
            "Extrator produziu %d tripletas (%d predicados rejeitados pelo guard: %s).",
            len(triples),
            rejected,
            dict(self.rejection_reasons),
        )
        return payload


if __name__ == "__main__":
    sample = (
        "Inteligência Artificial utiliza Redes Neurais. "
        "Redes Neurais processam grandes volumes de dados. "
        "O aprendizado profundo revolucionou a visão computacional."
    )
    extractor = EntityExtractor()
    for t in extractor.extract(sample):
        print(t.to_dict())