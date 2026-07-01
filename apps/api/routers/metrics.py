# ============================================================
# GET /api/metrics/{slug}
#
# Retorna metricas de qualidade do RAG para um projeto.
# Usado futuramente pelo Management Portal.
#
# Equivalente a [slug].js. As queries SQL sao praticamente
# identicas — a logica de negocio aqui e majoritariamente SQL,
# entao a "tradução" mais importante e estrutural (rotas, modelos).
# ============================================================

from fastapi import APIRouter, Depends, HTTPException

from database import obter_conexao_dependency
from models import (
    ConversasMetricas,
    DocumentoCitado,
    FeedbackMetricas,
    MetricsResponse,
    ProjetoMetricas,
    QualidadeMetricas,
)

router = APIRouter()


@router.get("/metrics/{slug}", response_model=MetricsResponse)
def metrics(slug: str, conexao=Depends(obter_conexao_dependency)):
    with conexao.cursor() as cursor:
        # 1. Dados do projeto
        cursor.execute(
            """
            SELECT p.id, p.nome, p.status,
                   COUNT(DISTINCT d.id) AS total_documentos,
                   COALESCE(SUM(d.total_chunks), 0) AS total_chunks
            FROM projetos p
            LEFT JOIN documentos d ON d.projeto_id = p.id
            WHERE p.slug = %s
            GROUP BY p.id, p.nome, p.status
            """,
            (slug,),
        )
        projeto = cursor.fetchone()

        if projeto is None:
            raise HTTPException(status_code=404, detail=f'Projeto "{slug}" nao encontrado.')

        # 2. Metricas de conversas e qualidade
        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT c.id) AS total_conversas,
                COUNT(m.id) FILTER (WHERE m.papel = 'usuario') AS total_perguntas,
                COUNT(m.id) FILTER (WHERE m.papel = 'assistente') AS total_respostas,
                COUNT(m.id) FILTER (
                    WHERE m.papel = 'assistente'
                    AND jsonb_array_length(m.fontes_utilizadas) > 0
                ) AS respostas_com_fonte,
                COUNT(m.id) FILTER (
                    WHERE m.papel = 'assistente'
                    AND jsonb_array_length(m.fontes_utilizadas) = 0
                    AND m.tokens_usados > 0
                ) AS respostas_sem_fonte,
                COALESCE(SUM(m.tokens_usados), 0) AS tokens_total,
                ROUND(AVG(m.tokens_usados) FILTER (WHERE m.tokens_usados > 0)) AS tokens_medio
            FROM conversas c
            LEFT JOIN mensagens m ON m.conversa_id = c.id
            WHERE c.projeto_id = %s
            """,
            (projeto["id"],),
        )
        q = cursor.fetchone()

        com_fonte = q["respostas_com_fonte"] or 0
        sem_fonte = q["respostas_sem_fonte"] or 0
        total_respostas = com_fonte + sem_fonte
        taxa_cobertura = round((com_fonte / total_respostas) * 100) if total_respostas > 0 else None

        # 3. Feedback (campo adicionado pelo migration 03)
        # Se o campo ainda nao existir, retorna zeros sem quebrar.
        feedback = FeedbackMetricas(positivas=0, negativas=0, sem_avaliacao=0, taxa_satisfacao_pct=None)
        try:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE avaliacao = 'positiva') AS positivas,
                    COUNT(*) FILTER (WHERE avaliacao = 'negativa') AS negativas,
                    COUNT(*) FILTER (WHERE avaliacao IS NULL) AS sem_avaliacao
                FROM mensagens m
                JOIN conversas c ON c.id = m.conversa_id
                WHERE c.projeto_id = %s
                  AND m.papel = 'assistente'
                """,
                (projeto["id"],),
            )
            f = cursor.fetchone()
            pos = f["positivas"] or 0
            neg = f["negativas"] or 0
            taxa_satisfacao = round((pos / (pos + neg)) * 100) if (pos + neg) > 0 else None
            feedback = FeedbackMetricas(
                positivas=pos,
                negativas=neg,
                sem_avaliacao=f["sem_avaliacao"] or 0,
                taxa_satisfacao_pct=taxa_satisfacao,
            )
        except Exception:
            # Migration 03 ainda nao foi aplicado — mantem os zeros
            conexao.rollback()

        # 4. Documentos mais citados
        cursor.execute(
            """
            SELECT
                fonte->>'documento_nome' AS documento,
                COUNT(*) AS vezes_citado
            FROM conversas c
            JOIN mensagens m ON m.conversa_id = c.id,
                jsonb_array_elements(m.fontes_utilizadas) AS fonte
            WHERE c.projeto_id = %s
              AND m.papel = 'assistente'
              AND jsonb_array_length(m.fontes_utilizadas) > 0
            GROUP BY fonte->>'documento_nome'
            ORDER BY vezes_citado DESC
            LIMIT 10
            """,
            (projeto["id"],),
        )
        citacoes = cursor.fetchall()

    return MetricsResponse(
        projeto=ProjetoMetricas(
            nome=projeto["nome"],
            status=projeto["status"],
            total_documentos=projeto["total_documentos"] or 0,
            total_chunks=projeto["total_chunks"] or 0,
        ),
        conversas=ConversasMetricas(
            total=q["total_conversas"] or 0,
            total_perguntas=q["total_perguntas"] or 0,
            total_respostas=q["total_respostas"] or 0,
        ),
        qualidade=QualidadeMetricas(
            respostas_com_fonte=com_fonte,
            respostas_sem_fonte=sem_fonte,
            taxa_cobertura_pct=taxa_cobertura,
            tokens_total=q["tokens_total"] or 0,
            tokens_medio=q["tokens_medio"] or 0,
        ),
        feedback=feedback,
        documentos_mais_citados=[
            DocumentoCitado(documento=row["documento"], vezes_citado=row["vezes_citado"])
            for row in citacoes
        ],
    )
