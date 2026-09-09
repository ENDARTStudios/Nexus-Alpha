import logging
import re

class SafeLogFormatter(logging.Formatter):
    """
    Formatter customizado do módulo logging que intercepta e mascara tokens,
    chaves de API e strings de conexões com senhas sensíveis de forma atômica.
    """
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        
        # Padrões Regex comuns de segredos sensíveis
        self.patterns = {
            "NEO4J_PASSWORD": re.compile(r"(bolt://neo4j:)[^@]+(@)"),
            "API_TOKENS": re.compile(r"(X-Nexus-Token['\"]?\s*:\s*['\"]?)[a-zA-Z0-9_\-]+(['\"]?)"),
            "GENERIC_KEYS": re.compile(r"(api_key=['\"]?|token=['\"]?)[a-zA-Z0-9_\-]{8,}")
        }

    def sanitize(self, message: str) -> str:
        if not isinstance(message, str):
            return message
            
        # Substitui credenciais em URLs do Neo4j (Ex: bolt://neo4j:SenhaSecreta@host -> bolt://neo4j:[MASKED]@host)
        message = self.patterns["NEO4J_PASSWORD"].sub(r"\1[MASKED]\2", message)
        
        # Substitui tokens passados em dicionários ou cabeçalhos de requisição
        message = self.patterns["API_TOKENS"].sub(r"\1[MASKED]\2", message)
        
        # Mascara argumentos de chaves genéricas de API
        message = self.patterns["GENERIC_KEYS"].sub(r"\1[MASKED]", message)
        
        return message

    def format(self, record):
        # Formata o log normalmente usando o comportamento nativo do Python
        original_output = super().format(record)
        # Sanitiza a string final antes de exibi-la no terminal público
        return self.sanitize(original_output)

def setup_secure_logging():
    """Configura o logger padrão da aplicação para usar o formatador blindado."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Cria o manipulador de saída para o console
    handler = logging.StreamHandler()
    formatter = SafeLogFormatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    
    # Remove handlers antigos para evitar duplicação de logs ruidosos
    if logger.handlers:
        logger.handlers.clear()
        
    logger.addHandler(handler)
    logging.info("Sistema de logs seguro ativado. Blindagem anti-vazamento operacional.")

# Teste Rápido Local
if __name__ == "__main__":
    setup_secure_logging()
    
    # Teste de simulação de erro contendo dados perigosos (senha virtual, não produtiva)
    logging.warning("Falha ao conectar na URL: bolt://neo4j:S3nh4Fake@neo4j-db:7687")
    logging.error("Requisição rejeitada com o cabeçalho: {'X-Nexus-Token': 'ChaveSecretaPadraoParaDesenvolvimento'}")
