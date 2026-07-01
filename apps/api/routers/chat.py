# ============================================================
# POST /api/chat — Copilot Runtime
#
# Recebe: { project_slug, message, session_id? }
# Retorna: { resposta, fontes, tokens_usados, conversa_id, mensagem_id }
#
# Equivalente ao handler() de chat.js, mas sem duplicar a logica
# de RAG — tudo vem de packages/core_py via rag_service.py.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException

from database import obter_conexao_dependency
from models import ChatRequest, ChatResponse
from rag_service import processar_chat

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, conexao=Depends(obter_conexao_dependency)):
    try:
        resultado = processar_chat(
            conexao,
            project_slug=body.project_slug,
            message=body.message,
            session_id=body.session_id,
        )
        return resultado

    except ValueError as erro:
        # Erros de negocio levantados por processar_chat, no formato
        # "CODIGO:mensagem" — usamos o codigo pra decidir o status HTTP.
        codigo, _, mensagem = str(erro).partition(":")
        status_map = {"PROJETO_NAO_ENCONTRADO": 404, "PROJETO_INATIVO": 409}
        raise HTTPException(status_code=status_map.get(codigo, 400), detail=mensagem)

    except Exception:
        conexao.rollback()
        raise HTTPException(status_code=500, detail="Erro interno ao processar a pergunta.")
