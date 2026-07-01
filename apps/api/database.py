# ============================================================
# Dependency do FastAPI para obter uma conexao com o banco.
#
# Reaproveita obter_conexao() de packages/core_py/db.py — a MESMA
# funcao usada pelo ingest.py e search.py. Isso elimina a duplicacao
# que existia no JS (cada arquivo de apps/api criava seu proprio
# "getPool()").
#
# Uso num endpoint:
#   @router.post("/chat")
#   def chat(body: ChatRequest, conexao = Depends(obter_conexao_dependency)):
#       ...
# ============================================================

import path_config  # noqa: F401 - garante que packages/core_py esta no sys.path

from db import obter_conexao


def obter_conexao_dependency():
    """
    Generator usado como Depends() do FastAPI.

    O FastAPI executa o codigo antes do "yield" no inicio da
    requisicao, entrega a conexao pro endpoint, e roda o codigo
    depois do "yield" (fechar a conexao) quando a requisicao termina
    — mesmo se o endpoint lancar uma exception. E equivalente ao
    "try/finally { client.release() }" que aparecia em todo handler
    do Next.js.
    """
    conexao = obter_conexao()
    try:
        yield conexao
    finally:
        conexao.close()
