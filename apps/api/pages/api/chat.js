// ============================================================
// POST /api/chat — Copilot Runtime (Fase 1)
//
// Recebe: { project_slug, message, session_id? }
// Retorna: { resposta, fontes, tokens_usados, conversa_id }
//
// PROVEDOR DE IA (AI_PROVIDER no .env.local):
//   "openai"  — OpenAI API. Requer OPENAI_API_KEY com billing.
//   "groq"    — Groq (chat gratuito) + Ollama (embeddings locais).
//               Requer GROQ_API_KEY e Ollama rodando localmente.
//   "ollama"  — Tudo local. Zero custo. Requer Ollama instalado.
//   "mock"    — Sem chamadas externas. Util para CI/onboarding.
//
// NOTA DE ARQUITETURA (debito tecnico documentado):
// A logica de RAG esta duplicada aqui em vez de importada de
// packages/core/rag.js porque aquele pacote e ESM puro e o
// Next.js Pages Router usa CommonJS. Unificar exigiria configurar
// workspaces/transpilePackages — complexidade adiada para quando
// o monorepo for formalizado.
// ============================================================

import { Pool } from "pg";
import OpenAI from "openai";
import https from "node:https";
import http from "node:http";

// Requisicao HTTP/HTTPS simples sem depender do fetch global
function httpPost(url, body) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const driver = parsed.protocol === "https:" ? https : http;
    const data = JSON.stringify(body);
    const req = driver.request(
      {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
        path: parsed.pathname,
        method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
      },
      (res) => {
        let raw = "";
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            try { resolve(JSON.parse(raw)); } catch (e) { reject(new Error(`JSON invalido: ${raw}`)); }
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${raw}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

const TOP_K = 4;
const EMBEDDING_DIMENSIONS = 1536;
const AI_PROVIDER = process.env.AI_PROVIDER || "openai";

const CHAT_MODELS = {
  openai: "gpt-4o-mini",
  groq: "llama-3.1-8b-instant",
  ollama: "llama3.2",
};

const EMBED_MODELS = {
  openai: "text-embedding-3-small",
  ollama: "nomic-embed-text",
};

// -- Clientes lazy --
let pool, openaiClient, groqClient;

function getPool() {
  if (!pool) pool = new Pool({ connectionString: process.env.DATABASE_URL });
  return pool;
}

function getOpenAIClient() {
  if (!openaiClient) openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  return openaiClient;
}

function getGroqClient() {
  if (!groqClient) {
    groqClient = new OpenAI({
      apiKey: process.env.GROQ_API_KEY,
      baseURL: "https://api.groq.com/openai/v1",
    });
  }
  return groqClient;
}

function getOllamaUrl() {
  return (process.env.OLLAMA_URL || "http://localhost:11434").replace(/\/$/, "");
}

// ============================================================
// EMBEDDINGS
// ============================================================

function hashString(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) hash = (hash * 33) ^ str.charCodeAt(i);
  return hash >>> 0;
}

function gerarEmbeddingMock(texto) {
  const vetor = new Array(EMBEDDING_DIMENSIONS).fill(0);
  const palavras = texto.toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").match(/[a-z0-9]+/g) || [];
  for (const palavra of palavras) {
    const h = hashString(palavra);
    vetor[h % EMBEDDING_DIMENSIONS] += h & 0x10000 ? 1 : -1;
  }
  const norma = Math.sqrt(vetor.reduce((s, v) => s + v * v, 0)) || 1;
  return vetor.map((v) => v / norma);
}

async function gerarEmbeddingOllama(texto) {
  const dados = await httpPost(`${getOllamaUrl()}/api/embeddings`, {
    model: EMBED_MODELS.ollama,
    prompt: texto,
  });
  if (!dados.embedding || !Array.isArray(dados.embedding))
    throw new Error(`Ollama nao retornou embedding. Resposta: ${JSON.stringify(dados)}`);
  const vetor = dados.embedding;
  while (vetor.length < EMBEDDING_DIMENSIONS) vetor.push(0);
  return vetor;
}

async function gerarEmbedding(texto) {
  switch (AI_PROVIDER) {
    case "mock":   return gerarEmbeddingMock(texto);
    case "ollama":
    case "groq":   return gerarEmbeddingOllama(texto);
    default: {
      const openai = getOpenAIClient();
      const resp = await openai.embeddings.create({ model: EMBED_MODELS.openai, input: texto });
      return resp.data[0].embedding;
    }
  }
}

// ============================================================
// CHAT
// ============================================================

function montarSystemPrompt({ nomeProjeto, personaTom, contexto }) {
  const tom = { tecnico_e_direto: "tecnico, direto e objetivo, sem rodeios",
                amigavel_e_didatico: "amigavel, didatico, explicando com calma" }[personaTom]
             ?? "profissional e prestativo";

  return `Voce e o especialista virtual do sistema "${nomeProjeto}".
Seu tom de comunicacao deve ser ${tom}.
Responda SOMENTE com base no CONTEXTO abaixo. Se a resposta nao estiver
no contexto, diga que nao encontrou a informacao — NAO invente.
Sempre cite o documento e a secao de origem.

CONTEXTO:
${contexto}`;
}

async function chamarLLM(systemPrompt, pergunta) {
  switch (AI_PROVIDER) {
    case "groq": {
      const resp = await getGroqClient().chat.completions.create({
        model: CHAT_MODELS.groq,
        messages: [{ role: "system", content: systemPrompt }, { role: "user", content: pergunta }],
        temperature: 0.2,
      });
      return { texto: resp.choices[0].message.content, tokens: resp.usage?.total_tokens ?? 0 };
    }
    case "ollama": {
      const ollamaClient = new OpenAI({ apiKey: "ollama", baseURL: `${getOllamaUrl()}/v1` });
      const resp = await ollamaClient.chat.completions.create({
        model: CHAT_MODELS.ollama,
        messages: [{ role: "system", content: systemPrompt }, { role: "user", content: pergunta }],
        temperature: 0.2,
      });
      return { texto: resp.choices[0].message.content, tokens: resp.usage?.total_tokens ?? 0 };
    }
    default: {
      const resp = await getOpenAIClient().chat.completions.create({
        model: CHAT_MODELS.openai,
        messages: [{ role: "system", content: systemPrompt }, { role: "user", content: pergunta }],
        temperature: 0.2,
      });
      return { texto: resp.choices[0].message.content, tokens: resp.usage?.total_tokens ?? 0 };
    }
  }
}

function montarRespostaMock(pergunta, chunks) {
  const trechos = chunks.map((row, i) => {
    const meta = row.metadados;
    const resumo = row.conteudo.slice(0, 220).replace(/\s+/g, " ").trim();
    const origem = meta.secao ? `${meta.documento_nome} > ${meta.secao}` : meta.documento_nome;
    return `[Trecho ${i + 1} - ${origem}]\n${resumo}...`;
  }).join("\n\n");

  return `[MODO MOCK - nenhuma chamada externa foi feita]\n\nPergunta: "${pergunta}"\n\n${trechos}\n\n---\nPara respostas reais: defina AI_PROVIDER=groq, ollama ou openai no .env.local.`;
}

// ============================================================
// HANDLER PRINCIPAL
// ============================================================

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ erro: "Use POST." });

  const { project_slug, message, session_id } = req.body ?? {};
  if (!project_slug || !message)
    return res.status(400).json({ erro: "Campos obrigatorios: project_slug, message" });

  if (!process.env.DATABASE_URL)
    return res.status(500).json({ erro: "DATABASE_URL nao configurado." });

  const client = await getPool().connect();

  try {
    // 1. Busca o projeto
    const projetoResult = await client.query(
      `SELECT id, nome, persona_tom, status FROM projetos WHERE slug = $1`,
      [project_slug]
    );
    if (projetoResult.rows.length === 0)
      return res.status(404).json({ erro: `Projeto "${project_slug}" nao encontrado.` });

    const projeto = projetoResult.rows[0];
    if (projeto.status !== "ativo")
      return res.status(409).json({ erro: `Projeto nao esta ativo (status: ${projeto.status}).` });

    // 2. Conversa (cria ou reaproveita pela sessao)
    let conversaId;
    if (session_id) {
      const ex = await client.query(
        `SELECT id FROM conversas WHERE projeto_id = $1 AND sessao_externa_id = $2`,
        [projeto.id, session_id]
      );
      if (ex.rows.length > 0) conversaId = ex.rows[0].id;
    }
    if (!conversaId) {
      const nova = await client.query(
        `INSERT INTO conversas (projeto_id, sessao_externa_id, canal) VALUES ($1, $2, 'widget') RETURNING id`,
        [projeto.id, session_id ?? null]
      );
      conversaId = nova.rows[0].id;
    }

    // 3. Salva mensagem do usuario
    await client.query(
      `INSERT INTO mensagens (conversa_id, papel, conteudo) VALUES ($1, 'usuario', $2)`,
      [conversaId, message]
    );

    // 4. Embedding + busca vetorial (RAG)
    const embeddingPergunta = await gerarEmbedding(message);
    const buscaResult = await client.query(
      `SELECT c.conteudo, c.metadados, (c.embedding <=> $1) AS distancia
       FROM chunks c WHERE c.projeto_id = $2 ORDER BY c.embedding <=> $1 LIMIT $3`,
      [`[${embeddingPergunta.join(",")}]`, projeto.id, TOP_K]
    );

    let respostaTexto, fontes = [], tokensUsados = 0;

    if (buscaResult.rows.length === 0) {
      respostaTexto = "Nenhum documento processado para este projeto.";
    } else if (AI_PROVIDER === "mock") {
      respostaTexto = montarRespostaMock(message, buscaResult.rows);
      fontes = buscaResult.rows.map((r) => ({ documento_nome: r.metadados.documento_nome, secao: r.metadados.secao }));
    } else {
      const contexto = buscaResult.rows
        .map((r, i) => `[Trecho ${i + 1} - ${r.metadados.documento_nome}]\n${r.conteudo}`)
        .join("\n\n---\n\n");
      const systemPrompt = montarSystemPrompt({ nomeProjeto: projeto.nome, personaTom: projeto.persona_tom, contexto });
      const { texto, tokens } = await chamarLLM(systemPrompt, message);
      respostaTexto = texto;
      tokensUsados = tokens;
      fontes = buscaResult.rows.map((r) => ({ documento_nome: r.metadados.documento_nome, secao: r.metadados.secao }));
    }

    // 5. Salva resposta do assistente
    await client.query(
      `INSERT INTO mensagens (conversa_id, papel, conteudo, fontes_utilizadas, tokens_usados)
       VALUES ($1, 'assistente', $2, $3, $4)`,
      [conversaId, respostaTexto, JSON.stringify(fontes), tokensUsados]
    );

    res.status(200).json({ resposta: respostaTexto, fontes, tokens_usados: tokensUsados, conversa_id: conversaId });
  } catch (err) {
    console.error("Erro em /api/chat:", err);
    res.status(500).json({ erro: "Erro interno ao processar a pergunta." });
  } finally {
    client.release();
  }
}
