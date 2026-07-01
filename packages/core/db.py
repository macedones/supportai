# ============================================================
# Conexao com o Postgres.
#
# Equivalente ao "new pg.Pool(...)" do rag.js/ingest.js/search.js.
# Em Python, psycopg2 nao tem um "pool global" tao direto quanto
# o pg do Node, entao expomos uma funcao simples que abre uma
# conexao por execucao do script (suficiente para CLI; numa API
# como FastAPI, isso evoluiria para um pool de verdade).
# ============================================================

import os
import psycopg2
import psycopg2.extras


def obter_conexao():
    """
    Abre uma conexao com o Postgres usando DATABASE_URL do .env.

    Equivalente a:
        const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });
        const client = await pool.connect();
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Defina DATABASE_URL no .env")

    # cursor_factory=DictCursor permite acessar colunas por nome,
    # tipo row["nome"], em vez de por indice row[0].
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.DictCursor)
