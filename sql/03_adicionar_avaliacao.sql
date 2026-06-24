-- ============================================================
-- Migration 03 — Adiciona campo de avaliação em mensagens
--
-- Permite que o usuário final avalie cada resposta do assistente
-- diretamente no widget (👍 / 👎). Dado mais valioso que qualquer
-- métrica automática — indica quais respostas realmente ajudaram.
--
-- Como rodar:
--   docker exec -i supportai-db psql -U supportai -d supportai < sql/03_adicionar_avaliacao.sql
-- ============================================================

ALTER TABLE mensagens
    ADD COLUMN IF NOT EXISTS avaliacao VARCHAR(10)
        CHECK (avaliacao IN ('positiva', 'negativa')),
    ADD COLUMN IF NOT EXISTS avaliacao_em TIMESTAMPTZ;

COMMENT ON COLUMN mensagens.avaliacao IS
    'Feedback do usuario final: positiva (👍) ou negativa (👎). NULL = nao avaliado.';

COMMENT ON COLUMN mensagens.avaliacao_em IS
    'Quando o feedback foi registrado.';

-- Índice para facilitar queries de métricas de feedback
CREATE INDEX IF NOT EXISTS idx_mensagens_avaliacao
    ON mensagens(avaliacao)
    WHERE avaliacao IS NOT NULL;
