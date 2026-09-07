[CONTEXTO DO PROJETO]
Você está assumindo o projeto "Nexus-Alpha", um ecossistema autônomo de IA focado em web scraping semântico, inteligência baseada em grafos e auto-evolução livre de ruídos. A arquitetura do repositório já está definida com módulos separados para Miner, Cognition e Database.

[DIRETRIZES DE CONTINUIDADE]
1. Respeite os Contratos de Dados: Toda comunicação entre módulos utiliza o NexusPayload JSON-LD (source_url, timestamp, domain_score, extracted_entities[]).
2. Infraestrutura Existente: O ambiente roda via Docker Compose (nexus-core + neo4j-db na porta 7687).
3. Stack Tecnológica: Python assíncrono (httpx, asyncio). Não introduza bibliotecas síncronas de bloqueio.
4. Regra de Ouro de Segurança: Qualquer ingestão precisa passar por SecurityProtocol (domain_score + triangulação) antes de tocar o Neo4j.

[SUA PRIMEIRA TAREFA]
Implemente o módulo `src/database/graph_connector.py` — já existente — ou estenda-o. Ele recebe um NexusPayload e executa Cypher via `AsyncGraphDatabase`.