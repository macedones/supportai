// ============================================================
// POST /api/chat
//
// Endpoint principal do Copilot Runtime (Fase 1).
//
// Recebe: { project_slug: string, message: string, session_id?: string }
// Retorna: { resposta: string, fontes: [...], tokens_usados: number, conversa_id: string }
//
// PROVEDOR DE IA (AI_PROVIDER):
//   "openai" (padrao) — usa a API da OpenAI (embeddings + chat).
//                        Requer OPENAI_API_KEY com billing ativo.
//   "mock"            — nao faz nenhuma chamada externa. Util para
//                        desenvolvimento e testes sem custo de API.
//
// NOTA DE ARQUITETURA:
// A logica de RAG (embeddings, busca vetorial, prompt) esta
// duplicada aqui em vez de importada de packages/core/rag.js.
// Motivo: packages/core e um modulo ESM puro (type: "module"),
// e configurar import cross-package em Next.js exigiria
// "transpilePackages" + ajustes de monorepo (workspaces) que
// sao complexidade desnecessaria para a Fase 1.
//
// Quando o monorepo for formalizado com workspaces (npm/pnpm),
// esta logica deve ser unificada em um pacote compartilhado
// importado por ambos (CLI e API). Marcado como debito tecnico
// conhecido — ver checkpoint do projeto.
// ============================================================

import { Pool } from "pg";
import OpenAI from "openai";

const EMBEDDING_MODEL = "text-embedding-3-small";
const CHAT_MODEL = "gpt-4o-mini";
const TOP_K = 4;
const EMBEDDING_DIMENSIONS = 1536;

const AI_PROVIDER = process.env.AI_PROVIDER || "openai";

let pool;
function getPool() {
  if (!pool) {
    pool = new Pool({ connectionString: process.env.DATABASE_URL });
  }
  return pool;
}

