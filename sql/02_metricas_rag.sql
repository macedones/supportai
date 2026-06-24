-- ============================================================
-- SupportAI — Métricas de Qualidade do RAG
-- Rode isso no banco para ver um panorama do que está acontecendo
-- nas conversas de cada projeto.
--
-- Como rodar:
--   docker exec -it supportai-db psql -U supportai -d supportai -f /dev/stdin < sql/02_metricas_rag.sql
-- ============================================================

-- ------------------------------------------------------------
-- 1. VISÃO GERAL POR PROJETO
-- Quantas conversas, mensagens, tokens e se está citando fontes
-- ------------------------------------------------------------
SELECT
    p.nome                                          AS projeto,
    p.status,
    COUNT(DISTINCT c.id)                            AS total_conversas,
    COUNT(DISTINCT m.id) FILTER (WHERE m.papel = 'usuario')     AS total_perguntas,
    COUNT(DISTINCT m.id) FILTER (WHERE m.papel = 'assistente')  AS total_respostas,
    COALESCE(SUM(m.tokens_usados), 0)               AS tokens_total,
    ROUND(AVG(m.tokens_usados) FILTER (WHERE m.tokens_usados > 0), 0) AS tokens_medio_por_resposta,
    COUNT(DISTINCT m.id) FILTER (
        WHERE m.papel = 'assistente'
        AND jsonb_array_length(m.fontes_utilizadas) > 0
    )                                               AS respostas_com_fonte,
    COUNT(DISTINCT m.id) FILTER (
        WHERE m.papel = 'assistente'
        AND jsonb_array_length(m.fontes_utilizadas) = 0
    )                                               AS respostas_sem_fonte
FROM projetos p
LEFT JOIN conversas c ON c.projeto_id = p.id
LEFT JOIN mensagens m ON m.conversa_id = c.id
GROUP BY p.id, p.nome, p.status
ORDER BY total_perguntas DESC;

-- ------------------------------------------------------------
-- 2. DOCUMENTOS MAIS CITADOS
-- Quais fontes o RAG está recuperando com mais frequência
-- Indica quais documentos são mais relevantes para as perguntas reais
-- ------------------------------------------------------------
SELECT
    p.nome                                          AS projeto,
    fonte->>'documento_nome'                        AS documento,
    COUNT(*)                                        AS vezes_citado
FROM projetos p
JOIN conversas c ON c.projeto_id = p.id
JOIN mensagens m ON m.conversa_id = c.id,
    jsonb_array_elements(m.fontes_utilizadas) AS fonte
WHERE m.papel = 'assistente'
  AND jsonb_array_length(m.fontes_utilizadas) > 0
GROUP BY p.nome, fonte->>'documento_nome'
ORDER BY p.nome, vezes_citado DESC;

-- ------------------------------------------------------------
-- 3. RESPOSTAS SEM FONTE (possíveis falhas do RAG)
-- Mensagens do assistente que não citaram nenhum documento.
-- Pode indicar: pergunta fora do escopo dos documentos ingeridos,
-- ou RAG não encontrou chunks suficientemente relevantes.
-- ------------------------------------------------------------
SELECT
    p.nome                                          AS projeto,
    LEFT(m.conteudo, 120)                           AS inicio_resposta,
    m.criado_em
FROM projetos p
JOIN conversas c ON c.projeto_id = p.id
JOIN mensagens m ON m.conversa_id = c.id
WHERE m.papel = 'assistente'
  AND jsonb_array_length(m.fontes_utilizadas) = 0
  AND m.tokens_usados > 0   -- exclui respostas do modo mock (tokens = 0)
ORDER BY m.criado_em DESC
LIMIT 20;

-- ------------------------------------------------------------
-- 4. COBERTURA DE CHUNKS POR DOCUMENTO
-- Quantos chunks cada documento tem e se estão sendo usados
-- ------------------------------------------------------------
SELECT
    p.nome                                          AS projeto,
    d.nome_arquivo                                  AS documento,
    d.total_chunks,
    d.status_processamento,
    d.processado_em
FROM projetos p
JOIN documentos d ON d.projeto_id = p.id
ORDER BY p.nome, d.nome_arquivo;

-- ------------------------------------------------------------
-- 5. FEEDBACK DOS USUÁRIOS
-- (Preparado para quando o campo "avaliacao" existir em mensagens.
--  Hoje retorna vazio — será populado após implementar o 👍/👎
--  no widget e o campo na tabela.)
-- ------------------------------------------------------------
SELECT
    'Campo avaliacao ainda nao existe em mensagens.' AS aviso,
    'Rode o migration 03_adicionar_avaliacao.sql para habilitar.' AS instrucao;
