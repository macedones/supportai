# ============================================================
# rag_service — orquestra o pipeline de chat: busca/cria a
# conversa, salva mensagens, chama o RAG (de packages/core_py/rag.py)
# e salva a resposta.
#
# Equivalente a logica que estava dentro do handler() de chat.js,
# so que extraida pra uma funcao testável e reaproveitavel — em
# vez de tudo dentro do endpoint.
# ============================================================

import json

import path_config  # noqa: F401

from rag import responder_pergunta


def obter_projeto_por_slug(conexao, slug: str) -> dict | None:
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT id, nome, persona_tom, status FROM projetos WHERE slug = %s",
            (slug,),
        )
        return cursor.fetchone()


def obter_ou_criar_conversa(conexao, projeto_id: str, session_id: str | None) -> str:
    with conexao.cursor() as cursor:
        if session_id:
            cursor.execute(
                "SELECT id FROM conversas WHERE projeto_id = %s AND sessao_externa_id = %s",
                (projeto_id, session_id),
            )
            existente = cursor.fetchone()
            if existente:
                return existente["id"]

        cursor.execute(
            """
            INSERT INTO conversas (projeto_id, sessao_externa_id, canal)
            VALUES (%s, %s, 'widget')
            RETURNING id
            """,
            (projeto_id, session_id),
        )
        return cursor.fetchone()["id"]


def salvar_mensagem_usuario(conexao, conversa_id: str, mensagem: str) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            "INSERT INTO mensagens (conversa_id, papel, conteudo) VALUES (%s, 'usuario', %s)",
            (conversa_id, mensagem),
        )


def salvar_mensagem_assistente(
    conexao, conversa_id: str, resposta: str, fontes: list[dict], tokens_usados: int
) -> str:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO mensagens (conversa_id, papel, conteudo, fontes_utilizadas, tokens_usados)
            VALUES (%s, 'assistente', %s, %s, %s)
            RETURNING id
            """,
            (conversa_id, resposta, json.dumps(fontes), tokens_usados),
        )
        return cursor.fetchone()["id"]


def processar_chat(conexao, project_slug: str, message: str, session_id: str | None) -> dict:
    """
    Pipeline completo de uma pergunta no chat: valida o projeto,
    cria/reaproveita a conversa, persiste a pergunta, chama o RAG
    (busca + LLM) e persiste a resposta.

    Levanta ValueError com uma mensagem de erro de negocio quando o
    projeto nao existe ou nao esta ativo — o router decide o status
    HTTP certo pra cada caso.
    """
    projeto = obter_projeto_por_slug(conexao, project_slug)
    if projeto is None:
        raise ValueError(f'PROJETO_NAO_ENCONTRADO:Projeto "{project_slug}" nao encontrado.')

    if projeto["status"] != "ativo":
        raise ValueError(f'PROJETO_INATIVO:Projeto nao esta ativo (status: {projeto["status"]}).')

    conversa_id = obter_ou_criar_conversa(conexao, projeto["id"], session_id)
    salvar_mensagem_usuario(conexao, conversa_id, message)

    resultado = responder_pergunta(conexao, projeto, message)

    mensagem_id = salvar_mensagem_assistente(
        conexao,
        conversa_id,
        resultado["resposta"],
        resultado["fontes"],
        resultado["tokens_usados"],
    )

    conexao.commit()

    return {
        "resposta": resultado["resposta"],
        "fontes": resultado["fontes"],
        "tokens_usados": resultado["tokens_usados"],
        "conversa_id": conversa_id,
        "mensagem_id": mensagem_id,
    }
