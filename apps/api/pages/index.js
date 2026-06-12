export default function Home() {
  return (
    <main style={{ fontFamily: "monospace", padding: "2rem" }}>
      <h1>SupportAI — Copilot Runtime</h1>
      <p>Esta e a API do SupportAI. Endpoints disponiveis:</p>
      <ul>
        <li><code>GET /api/health</code> — verificacao de status</li>
        <li><code>POST /api/chat</code> — conversa com o especialista virtual</li>
      </ul>
      <p>
        Exemplo de uso do <code>/api/chat</code>:
      </p>
      <pre>
{`curl -X POST http://localhost:3001/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{"project_slug": "erp-hospitalar", "message": "como tratar uma glosa administrativa?"}'`}
      </pre>
    </main>
  );
}
