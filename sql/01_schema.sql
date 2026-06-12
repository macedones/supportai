-- ============================================================
-- SupportAI / Assistant AI Platform
-- Schema MVP v0.4 — Multi-tenant (RAG-based)
-- PostgreSQL 15+ com extensão pgvector
-- ============================================================

-- ------------------------------------------------------------
-- Extensões necessárias
-- ------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector

-- ------------------------------------------------------------
-- ORGANIZACOES
-- O cliente direto da plataforma (ISV / Software House)
-- ------------------------------------------------------------
CREATE TABLE organizacoes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome        VARCHAR(200) NOT NULL,
    plano       VARCHAR(50)  NOT NULL DEFAULT 'free',
    criado_em   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE organizacoes IS 'ISV / Software House que utiliza a plataforma. Pode ter múltiplos projetos (especialistas).';
COMMENT ON COLUMN organizacoes.plano IS 'Ex.: free, starter, pro, enterprise';

-- ------------------------------------------------------------
-- USUARIOS_PORTAL
-- Pessoas que acessam o Management Portal
-- ------------------------------------------------------------
CREATE TABLE usuarios_portal (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
    nome            VARCHAR(200) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    senha_hash      VARCHAR(255) NOT NULL,
    papel           VARCHAR(50)  NOT NULL DEFAULT 'admin',
    criado_em       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_usuarios_portal_email UNIQUE (email)
);

COMMENT ON TABLE usuarios_portal IS 'Usuários que administram o portal (equipe do ISV).';
COMMENT ON COLUMN usuarios_portal.papel IS 'Ex.: owner, admin, member';

CREATE INDEX idx_usuarios_portal_org_id ON usuarios_portal(org_id);

-- ------------------------------------------------------------
-- PROJETOS
-- 1 projeto = 1 especialista virtual
-- ------------------------------------------------------------
CREATE TABLE projetos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
    nome            VARCHAR(200) NOT NULL,
    slug            VARCHAR(100) NOT NULL,
    dominio         VARCHAR(255),
    status          VARCHAR(30)  NOT NULL DEFAULT 'rascunho',
    persona_tom     VARCHAR(100) NOT NULL DEFAULT 'tecnico_e_direto',
    idioma_padrao   VARCHAR(10)  NOT NULL DEFAULT 'pt-BR',
    criado_em       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_projetos_slug UNIQUE (slug),
    CONSTRAINT chk_projetos_status CHECK (status IN ('rascunho', 'processando', 'ativo', 'pausado'))
);

COMMENT ON TABLE projetos IS 'Cada projeto representa um especialista virtual de um produto específico do ISV.';
COMMENT ON COLUMN projetos.slug IS 'Identificador público usado no widget (ex: data-project-id ou subdomínio).';
COMMENT ON COLUMN projetos.dominio IS 'Domínio onde o widget será embedado (para CORS/whitelist futura).';
COMMENT ON COLUMN projetos.persona_tom IS 'Parametriza o template de system prompt do Specialization Engine. Ex.: tecnico_e_direto, amigavel_e_didatico.';
COMMENT ON COLUMN projetos.status IS 'rascunho = criado mas sem documentos processados; processando = ingestão em andamento; ativo = pronto para uso; pausado = desativado pelo ISV.';

CREATE INDEX idx_projetos_org_id ON projetos(org_id);

-- ------------------------------------------------------------
-- CONFIGURACOES_PROJETO
-- Pares chave/valor flexíveis por projeto
-- ------------------------------------------------------------
CREATE TABLE configuracoes_projeto (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    projeto_id  UUID NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    chave       VARCHAR(100) NOT NULL,
    valor       TEXT,

    CONSTRAINT uq_config_projeto_chave UNIQUE (projeto_id, chave)
);

COMMENT ON TABLE configuracoes_projeto IS 'Configurações adicionais por projeto (ex: cor do widget, mensagem de boas-vindas, limites de uso).';

CREATE INDEX idx_configuracoes_projeto_projeto_id ON configuracoes_projeto(projeto_id);

-- ------------------------------------------------------------
-- DOCUMENTOS
-- Arquivos enviados pelo ISV (fonte de conhecimento)
-- ------------------------------------------------------------
CREATE TABLE documentos (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    projeto_id              UUID NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    nome_arquivo            VARCHAR(255) NOT NULL,
    tipo                    VARCHAR(30)  NOT NULL,
    status_processamento    VARCHAR(30)  NOT NULL DEFAULT 'pendente',
    total_chunks            INT          NOT NULL DEFAULT 0,
    enviado_em              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    processado_em           TIMESTAMPTZ,

    CONSTRAINT chk_documentos_tipo CHECK (tipo IN ('pdf', 'docx', 'md', 'txt', 'html', 'faq', 'openapi')),
    CONSTRAINT chk_documentos_status CHECK (status_processamento IN ('pendente', 'processando', 'concluido', 'erro'))
);

