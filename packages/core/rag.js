// ============================================================
// Copilot Runtime — Logica central do RAG (reutilizavel)
//
// Usado tanto pelo script CLI (search.js) quanto pela API
// (apps/api/pages/api/chat.js).
//
// PROVEDOR DE IA (AI_PROVIDER):
//   "openai"  — OpenAI API (embeddings + chat). Requer billing.
//   "groq"    — Groq API (chat gratuito) + Ollama (embeddings locais).
//               Requer GROQ_API_KEY e Ollama rodando localmente.
//   "ollama"  — Tudo local via Ollama (embeddings + chat). Zero custo,
//               zero dependencia externa. Requer Ollama instalado.
//   "mock"    — Nenhuma chamada externa. Embeddings via feature hashing,
//               resposta simulada. Util para CI e onboarding.
// ============================================================

import OpenAI from "openai";
import https from "node:https";
import http from "node:http";

const TOP_K = 4;
const EMBEDDING_DIMENSIONS = 1536;

const AI_PROVIDER = process.env.AI_PROVIDER || "openai";

// -- Modelos por provedor --
// Chat
const CHAT_MODELS = {
  openai: "gpt-4o-mini",
  groq: "llama-3.1-8b-instant", // rapido e gratuito
  ollama: "llama3.2",           // modelo local leve
};

// Embedding
const EMBED_MODELS = {
  openai: "text-embedding-3-small",  // 1536 dimensoes
  groq: "nomic-embed-text",          // Groq nao suporta embeddings ainda,
                                      // entao groq usa Ollama para embeddings
  ollama: "nomic-embed-text",         // 768 dimensoes
};

// O modelo nomic-embed-text gera vetores de 768 dimensoes,
// nao 1536. O schema usa VECTOR(1536). Para compatibilidade,
// o embedding de 768 e "padded" (completado com zeros) ate 1536.
// Isso funciona porque pgvector compara por distancia de cosseno
// e os zeros extras nao afetam o resultado (contribuicao zero).
const OLLAMA_EMBED_DIMENSIONS = 768;

// -- Clientes lazy (criados so quando necessario) --
let openaiClient = null;
let groqClient = null;

function getOpenAIClient() {
  if (!openaiClient) {
    openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openaiClient;
}

function getGroqClient() {
  if (!groqClient) {
    // O SDK da OpenAI aceita um baseURL diferente — o Groq e compativel
    // com a interface da OpenAI, entao reutilizamos o mesmo SDK.
    // E como trocar a tomada: mesma ficha, outra voltagem.
    groqClient = new OpenAI({
      apiKey: process.env.GROQ_API_KEY,
      baseURL: "https://api.groq.com/openai/v1",
    });
  }
  return groqClient;
}

// URL base do Ollama (padrao: localhost:11434)
function getOllamaUrl() {
  return (process.env.OLLAMA_URL || "http://localhost:11434").replace(/\/$/, "");
}

// ============================================================
// EMBEDDINGS
// ============================================================

// ------------------------------------------------------------
// Requisicao HTTP/HTTPS simples (substitui fetch).
// Usamos os modulos nativos node:http e node:https para evitar
// dependencia do fetch global (disponivel so no Node 18+) e
// problemas de escopo causados por imports incorretos.
// ------------------------------------------------------------
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
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
        },
      },
      (res) => {
        let raw = "";
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            try { resolve(JSON.parse(raw)); }
            catch (e) { reject(new Error(`JSON invalido: ${raw}`)); }
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

// ------------------------------------------------------------
// Embedding via Ollama usando HTTP nativo.
// ------------------------------------------------------------
async function gerarEmbeddingOllama(texto) {
  const url = `${getOllamaUrl()}/api/embeddings`;

  const dados = await httpPost(url, {
    model: EMBED_MODELS.ollama,
    prompt: texto,
  });

  const vetor = dados.embedding;
  if (!vetor || !Array.isArray(vetor)) {
    throw new Error(`Ollama nao retornou embedding. Resposta: ${JSON.stringify(dados)}`);
  }

  // Padding: completa com zeros ate 1536 (nomic-embed-text gera 768)
  while (vetor.length < EMBEDDING_DIMENSIONS) vetor.push(0);
  return vetor;
}

// ------------------------------------------------------------
// Hash simples (djb2) — usado apenas pelo modo mock.
// ------------------------------------------------------------
function hashString(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return hash >>> 0;
}

export function gerarEmbeddingMock(texto) {
  const vetor = new Array(EMBEDDING_DIMENSIONS).fill(0);
  const palavras =
    texto
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .match(/[a-z0-9]+/g) || [];

  for (const palavra of palavras) {
    const h = hashString(palavra);
    const indice = h % EMBEDDING_DIMENSIONS;
    const sinal = h & 0x10000 ? 1 : -1;
    vetor[indice] += sinal;
  }

  const norma = Math.sqrt(vetor.reduce((soma, v) => soma + v * v, 0)) || 1;
  return vetor.map((v) => v / norma);
}

// ------------------------------------------------------------
// gerarEmbedding: roteador central de embeddings.
// Decide qual provedor usar com base em AI_PROVIDER.
// ------------------------------------------------------------
export async function gerarEmbedding(texto) {
  switch (AI_PROVIDER) {
    case "mock":
      return gerarEmbeddingMock(texto);

    case "ollama":
    case "groq": // groq nao suporta embeddings, usa ollama para isso
      return gerarEmbeddingOllama(texto);

    case "openai":
    default: {
      const openai = getOpenAIClient();
      const resposta = await openai.embeddings.create({
        model: EMBED_MODELS.openai,
        input: texto,
      });
      return resposta.data[0].embedding;
    }
  }
}

// ============================================================
// CHAT / GERACAO DE RESPOSTA
// ============================================================

export function montarSystemPrompt({ nomeProjeto, personaTom, contexto }) {
  const tomDescricao = {
    tecnico_e_direto: "tecnico, direto e objetivo, sem rodeios",
    amigavel_e_didatico: "amigavel, didatico, explicando com calma",
  }[personaTom] ?? "profissional e prestativo";

  return `Voce e o especialista virtual do sistema "${nomeProjeto}".

Seu tom de comunicacao deve ser ${tomDescricao}.

Responda SOMENTE com base no CONTEXTO fornecido abaixo, que foi extraido
da documentacao oficial do sistema. Se a resposta nao estiver no contexto,
diga claramente que nao encontrou essa informacao na documentacao
disponivel — NAO invente informacoes.

Sempre que possivel, cite o nome do documento e a secao de onde veio
a informacao usada na resposta.

CONTEXTO:
${contexto}`;
}

// ------------------------------------------------------------
// chamarLLM: abstrai a chamada ao modelo de chat.
//
// OpenAI e Groq usam o mesmo SDK (Groq e compativel com a
// interface da OpenAI). Ollama tem sua propria API REST, mas
// tambem oferece um endpoint compativel com OpenAI em /v1,
// entao reutilizamos o SDK aqui tambem.
// ------------------------------------------------------------
async function chamarLLM(systemPrompt, pergunta) {
  switch (AI_PROVIDER) {
    case "groq": {
      const groq = getGroqClient();
      const resp = await groq.chat.completions.create({
        model: CHAT_MODELS.groq,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: pergunta },
        ],
        temperature: 0.2,
      });
      return {
        texto: resp.choices[0].message.content,
        tokens: resp.usage?.total_tokens ?? 0,
      };
    }

    case "ollama": {
      // Ollama expoe endpoint compativel com OpenAI em /v1.
      // Reutilizamos o SDK da OpenAI apontando para localhost.
      const ollamaClient = new OpenAI({
        apiKey: "ollama",           // valor exigido pelo SDK, ignorado pelo Ollama
        baseURL: `${getOllamaUrl()}/v1`,
      });
      const resp = await ollamaClient.chat.completions.create({
        model: CHAT_MODELS.ollama,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: pergunta },
        ],
        temperature: 0.2,
      });
      return {
        texto: resp.choices[0].message.content,
        tokens: resp.usage?.total_tokens ?? 0,
      };
    }

    case "openai":
    default: {
      const openai = getOpenAIClient();
      const resp = await openai.chat.completions.create({
        model: CHAT_MODELS.openai,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: pergunta },
        ],
        temperature: 0.2,
      });
      return {
        texto: resp.choices[0].message.content,
        tokens: resp.usage?.total_tokens ?? 0,
      };
    }
  }
}

