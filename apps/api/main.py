# ============================================================
# Copilot Runtime — App FastAPI
#
# Equivalente a:
#   - next.config.js (CORS)
#   - pages/index.js (rota raiz com info da API)
#   - pages/api/*.js (registrados aqui como routers)
#
# Como rodar:
#   uvicorn main:app --reload --port 3001
# ============================================================

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from routers import chat, feedback, health, metrics

app = FastAPI(title="SupportAI — Copilot Runtime")

# A API sera chamada por widgets embedados em outros dominios
# (sites dos ISVs). CORS liberado de forma ampla na Fase 1;
# restringir por dominio do projeto e' tarefa da Fase 2/3
# (campo "projetos.dominio" ja existe no schema para isso).
#
# Equivalente ao async headers() de next.config.js.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Cada router abaixo equivale a um arquivo dentro de pages/api/.
# Mantemos o prefixo "/api" pra preservar as mesmas URLs do Next.js
# (GET /api/health, POST /api/chat, etc.), facilitando a migracao
# do widget sem precisar mudar nada nele.
app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
def home():
    """Equivalente a pages/index.js — pagina simples com info da API."""
    return """
    <main style="font-family: monospace; padding: 2rem;">
      <h1>SupportAI — Copilot Runtime</h1>
      <p>Esta e a API do SupportAI. Endpoints disponiveis:</p>
      <ul>
        <li><code>GET /api/health</code> — verificacao de status</li>
        <li><code>POST /api/chat</code> — conversa com o especialista virtual</li>
        <li><code>POST /api/feedback</code> — avaliar uma resposta</li>
        <li><code>GET /api/metrics/{slug}</code> — metricas de um projeto</li>
      </ul>
      <p>Exemplo de uso do <code>/api/chat</code>:</p>
      <pre>curl -X POST http://localhost:3001/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{"project_slug": "erp-hospitalar", "message": "como tratar uma glosa administrativa?"}'</pre>
      <p>Documentacao interativa automatica: <a href="/docs">/docs</a></p>
    </main>
    """
