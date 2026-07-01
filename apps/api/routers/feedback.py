# ============================================================
# POST /api/feedback
#
# Registra o feedback do usuario (positiva/negativa) em uma
# mensagem especifica do assistente.
#
# IMPORTANTE: requer que o migration 03_adicionar_avaliacao.sql
# tenha sido aplicado no banco antes de usar este endpoint.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException

from database import obter_conexao_dependency
from models import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(body: FeedbackRequest, conexao=Depends(obter_conexao_dependency)):
    try:
        with conexao.cursor() as cursor:
            cursor.execute(
                """
                UPDATE mensagens
                SET avaliacao = %s, avaliacao_em = now()
                WHERE id = %s
                  AND papel = 'assistente'
                RETURNING id
                """,
                (body.avaliacao, body.mensagem_id),
            )
            atualizado = cursor.fetchone()

        if atualizado is None:
            conexao.rollback()
            raise HTTPException(
                status_code=404,
                detail="Mensagem nao encontrada ou nao e uma resposta do assistente.",
            )

        conexao.commit()
        return FeedbackResponse(ok=True)

    except HTTPException:
        raise
    except Exception as erro:
        conexao.rollback()
        # Se o campo avaliacao nao existir ainda (migration nao aplicado)
        if "avaliacao" in str(erro):
            raise HTTPException(
                status_code=500,
                detail="Campo de avaliacao nao existe ainda. Rode: sql/03_adicionar_avaliacao.sql",
            )
        raise HTTPException(status_code=500, detail="Erro interno ao registrar feedback.")