function montarRespostaMock(pergunta, chunks) {
  const trechos = chunks
    .map((row, i) => {
      const meta = row.metadados;
      const resumo = row.conteudo.slice(0, 220).replace(/\s+/g, " ").trim();
      const origem = meta.secao
        ? `${meta.documento_nome} > ${meta.secao}`
        : meta.documento_nome;
      return `[Trecho ${i + 1} - ${origem}]\n${resumo}...`;
    })
    .join("\n\n");

  return `[MODO MOCK - nenhuma chamada externa foi feita]

Pergunta: "${pergunta}"

Trechos recuperados (busca por sobreposicao de palavras):

${trechos}

---
Para respostas reais: defina AI_PROVIDER=groq, ollama ou openai no .env.`;
}

// ============================================================
// PIPELINE COMPLETO
// ============================================================

export async function buscarChunksRelevantes(client, projetoId, pergunta) {
  const embeddingPergunta = await gerarEmbedding(pergunta);

  const resultado = await client.query(
    `SELECT c.conteudo, c.metadados, (c.embedding <=> $1) AS distancia
     FROM chunks c
     WHERE c.projeto_id = $2
     ORDER BY c.embedding <=> $1
     LIMIT $3`,
    [`[${embeddingPergunta.join(",")}]`, projetoId, TOP_K]
  );

  return resultado.rows;
}

export async function responderPergunta(client, projeto, pergunta) {
  const chunks = await buscarChunksRelevantes(client, projeto.id, pergunta);

  if (chunks.length === 0) {
    return {
      resposta: "Nenhum documento foi processado para este projeto.",
      fontes: [],
      tokens_usados: 0,
    };
  }

  const fontes = chunks.map((row) => ({
    documento_nome: row.metadados.documento_nome,
    secao: row.metadados.secao,
    distancia: Number(row.distancia.toFixed(4)),
  }));

  if (AI_PROVIDER === "mock") {
    return {
      resposta: montarRespostaMock(pergunta, chunks),
      fontes,
      tokens_usados: 0,
    };
  }

  const contexto = chunks
    .map((row, i) => `[Trecho ${i + 1} - ${row.metadados.documento_nome}]\n${row.conteudo}`)
    .join("\n\n---\n\n");

  const systemPrompt = montarSystemPrompt({
    nomeProjeto: projeto.nome,
    personaTom: projeto.persona_tom,
    contexto,
  });

  const { texto, tokens } = await chamarLLM(systemPrompt, pergunta);

  return {
    resposta: texto,
    fontes,
    tokens_usados: tokens,
  };
}
