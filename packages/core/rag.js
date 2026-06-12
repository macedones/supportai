// ============================================================
// Copilot Runtime — Logica central do RAG (reutilizavel)
//
// Usado tanto pelo script CLI (search.js) quanto pela API
// (apps/api/pages/api/chat.js). Mantem a logica de busca +
// montagem de prompt + chamada ao LLM em um so lugar.
// ============================================================

import OpenAI from "openai/index.js";

const EMBEDDING_MODEL = "text-embedding-3-small";
const CHAT_MODEL = "gpt-4o-mini";
const TOP_K = 4;

let openaiClient = null;
function getOpenAI() {
  if (!openaiClient) {
    openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openaiClient;
}

export async function gerarEmbedding(texto) {
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

  const fontes = chunks.map((row) => ({
    documento_nome: row.metadados.documento_nome,
    secao: row.metadados.secao,
    distancia: Number(row.distancia.toFixed(4)),
  }));

  return {
    resposta: resposta.choices[0].message.content,
    fontes,
    tokens_usados: resposta.usage.total_tokens,
  };
}
