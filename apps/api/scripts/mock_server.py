import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import random

HOST = "127.0.0.1"
PORT = 8000

class NexusMockServer(BaseHTTPRequestHandler):
    """
    Simula uma API REST para fornecer dados flutuantes e dinâmicos ao Frontend,
    permitindo auditar o comportamento da UI sob estresse ou latência.
    """
    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        # Habilita o CORS para que seu app Next.js consiga consumir localmente sem bloqueios
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-Nexus-Token, Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        """Trata requisições de preflight do navegador."""
        self._set_headers(200)

    def do_GET(self):
        if self.path == "/api/metrics":
            # Introduz um atraso artificial aleatório para testar se os Skeletons da interface funcionam
            time.sleep(random.uniform(0.8, 1.8))
            
            # Gera dados simulados flutuantes e dinâmicos
            mock_data = {
                "status": "online",
                "timestamp": int(time.time()),
                "facts": random.randint(1400, 1450),
                "vectors": random.randint(8900, 9000),
                "quarantine": random.randint(5, 15)
            }
            
            self._set_headers(200)
            self.wfile.write(json.dumps(mock_data).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Rota não encontrada no mock."}).encode("utf-8"))

def run_mock_server():
    server = HTTPServer((HOST, PORT), NexusMockServer)
    print(f"📡 Servidor de simulação visual rodando em http://{HOST}:{PORT}")
    print("Acesse http://127.0.0.1:8000/api/metrics para ver os dados flutuantes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor de simulação encerrado de forma limpa.")
        server.server_close()

if __name__ == "__main__":
    run_mock_server()
