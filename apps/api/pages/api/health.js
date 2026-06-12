// ============================================================
// GET /api/health
//
// Health check simples. Verifica se a API esta de pe e se
// consegue conectar ao banco de dados.
// ============================================================

import { Pool } from "pg";

let pool;
function getPool() {
  if (!pool) {
    pool = new Pool({ connectionString: process.env.DATABASE_URL });
  }
  return pool;
}

export default async function handler(req, res) {
  try {
    const client = await getPool().connect();
    try {
      await client.query("SELECT 1");
      res.status(200).json({ status: "ok", database: "ok" });
    } finally {
      client.release();
    }
  } catch (err) {
    res.status(500).json({ status: "ok", database: "erro", detalhe: err.message });
  }
}
