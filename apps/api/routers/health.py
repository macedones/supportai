# ============================================================
# GET /api/health
#
# Health check simples. Verifica se a API esta de pe e se
# consegue conectar ao banco de dados.
# ============================================================

from fastapi import APIRouter, Depends

from database import obter_conexao_dependency
from models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(conexao=Depends(obter_conexao_dependency)):
    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HealthResponse(status="ok", database="ok")
    except Exception as erro:
        return HealthResponse(status="ok", database="erro", detalhe=str(erro))