let openai;
function getOpenAI() {
  if (!openai) {
    openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openai;
}

// ------------------------------------------------------------
// Hash simples (djb2) usado apenas pelo embedding mock.
// Mesma implementacao de packages/core/rag.js — ver nota de
// arquitetura no topo do arquivo sobre a duplicacao.
// ------------------------------------------------------------
function hashString(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return hash >>> 0;
}

// ------------------------------------------------------------
// Embedding "mock" via feature hashing (bag-of-words com hash).
// Zero custo, sem API externa. Ver explicacao completa em
// packages/core/rag.js.
// ------------------------------------------------------------
function gerarEmbeddingMock(texto) {
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

async function gerarEmbedding(texto) {
  if (AI_PROVIDER === "mock") {
    return gerarEmbeddingMock(texto);
  }
  const openaiClient = getOpenAI();
  const resposta = await openaiClient.embeddings.create({
    model: EMBEDDING_MODEL,
    input: texto,
  });
  return resposta.data[0].embedding;
}

function montarSystemPrompt({ nomeProjeto, personaTom, contexto }) {
  const tomDescricao =
    {
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
// Resposta "mock": nao chama nenhum LLM, apenas formata os
// trechos recuperados pela busca vetorial.
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

export default async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.status(200).end();
    return;
  }

  if (req.method !== "POST") {
    res.status(405).json({ erro: "Metodo nao permitido. Use POST." });
    return;
  }

  const { project_slug, message, session_id } = req.body ?? {};

  if (!project_slug || !message) {
    res.status(400).json({ erro: "Campos obrigatorios: project_slug, message" });
    return;
  }

  if (!process.env.DATABASE_URL) {
    res.status(500).json({ erro: "Servidor nao configurado (DATABASE_URL ausente)." });
    return;
  }

  if (AI_PROVIDER !== "mock" && !process.env.OPENAI_API_KEY) {
    res.status(500).json({ erro: "Servidor nao configurado (OPENAI_API_KEY ausente). Defina AI_PROVIDER=mock para testar sem OpenAI." });
    return;
  }

  const client = await getPool().connect();

  try {
    // 1. Busca o projeto pelo slug
    const projetoResult = await client.query(
      `SELECT id, nome, persona_tom, status FROM projetos WHERE slug = $1`,
      [project_slug]
    );

    if (projetoResult.rows.length === 0) {
      res.status(404).json({ erro: `Projeto "${project_slug}" nao encontrado.` });
      return;
    }

    const projeto = projetoResult.rows[0];

    if (projeto.status !== "ativo") {
      res.status(409).json({ erro: `Projeto "${project_slug}" ainda nao esta ativo (status: ${projeto.status}).` });
      return;
    }

    // 2. Garante que existe uma conversa (cria se necessario)
    let conversaId;
    if (session_id) {
      const conversaExistente = await client.query(
        `SELECT id FROM conversas WHERE projeto_id = $1 AND sessao_externa_id = $2`,
        [projeto.id, session_id]
      );
      if (conversaExistente.rows.length > 0) {
        conversaId = conversaExistente.rows[0].id;
      }
    }

    if (!conversaId) {
      const novaConversa = await client.query(
        `INSERT INTO conversas (projeto_id, sessao_externa_id, canal)
         VALUES ($1, $2, 'widget')
         RETURNING id`,
        [projeto.id, session_id ?? null]
      );
      conversaId = novaConversa.rows[0].id;
    }

    // 3. Salva a mensagem do usuario
    await client.query(
      `INSERT INTO mensagens (conversa_id, papel, conteudo)
       VALUES ($1, 'usuario', $2)`,
      [conversaId, message]
    );

    // 4. Embedding da pergunta + busca vetorial (RAG)
    const embeddingPergunta = await gerarEmbedding(message);

    const buscaResult = await client.query(
      `SELECT c.conteudo, c.metadados, (c.embedding <=> $1) AS distancia
       FROM chunks c
       WHERE c.projeto_id = $2
       ORDER BY c.embedding <=> $1
       LIMIT $3`,
      [`[${embeddingPergunta.join(",")}]`, projeto.id, TOP_K]
    );

    let respostaTexto;
    let fontes = [];
    let tokensUsados = 0;

    if (buscaResult.rows.length === 0) {
      respostaTexto =
        "Ainda nao tenho conhecimento suficiente sobre este sistema para responder. " +
        "Nenhum documento foi processado para este projeto.";
    } else if (AI_PROVIDER === "mock") {
      respostaTexto = montarRespostaMock(message, buscaResult.rows);
      fontes = buscaResult.rows.map((row) => ({
        documento_nome: row.metadados.documento_nome,
        secao: row.metadados.secao,
      }));
    } else {
      const contexto = buscaResult.rows
        .map((row, i) => `[Trecho ${i + 1} - ${row.metadados.documento_nome}]\n${row.conteudo}`)
        .join("\n\n---\n\n");

      const systemPrompt = montarSystemPrompt({
        nomeProjeto: projeto.nome,
        personaTom: projeto.persona_tom,
        contexto,
      });

      const openaiClient = getOpenAI();
      const chatResp = await openaiClient.chat.completions.create({
        model: CHAT_MODEL,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: message },
        ],
        temperature: 0.2,
      });

      respostaTexto = chatResp.choices[0].message.content;
      tokensUsados = chatResp.usage.total_tokens;
      fontes = buscaResult.rows.map((row) => ({
        documento_nome: row.metadados.documento_nome,
        secao: row.metadados.secao,
      }));
    }

    // 5. Salva a resposta do assistente
    await client.query(
      `INSERT INTO mensagens (conversa_id, papel, conteudo, fontes_utilizadas, tokens_usados)
       VALUES ($1, 'assistente', $2, $3, $4)`,
      [conversaId, respostaTexto, JSON.stringify(fontes), tokensUsados]
    );

    res.status(200).json({
      resposta: respostaTexto,
      fontes,
      tokens_usados: tokensUsados,
      conversa_id: conversaId,
    });
  } catch (err) {
    console.error("Erro em /api/chat:", err);
    res.status(500).json({ erro: "Erro interno ao processar a pergunta." });
  } finally {
    client.release();
  }
}
