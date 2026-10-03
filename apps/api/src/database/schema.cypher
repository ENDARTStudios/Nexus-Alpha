"""
Nexus-Alpha - Graph Knowledge Schema (Neo4j / Cypher)
Define nós, relacionamentos e queries de ingestão, contradição e evolução.
"""

GRAPH_SCHEMA = """
// === CONSTRAINTS DE UNICIDADE ===
CREATE CONSTRAINT conceito_nome IF NOT EXISTS FOR (c:Conceito) REQUIRE c.nome IS UNIQUE;
CREATE CONSTRAINT fonte_url IF NOT EXISTS FOR (f:FonteWeb) REQUIRE f.url IS UNIQUE;
CREATE CONSTRAINT autor_id IF NOT EXISTS FOR (a:Autor) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT fato_id IF NOT EXISTS FOR (fa:Fato) REQUIRE fa.id IS UNIQUE;

// === ÍNDICES DE BUSCA ===
CREATE INDEX conceito_busca IF NOT EXISTS FOR (c:Conceito) ON (c.nome);
CREATE INDEX fonte_dominio IF NOT EXISTS FOR (f:FonteWeb) ON (f.dominio);
"""

INGEST_QUERY = """
MERGE (c1:Conceito {nome: $conceito_origem})
  ON CREATE SET c1.criado_em = timestamp()
MERGE (c2:Conceito {nome: $conceito_destino})
  ON CREATE SET c2.criado_em = timestamp()
MERGE (f:FonteWeb {url: $fonte_url})
  ON CREATE SET f.dominio = $dominio, f.criado_em = timestamp()
  SET f.ultima_verificacao = timestamp(),
      f.confiabilidade = coalesce($confiabilidade, f.confiabilidade, 0.5)
MERGE (a:Autor {id: $autor_id})
  ON CREATE SET a.nome = $autor_nome, a.criado_em = timestamp()
MERGE (c1)-[r:CONECTA_A {tipo: $relacao}]->(c2)
  SET r.peso = $peso, r.timestamp = timestamp(), r.contexto = $contexto
MERGE (c1)-[:MINERADO_DE]->(f)
MERGE (c2)-[:MINERADO_DE]->(f)
MERGE (a)-[:PUBLICOU]->(f)
RETURN c1.nome AS origem, type(r) AS relacao, c2.nome AS destino, f.confiabilidade AS conf
"""

CONTRADICTION_QUERY = """
MATCH (c1:Conceito)-[r1]->(c2:Conceito)
WHERE type(r1) IN ['AFIRMA', 'CONECTA_A']
WITH c1, c2, collect({tipo: type(r1), peso: r1.peso}) AS relacoes
WHERE size(relacoes) > 1 AND any(r IN relacoes WHERE r.tipo = 'NEGA')
RETURN c1.nome AS conceito_origem,
       c2.nome AS conceito_destino,
       relacoes,
       'Alerta: contradição detectada — ativar modo de desempate web' AS status
"""

DECAY_QUERY = """
MATCH (f:FonteWeb)
WHERE f.confiabilidade < 0.3
SET f.em_quarentena = true
RETURN f.url AS url, f.confiabilidade AS score, 'Fonte em quarentena' AS status
"""

EVOLUTION_REPORT = """
MATCH (c:Conceito)
OPTIONAL MATCH (c)-[r]->()
WITH c, count(r) AS grau
RETURN c.nome AS conceito,
       grau AS conexoes,
       c.ultima_atualizacao AS atualizado_em
ORDER BY grau DESC
LIMIT 25
"""