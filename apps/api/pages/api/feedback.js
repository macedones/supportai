// ============================================================
// POST /api/feedback
//
// Registra o feedback do usuario (👍 / 👎) em uma mensagem
// especifica do assistente.
//
// Recebe: { mensagem_id: string, avaliacao: "positiva" | "negativa" }
// Retorna: { ok: true }
//
// IMPORTANTE: requer que o migration 03_adicionar_avaliacao.sql
// tenha sido aplicado no banco antes de usar este endpoint.
// ============================================================

import { Pool } from "pg";

let pool;
function getPool() {
  if (!pool) pool = new Pool({ connectionString: process.env.DATABASE_URL });
  return pool;
}

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST")
    return res.status(405).json({ erro: "Use POST." });

  const { mensagem_id, avaliacao } = req.body ?? {};

  if (!mensagem_id || !avaliacao)
    return res.status(400).json({ erro: "Campos obrigatorios: mensagem_id, avaliacao" });

  if (!["positiva", "negativa"].includes(avaliacao))
    return res.status(400).json({ erro: "avaliacao deve ser 'positiva' ou 'negativa'" });

  const client = await getPool().connect();

  try {
    const result = await client.query(
      `UPDATE mensagens
       SET avaliacao = $1, avaliacao_em = now()
       WHERE id = $2
         AND papel = 'assistente'   -- so respostas do assistente podem ser avaliadas
       RETURNING id`,
      [avaliacao, mensagem_id]
    );

    if (result.rows.length === 0)
      return res.status(404).json({ erro: "Mensagem nao encontrada ou nao e uma resposta do assistente." });

    res.status(200).json({ ok: true });
  } catch (err) {
    console.error("Erro em /api/feedback:", err);
    // Se o campo avaliacao nao existir ainda (migration nao aplicado)
    if (err.message?.includes("avaliacao")) {
      return res.status(500).json({
        erro: "Campo de avaliacao nao existe ainda. Rode: sql/03_adicionar_avaliacao.sql",
      });
    }
    res.status(500).json({ erro: "Erro interno ao registrar feedback." });
  } finally {
    client.release();
  }
}