COMMENT ON TABLE documentos IS 'Documentos de conhecimento enviados pelo ISV (PDF, FAQ, Markdown, etc.).';
COMMENT ON COLUMN documentos.status_processamento IS 'Usado pelo portal para exibir progresso de ingestão (ex: "processando...", "pronto").';

CREATE INDEX idx_documentos_projeto_id ON documentos(projeto_id);
CREATE INDEX idx_documentos_status ON documentos(status_processamento);

-- ------------------------------------------------------------
-- CHUNKS
-- Pedaços de texto + embeddings para busca semântica (RAG)
-- ------------------------------------------------------------
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    documento_id    UUID NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    projeto_id      UUID NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    conteudo        TEXT NOT NULL,
    ordem           INT  NOT NULL,
    embedding       VECTOR(1536),  -- dimensão do text-embedding-3-small (OpenAI)
    metadados       JSONB NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE chunks IS 'Pedaços de texto extraídos dos documentos, com embedding vetorial para busca semântica.';
COMMENT ON COLUMN chunks.projeto_id IS 'Desnormalizado de documentos.projeto_id para permitir filtro direto e isolamento multi-tenant nas queries vetoriais.';
COMMENT ON COLUMN chunks.ordem IS 'Posição do chunk dentro do documento original (para reconstrução de contexto).';
COMMENT ON COLUMN chunks.embedding IS 'Vetor de 1536 dimensões (text-embedding-3-small). Ajustar se trocar de modelo de embedding.';
COMMENT ON COLUMN chunks.metadados IS 'Ex.: {"pagina": 4, "secao": "Configuração de NF-e", "documento_nome": "manual-fiscal.pdf"}';

CREATE INDEX idx_chunks_projeto_id ON chunks(projeto_id);
CREATE INDEX idx_chunks_documento_id ON chunks(documento_id);

-- Índice vetorial para busca por similaridade (cosine distance)
-- IVFFlat é um bom default para volumes pequenos/médios na fase de MVP.
CREATE INDEX idx_chunks_embedding_cosine
    ON chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ------------------------------------------------------------
-- CONVERSAS
-- Sessões de chat iniciadas a partir do widget
-- ------------------------------------------------------------
CREATE TABLE conversas (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    projeto_id           UUID NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    sessao_externa_id    VARCHAR(255),
    canal                VARCHAR(30) NOT NULL DEFAULT 'widget',
    iniciada_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultima_mensagem_em   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_conversas_canal CHECK (canal IN ('widget', 'api', 'slack', 'whatsapp'))
);

COMMENT ON TABLE conversas IS 'Sessões de conversa entre o usuário final (do ISV) e o especialista virtual.';
COMMENT ON COLUMN conversas.sessao_externa_id IS 'Identificador opcional fornecido pelo ISV para correlacionar com seu próprio sistema (ex: ID do usuário final).';
COMMENT ON COLUMN conversas.canal IS 'Canal de origem da conversa. Hoje só "widget" é usado; demais valores preparam expansão futura.';

CREATE INDEX idx_conversas_projeto_id ON conversas(projeto_id);
CREATE INDEX idx_conversas_sessao_externa_id ON conversas(sessao_externa_id);

-- ------------------------------------------------------------
-- MENSAGENS
-- Mensagens trocadas dentro de uma conversa
-- ------------------------------------------------------------
CREATE TABLE mensagens (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversa_id      UUID NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
    papel            VARCHAR(20) NOT NULL,
    conteudo         TEXT NOT NULL,
    fontes_utilizadas JSONB NOT NULL DEFAULT '[]'::jsonb,
    tokens_usados    INT,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_mensagens_papel CHECK (papel IN ('usuario', 'assistente', 'sistema'))
);

COMMENT ON TABLE mensagens IS 'Mensagens individuais dentro de uma conversa.';
COMMENT ON COLUMN mensagens.fontes_utilizadas IS 'Array de chunks/documentos citados na resposta. Ex.: [{"documento_id": "...", "documento_nome": "manual.pdf", "trecho": "..."}]';
COMMENT ON COLUMN mensagens.tokens_usados IS 'Tokens consumidos nesta mensagem (para analytics e billing futuro). NULL para mensagens de usuário.';

CREATE INDEX idx_mensagens_conversa_id ON mensagens(conversa_id);
CREATE INDEX idx_mensagens_criado_em ON mensagens(criado_em);

-- ------------------------------------------------------------
-- Trigger: atualizar conversas.ultima_mensagem_em automaticamente
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION atualizar_ultima_mensagem()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversas
    SET ultima_mensagem_em = NEW.criado_em
    WHERE id = NEW.conversa_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_atualizar_ultima_mensagem
    AFTER INSERT ON mensagens
    FOR EACH ROW
    EXECUTE FUNCTION atualizar_ultima_mensagem();

-- ============================================================
-- Fim do schema v0.4
-- ============================================================
