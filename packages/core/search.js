// ============================================================
// Copilot Runtime — Versao de linha de comando
//
// Wrapper fino sobre packages/core/rag.js, util para testar
// o RAG rapidamente sem precisar subir a API.
//
// Como rodar:
//   node search.js <slug-do-projeto> "<pergunta>"
//
// Exemplo:
//   node search.js erp-hospitalar "como tratar uma glosa administrativa?"
// ============================================================

import "dotenv/config";
import pg from "pg";
import { responderPergunta } from "./rag.js";

const [, , projetoSlug, pergunta] = process.argv;

if (!projetoSlug || !pergunta) {
  console.error('Uso: node search.js <slug-do-projeto> "<pergunta>"');
  console.error('Exemplo: node search.js erp-hospitalar "como tratar uma glosa administrativa?"');
  process.exit(1);
}

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });

async function main() {
  const aiProvider = process.env.AI_PROVIDER || "openai";

  if (aiProvider === "mock") {
    console.log("AI_PROVIDER=mock — busca sem chamadas externas (resposta simulada).\n");
  } else if (aiProvider === "groq" || aiProvider === "ollama") {
    const ollamaUrl = process.env.OLLAMA_URL || "http://localhost:11434";
    console.log(`AI_PROVIDER=${aiProvider} — embeddings via Ollama (${ollamaUrl}).\n`);
  } else if (aiProvider === "openai") {
    if (!process.env.OPENAI_API_KEY || process.env.OPENAI_API_KEY.startsWith("sk-coloque")) {
      console.error("ERRO: defina OPENAI_API_KEY no .env para usar AI_PROVIDER=openai.");
      console.error("Alternativa gratuita: AI_PROVIDER=groq (console.groq.com) ou AI_PROVIDER=ollama.");
      process.exit(1);
    }
  }

  const client = await pool.connect();

  try {
    const projetoResult = await client.query(
      `SELECT id, nome, persona_tom FROM projetos WHERE slug = $1`,
      [projetoSlug]
    );

    if (projetoResult.rows.length === 0) {
      console.error(`Projeto com slug "${projetoSlug}" nao encontrado. Rode o ingest.js primeiro.`);
      process.exit(1);
    }

    const projeto = projetoResult.rows[0];

    console.log(`\nProjeto: ${projeto.nome}`);
    console.log(`Pergunta: ${pergunta}\n`);

    const { resposta, fontes, tokens_usados } = await responderPergunta(client, projeto, pergunta);

    console.log("--- Fontes utilizadas ---");
    fontes.forEach((f, i) => {
      console.log(`[${i + 1}] ${f.documento_nome}${f.secao ? ` > ${f.secao}` : ""} (distancia: ${f.distancia})`);
    });
    console.log("-------------------------\n");

    console.log("--- Resposta do especialista ---");
    console.log(resposta);
    console.log("---------------------------------");

    console.log(`\n(tokens usados: ${tokens_usados})`);
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((err) => {
  console.error("\n❌ Erro:", err.message);
  process.exit(1);
});
