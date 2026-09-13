"""
Nexus-Alpha - Protocolo de Segurança e Filtro Anti-Desinformação
Implementa Domain Score, NLP de sensacionalismo e Triangulação obrigatória.
"""
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


HIGH_TRUST_TLDS = (".edu", ".gov", ".ac.", ".org")
TRUSTED_TECH_DOMAINS = (
    "huggingface.co", "openai.com", "research.google", "ai.google", "deepmind.google",
    "engineering.fb.com", "github.com", "ibm.com", "paperswithcode.com", "ollama.com",
    "pytorch.org", "tensorflow.org", "scikit-learn.org", "arxiv.org", "mozilla.org",
    "w3.org", "keras.io",
)
LOW_TRUST_PATTERNS = (
    "reddit.com", "medium.com", "wordpress.com",
    "blogspot.com", "tumblr.com", "substack.com",
)

SENSATIONAL_KEYWORDS = {
    "inacreditável", "urgente", "escândalo", "misterioso", "chocante",
    "imperdível", "surpreendente", "absurdo", "revelado", "exclusivo",
    "breaking", "shocking", "unbelievable", "scandal", "outrageous",
}


@dataclass
class VerificationResult:
    fact: str
    status: str
    confidence: float
    sources: list[dict]


class SecurityProtocol:
    def __init__(self, quorum: int = 3, min_domain_score: float = 0.7) -> None:
        self.quorum = quorum
        self.min_domain_score = min_domain_score

    def domain_score(self, url: str) -> float:
        host = urlparse(url).netloc.lower()
        if any(tld in host for tld in HIGH_TRUST_TLDS):
            return 0.9
        if any(domain in host for domain in TRUSTED_TECH_DOMAINS):
            return 0.8
        if any(pat in host for pat in LOW_TRUST_PATTERNS):
            return 0.4
        return 0.6

    def sensationalism_score(self, text: str) -> float:
        words = re.findall(r"\w+", text.lower())
        if not words:
            return 0.0
        hits = sum(1 for w in words if w in SENSATIONAL_KEYWORDS)
        density = hits / len(words)
        return min(1.0, density * 50)

    def confidence(self, url: str, text: str) -> float:
        base = self.domain_score(url)
        sens = self.sensationalism_score(text)
        penalty = 0.5 if sens > 0.15 else 0.0
        return round(max(0.0, base - penalty), 3)

    def triangulate(self, fact: str, sources: Iterable[dict]) -> VerificationResult:
        """
        sources: lista de {url, text}
        Só aprova um fato quando N domínios independentes com score >= min_domain_score o confirmam.
        """
        verified_domains: set[str] = set()
        audited_sources: list[dict] = []

        for src in sources:
            score = self.confidence(src["url"], src.get("text", ""))
            domain = urlparse(src["url"]).netloc
            audited_sources.append({"url": src["url"], "domain": domain, "score": score})

            if score >= self.min_domain_score and self._contains_fact(src.get("text", ""), fact):
                verified_domains.add(domain)

        is_verified = len(verified_domains) >= self.quorum
        final_conf = (
            sum(s["score"] for s in audited_sources if s["domain"] in verified_domains)
            / max(1, len(verified_domains))
            if is_verified else 0.0
        )

        return VerificationResult(
            fact=fact,
            status="Fato Verificado" if is_verified else "Hipótese Isolada (quarentena)",
            confidence=round(final_conf, 3),
            sources=audited_sources,
        )

    @staticmethod
    def _contains_fact(text: str, fact: str) -> bool:
        fact_tokens = [t for t in re.findall(r"\w{4,}", fact.lower())]
        if not fact_tokens:
            return False
        lower = text.lower()
        return sum(1 for t in fact_tokens if t in lower) >= max(1, len(fact_tokens) // 2)


if __name__ == "__main__":
    proto = SecurityProtocol()
    sample = [
        {"url": "https://www.gov.br/pesquisa.txt", "text": "Estudo confirma dado X."},
        {"url": "https://www.universidade.edu/artigo", "text": "Paper confirma dado X."},
        {"url": "https://blogspam.wordpress.com/post", "text": "URGENTE! Dado X inacreditável!!!"},
    ]
    result = proto.triangulate("dado X confirmado", sample)
    print(result)