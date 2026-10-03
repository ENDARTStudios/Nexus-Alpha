# #048.10M — Política de fontes para expansão não-VENCEU

Conservadora e explícita. Implementada em `scripts/audit_expansion_source_policy_048_10m.py`.

## 6.1 Permitidas por padrão
```text
pt.wikipedia.org, en.wikipedia.org           (família Wikimedia)
rsssf.org, www.rsssf.org, rsssfbrasil.com, www.rsssfbrasil.com   (família RSSSF)
nominatim.openstreetmap.org                  (apenas LOCALIZADO_EM / geografia; ODbL)
```
Regras:
- Wikipedia PT/EN contam como **domínios** distintos, mas **não** como independência editorial (mesma família Wikimedia).
- RSSSF / RSSSF Brasil contam como domínios distintos, mas geram **warning** de mesma família editorial.
- OpenStreetMap é família independente geográfica/open data; exige attribution/ODbL.

## 6.2 Advertidas
```text
commons.wikimedia.org, wikidata.org, news.wikimedia.org
sites oficiais de clubes/confederações (somente se já em allowlist; senão exigir issue de política)
```
Não promovem independência editorial automaticamente.

## 6.3 Proibidas
```text
Transfermarkt, Soccerway, worldfootball.net, fbref.com
Almanaque dos Clubes sem licença Elite
redes sociais, fóruns, agregadores SEO, sites de aposta, wikis não oficiais
PDFs não governados, snapshots não verificáveis, endpoints não HTTPS
qualquer fonte que exija bypass de bot protection
```

## 6.4 Regra de independência
Um candidato só é elegível futuramente se: (1) ≥3 domínios distintos; (2) não depender só de
múltiplos idiomas da Wikipedia; (3) incluir ao menos 1 fonte não-Wikimedia; (4) não usar fonte
proibida; (5) evidência vir da página/endpoint (não de menção textual); (6) RSSSF/RSSSF Brasil não
contam como duas independências; (7) sem embedding/LLM como validador; (8) sem promover fato com 1–2 domínios.
