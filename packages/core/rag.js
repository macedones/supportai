// ============================================================
// Copilot Runtime — Logica central do RAG (reutilizavel)
//
// Usado tanto pelo script CLI (search.js) quanto pela API
// (apps/api/pages/api/chat.js). Mantem a logica de busca +
// montagem de prompt + chamada ao LLM em um so lugar.
//
// PROVEDOR DE IA (AI_PROVIDER):
//   "openai" (padrao) — usa a API da OpenAI (embeddings + chat).
//                        Requer OPENAI_API_KEY com billing ativo.
//   "mock"            — nao faz nenhuma chamada externa. Util para
//                        desenvolvimento, testes e onboarding de
//                        contribuidores sem custo de API.
// ============================================================

import OpenAI from "openai";

const EMBEDDING_MODEL = "text-embedding-3-small";
const CHAT_MODEL = "gpt-4o-mini";
const TOP_K = 4;
const EMBEDDING_DIMENSIONS = 1536;

const AI_PROVIDER = process.env.AI_PROVIDER || "openai";

let openaiClient = null;
function getOpenAI() {
  if (!openaiClient) {
    openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openaiClient;
}

// ------------------------------------------------------------
// Hash simples (djb2) usado apenas pelo embedding mock.
// ------------------------------------------------------------
function hashString(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return hash >>> 0; // forca unsigned 32-bit
}

// ------------------------------------------------------------
// Embedding "mock" via feature hashing (bag-of-words com hash).
//
// Nao usa nenhuma API externa - zero custo. A similaridade
// resultante reflete sobreposicao de palavras entre textos, NAO
// significado semantico real (ex: "carro" e "automovel" nao
// serao considerados parecidos). E suficiente para validar todo
// o pipeline (chunking, armazenamento, busca vetorial via
// pgvector, API, widget) sem depender de credito na OpenAI.
//
// Para qualidade de resposta real, use AI_PROVIDER=openai.
// ------------------------------------------------------------
export function gerarEmbeddingMock(texto) {
  const vetor = new Array(EMBEDDING_DIMENSIONS).fill(0);

  const palavras =
    texto
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "") // remove acentos
      .match(/[a-z0-9]+/g) || [];

  for (const palavra of palavras) {
    const h = hashString(palavra);
    const indice = h % EMBEDDING_DIMENSIONS;
    const sinal = h & 0x10000 ? 1 : -1;
    vetor[indice] += sinal;
  }

  // Normalizacao L2 - necessaria para a distancia de cosseno
  // (usada pelo indice pgvector) funcionar de forma consistente.
  const norma = Math.sqrt(vetor.reduce((soma, v) => soma + v * v, 0)) || 1;
  return vetor.map((v) => v / norma);
}

export async function gerarEmbedding(texto) {
  if (AI_PROVIDER === "mock") {
    return gerarEmbeddingMock(texto);
  }

  const openai = getOpenAI();
  const resposta = await openai.embeddings.create({
    model: EMBEDDING_MODEL,
    input: texto,
  });
  return resposta.data[0].embedding;
}

// ------------------------------------------------------------
// Specialization Engine minimo: monta o system prompt
// parametrizado pelo projeto + contexto recuperado via RAG.
// ------------------------------------------------------------
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
// Resposta "mock": nao chama nenhum LLM. Apenas formata os
// trechos recuperados pela busca vetorial, para permitir
// validar o pipeline de retrieval sem custo de API.
// ------------------------------------------------------------
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

  return `[MODO MOCK - nenhuma chamada a OpenAI foi feita]

Pergunta: "${pergunta}"

Trechos mais relevantes encontrados na documentacao (busca por
sobreposicao de palavras, sem compreensao semantica real):

${trechos}

---
Esta e uma resposta simulada, usada para testar o pipeline de busca (RAG)
sem custo de API. Para respostas reais geradas por IA, defina
AI_PROVIDER=openai e configure uma OPENAI_API_KEY valida com billing ativo.`;
}

// ------------------------------------------------------------
// Busca os TOP_K chunks mais similares a pergunta, dentro de um
// projeto especifico (isolamento multi-tenant via projeto_id).
// ------------------------------------------------------------
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

// ------------------------------------------------------------
// Funcao principal: recebe a pergunta + dados do projeto,
// executa o pipeline completo de RAG e retorna a resposta
// estruturada (texto + fontes + tokens).
// ------------------------------------------------------------
export async function responderPergunta(client, projeto, pergunta) {
  const chunks = await buscarChunksRelevantes(client, projeto.id, pergunta);

  if (chunks.length === 0) {
    return {
      resposta:
        "Ainda nao tenho conhecimento suficiente sobre este sistema para responder. " +
        "Nenhum documento foi processado para este projeto.",
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

  const openai = getOpenAI();
  const resposta = await openai.chat.completions.create({
    model: CHAT_MODEL,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: pergunta },
    ],
    temperature: 0.2,
  });

  return {
    resposta: resposta.choices[0].message.content,
    fontes,
    tokens_usados: resposta.usage.total_tokens,
  };
}
