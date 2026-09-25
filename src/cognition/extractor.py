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

from .predicate_mapper import INVALID_PREDICATE_REASONS, validate_predicate

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

    def __init__(self, model: str = "pt_core_news_sm", enable_fallback: bool = True) -> None:
        self.model_name = model
        self.enable_fallback = enable_fallback
        self._nlp = None
        self.rejection_reasons: collections.Counter = collections.Counter()
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
            root = next((t for t in sent if t.dep_ == "ROOT"), None)
            if root is None or root.pos_ not in ("VERB", "AUX"):
                continue
            predicate, predicate_reason = validate_predicate(root.lemma_)
            if predicate_reason in INVALID_PREDICATE_REASONS:
                self.rejection_reasons[predicate_reason] += 1
                continue
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
                continue
            subject = self._normalize_term(strip_boundary_noise(self._phrase_text(subj_tok)))
            obj = self._normalize_term(strip_boundary_noise(self._phrase_text(obj_tok)))
            subject = rescue_truncated_toponym(subject, text)
            obj = rescue_truncated_toponym(obj, text)
            if is_function_word_span(subject) or is_function_word_span(obj):
                continue
            if not self._valid_term(subject) or not self._valid_term(obj):
                continue
            triples.append(Triple(
                subject=subject,
                predicate=predicate,
                object=obj,
                confidence=self._confidence_for(subject, obj, predicate),
            ))
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