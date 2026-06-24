// ============================================================
// GET /api/metrics/[slug]
//
// Retorna métricas de qualidade do RAG para um projeto.
// Usado futuramente pelo Management Portal.
//
// Retorna:
// {
//   projeto: { nome, status, total_documentos, total_chunks },
//   conversas: { total, total_perguntas, total_respostas },
//   qualidade: {
//     respostas_com_fonte: number,    -- RAG encontrou contexto relevante
//     respostas_sem_fonte: number,    -- RAG não encontrou (fora do escopo)
//     taxa_cobertura_pct: number,     -- % de respostas com fonte
//     tokens_total: number,
//     tokens_medio: number
//   },
//   feedback: {
//     positivas: number,
//     negativas: number,
//     sem_avaliacao: number,
//     taxa_satisfacao_pct: number     -- positivas / (positivas + negativas)
//   },
//   documentos_mais_citados: [{ documento, vezes_citado }]
// }
// ============================================================

import { Pool } from "pg";

let pool;
function getPool() {
  if (!pool) pool = new Pool({ connectionString: process.env.DATABASE_URL });
  return pool;
}

export default async function handler(req, res) {
  if (req.method !== "GET")
    return res.status(405).json({ erro: "Use GET." });

  const { slug } = req.query;
  if (!slug)
    return res.status(400).json({ erro: "slug obrigatorio." });

  const client = await getPool().connect();

  try {
    // 1. Dados do projeto
    const projetoResult = await client.query(
      `SELECT p.id, p.nome, p.status,
              COUNT(DISTINCT d.id)    AS total_documentos,
              COALESCE(SUM(d.total_chunks), 0) AS total_chunks
       FROM projetos p
       LEFT JOIN documentos d ON d.projeto_id = p.id
       WHERE p.slug = $1
       GROUP BY p.id, p.nome, p.status`,
      [slug]
    );

    if (projetoResult.rows.length === 0)
      return res.status(404).json({ erro: `Projeto "${slug}" nao encontrado.` });

    const projeto = projetoResult.rows[0];

    // 2. Métricas de conversas e qualidade
    const qualidadeResult = await client.query(
      `SELECT
         COUNT(DISTINCT c.id)                                             AS total_conversas,
         COUNT(m.id) FILTER (WHERE m.papel = 'usuario')                  AS total_perguntas,
         COUNT(m.id) FILTER (WHERE m.papel = 'assistente')               AS total_respostas,
         COUNT(m.id) FILTER (
             WHERE m.papel = 'assistente'
             AND jsonb_array_length(m.fontes_utilizadas) > 0
         )                                                                AS respostas_com_fonte,
         COUNT(m.id) FILTER (
             WHERE m.papel = 'assistente'
             AND jsonb_array_length(m.fontes_utilizadas) = 0
             AND m.tokens_usados > 0
         )                                                                AS respostas_sem_fonte,
         COALESCE(SUM(m.tokens_usados), 0)                               AS tokens_total,
         ROUND(AVG(m.tokens_usados) FILTER (WHERE m.tokens_usados > 0))  AS tokens_medio
       FROM conversas c
       LEFT JOIN mensagens m ON m.conversa_id = c.id
       WHERE c.projeto_id = $1`,
      [projeto.id]
    );

    const q = qualidadeResult.rows[0];
    const comFonte = parseInt(q.respostas_com_fonte) || 0;
    const semFonte = parseInt(q.respostas_sem_fonte) || 0;
    const totalRespostas = comFonte + semFonte;
    const taxaCobertura = totalRespostas > 0
      ? Math.round((comFonte / totalRespostas) * 100)
      : null;

    // 3. Feedback (👍 / 👎) — campo adicionado pelo migration 03
    // Se o campo ainda não existir, retorna zeros sem quebrar.
    let feedback = { positivas: 0, negativas: 0, sem_avaliacao: 0, taxa_satisfacao_pct: null };
    try {
      const feedbackResult = await client.query(
        `SELECT
           COUNT(*) FILTER (WHERE avaliacao = 'positiva')  AS positivas,
           COUNT(*) FILTER (WHERE avaliacao = 'negativa')  AS negativas,
           COUNT(*) FILTER (WHERE avaliacao IS NULL)       AS sem_avaliacao
         FROM mensagens m
         JOIN conversas c ON c.id = m.conversa_id
         WHERE c.projeto_id = $1
           AND m.papel = 'assistente'`,
        [projeto.id]
      );
      const f = feedbackResult.rows[0];
      const pos = parseInt(f.positivas) || 0;
      const neg = parseInt(f.negativas) || 0;
      const taxaSatisfacao = (pos + neg) > 0
        ? Math.round((pos / (pos + neg)) * 100)
        : null;
      feedback = {
        positivas: pos,
        negativas: neg,
        sem_avaliacao: parseInt(f.sem_avaliacao) || 0,
        taxa_satisfacao_pct: taxaSatisfacao,
      };
    } catch {
      // Migration 03 ainda nao foi aplicado — retorna zeros
    }

    // 4. Documentos mais citados
    const citacoesResult = await client.query(
      `SELECT
         fonte->>'documento_nome'  AS documento,
         COUNT(*)                  AS vezes_citado
       FROM conversas c
       JOIN mensagens m ON m.conversa_id = c.id,
           jsonb_array_elements(m.fontes_utilizadas) AS fonte
       WHERE c.projeto_id = $1
         AND m.papel = 'assistente'
         AND jsonb_array_length(m.fontes_utilizadas) > 0
       GROUP BY fonte->>'documento_nome'
       ORDER BY vezes_citado DESC
       LIMIT 10`,
      [projeto.id]
    );

    res.status(200).json({
      projeto: {
        nome: projeto.nome,
        status: projeto.status,
        total_documentos: parseInt(projeto.total_documentos) || 0,
        total_chunks: parseInt(projeto.total_chunks) || 0,
      },
      conversas: {
        total: parseInt(q.total_conversas) || 0,
        total_perguntas: parseInt(q.total_perguntas) || 0,
        total_respostas: parseInt(q.total_respostas) || 0,
      },
      qualidade: {
        respostas_com_fonte: comFonte,
        respostas_sem_fonte: semFonte,
        taxa_cobertura_pct: taxaCobertura,
        tokens_total: parseInt(q.tokens_total) || 0,
        tokens_medio: parseInt(q.tokens_medio) || 0,
      },
      feedback,
      documentos_mais_citados: citacoesResult.rows.map((r) => ({
        documento: r.documento,
        vezes_citado: parseInt(r.vezes_citado),
      })),
    });
  } catch (err) {
    console.error("Erro em /api/metrics:", err);
    res.status(500).json({ erro: "Erro interno ao buscar metricas." });
  } finally {
    client.release();
  }
}
