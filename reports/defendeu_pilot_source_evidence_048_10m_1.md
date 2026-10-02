# DEFENDEU pilot source evidence — #048.10M.1

**Data:** 2026-10-01 · **Modo:** read-only · **Orçamento de probes:** 25/45 requests
(pt 8 + en 8 + rsssfbrasil 8 + 1 descoberta rsssfbrasil)

## Política de fontes
- **Permitidas:** pt.wikipedia.org, en.wikipedia.org, rsssf.org, rsssfbrasil.com
  (source policy do atlas: `allowed` para todos os candidatos).
- **Proibidas:** Transfermarkt, Soccerway, worldfootball, fbref, Almanaque sem
  licença, redes sociais, fóruns, agregadores SEO, sites de aposta — nenhuma
  consulta foi feita a domínios proibidos.

## Independência editorial
- Wikimedia PT/EN: contam como **domínios distintos** para quórum, mas são a
  **mesma publisher family** (Wikimedia).
- RSSSF/RSSSF Brasil: contam como domínios distintos, mas **não** como duas
  famílias editoriais independentes (warning D8).
- Todo candidato requer ao menos 1 domínio não-Wikimedia (`rsssf.org` no
  `required_domains` do atlas).

## Limitação honesta do probe RSSSF
Os paths `rsssfbrasil.com/clubs/<clube>.htm` retornaram 404 (8/8) e a raiz do
site não expõe índice de clubes parseável (descoberta: 130 hrefs, nenhum padrão
de clube). **Nenhum candidato teve RSSSF confirmado por probe** — para todos, o
3º domínio permanece **plausível pela política do atlas** (LOCAL_EXISTING_
EVIDENCE), não confirmado por página real. O worker futuro precisa corroborar
RSSSF de fato antes do quórum; probes RSSSF adicionais são dívida registrada.

## Candidatos selecionados (7)

| candidate | subject | object | domains (required) | probe confirmado | evidence_strength | risk |
|---|---|---|---|---|---|---|
| defendeu_manuelfranciscodossantos_001 | MANUEL FRANCISCO DOS SANTOS (Garrincha) | BOTAFOGO DE FUTEBOL E REGATAS | pt/en wiki + rsssf | pt+en (2/3) | LOCAL_EXISTING_EVIDENCE | low |
| defendeu_jairzinho_002 | JAIRZINHO | BOTAFOGO DE FUTEBOL E REGATAS | pt/en wiki + rsssf | pt+en (2/3) | LOCAL_EXISTING_EVIDENCE | low |
| defendeu_zito_003 | ZITO | SANTOS FUTEBOL CLUBE | pt/en wiki + rsssf | pt (1/3) | LOCAL_EXISTING_EVIDENCE | low |
| defendeu_socratesbrasileirosampai_005 | SÓCRATES BRASILEIRO SAMPAIO DE SOUZA VIEIRA DE OLIVEIRA | SPORT CLUB CORINTHIANS PAULISTA | pt/en wiki + rsssf | pt+en (2/3) | LOCAL_EXISTING_EVIDENCE | low |
| defendeu_romariodesouzafaria_006 | ROMÁRIO DE SOUZA FARIA | CLUBE DE REGATAS VASCO DA GAMA | pt/en wiki + rsssf | pt+en (2/3) | LOCAL_EXISTING_EVIDENCE | low |
| defendeu_carlosalbertotorres_007 | CARLOS ALBERTO TORRES | SANTOS FUTEBOL CLUBE | pt/en wiki + rsssf | pt+en (2/3) | LOCAL_EXISTING_EVIDENCE | low |
| defendeu_rogerioceni_012 | ROGÉRIO CENI | SÃO PAULO FUTEBOL CLUBE | pt/en wiki + rsssf | pt+en (2/3) | LOCAL_EXISTING_EVIDENCE | medium |

Evidência local que sustenta LOCAL_EXISTING_EVIDENCE: atlas read-only
(`expansion_defendeu_atlas_048_10m.json` — 3 domínios plausíveis por candidato),
fatos DEFENDEU unverified já no grafo (_001/_002/_003) e fixtures de extração
DEFENDEU commitadas (test_player_club_defendeu_extraction.py).

## Excluídos (5) com causa

| candidate | motivo |
|---|---|
| defendeu_arthurantunescoimbra_004 (Rivelino→Flamengo) | **Cenário E:** probe 0/2 nas páginas canônicas (200 OK sem menção ao objeto) — fato não corroborável; possível erro fático no atlas. Excluído; atlas não corrigido neste task |
| defendeu_niltonreisdossantos_008 | D1: homonímia jogador×estádio não resolvida por alias |
| defendeu_ronaldoluisnazariodelima_009 | D1 (nome comum) + D3 + múltiplos clubes na carreira |
| defendeu_denilsondeoliveiraaraujo_010 | D1 + D3 + múltiplos clubes na carreira |
| defendeu_gustavonery_011 | D2: nome comum sem alias forte |

## Bloqueios
Nenhum bloqueio para o dry-run. Dívidas registradas (não misturadas neste task):
probes RSSSF alternativos (futuro #048.10M.0_2 read-only), #054.2 (boot probe),
#054.3 (worker retry 429), #054.4 (ruff gate no CI).
