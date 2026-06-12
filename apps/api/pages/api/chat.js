// ============================================================
// POST /api/chat
//
// Endpoint principal do Copilot Runtime (Fase 1).
//
// Recebe: { project_slug: string, message: string, session_id?: string }
// Retorna: { resposta: string, fontes: [...], tokens_usados: number, conversa_id: string }
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

  if (!process.env.OPENAI_API_KEY || !process.env.DATABASE_URL) {
    res.status(500).json({ erro: "Servidor nao configurado (variaveis de ambiente ausentes)." });
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
    const openaiClient = getOpenAI();
    const embeddingResp = await openaiClient.embeddings.create({
      model: EMBEDDING_MODEL,
      input: message,
    });
    const embeddingPergunta = embeddingResp.data[0].embedding;

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
    } else {
      const contexto = buscaResult.rows
        .map((row, i) => `[Trecho ${i + 1} - ${row.metadados.documento_nome}]\n${row.conteudo}`)
        .join("\n\n---\n\n");

      const systemPrompt = montarSystemPrompt({
        nomeProjeto: projeto.nome,
        personaTom: projeto.persona_tom,
        contexto,
      });

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
