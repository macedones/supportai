# SupportAI

Plataforma open source para transformar documentação de software em um assistente de suporte embedável. ISVs fornecem seus manuais e FAQs; a plataforma gera um chat especializado que responde com base exclusivamente nesses documentos, citando a fonte de cada informação.

O assistente não usa o conhecimento geral do LLM — responde apenas com o que foi ingerido. Isso diferencia um especialista virtual de um chatbot genérico.

---

## Como funciona

1. O ISV ingere sua documentação (arquivos `.md`) via CLI
2. Os documentos são divididos em chunks, vetorizados e armazenados no PostgreSQL com pgvector
3. O usuário pergunta ao widget embedado no site do produto
4. A API busca os chunks mais relevantes por similaridade semântica, monta o contexto e chama o LLM
5. A resposta inclui a referência ao trecho da documentação que a embasou

**Exemplo:**

Pergunta: *"O que é uma glosa técnica e qual o prazo para recurso?"*

Resposta (Groq + Llama 3.1, zero custo):
```
Uma glosa técnica é a recusa de pagamento por parte da operadora de saúde,
geralmente por questionamento sobre a pertinência clínica do procedimento.
O prazo para recurso varia por operadora, geralmente entre 30 e 90 dias corridos
a partir do recebimento do demonstrativo.
(manual-modulo-faturamento.md, seção "Tipos de Glosa")
```

---

## Status

| Componente | Status |
|---|---|
| Schema multi-tenant (PostgreSQL + pgvector) | Pronto |
| Knowledge Engine — ingestão de MD, chunking, embeddings | Pronto |
| Copilot Runtime — API de chat com RAG | Pronto |
| Widget embedável `<assistant-ai>` — Web Component | Pronto |
| Multi-provider (Groq, Ollama, OpenAI, Mock) | Pronto |
| Demo: MedSys ERP Hospitalar | Funcional |
| Management Portal | Em andamento |
| Demo: ERP Jurídico | Em andamento |
| Ingestão de Swagger/OpenAPI (Python) | Fase 2 |

---

## Arquitetura

```
┌──────────────────────────────────────────┐
│  Widget (<assistant-ai>)                  │
│  apps/widget — Web Component, ~8KB        │
│  Shadow DOM — sem conflito de CSS         │
└─────────────────┬────────────────────────┘
                   │ POST /api/chat
┌─────────────────▼────────────────────────┐
│  Copilot Runtime (API)                    │
│  apps/api — Next.js API Routes            │
│  - Embedding da pergunta                  │
│  - Busca semântica (pgvector)             │
│  - Monta prompt especializado (RAG)       │
│  - Chama LLM (Groq / Ollama / OpenAI)    │
│  - Persiste conversa no banco             │
└─────────────────┬────────────────────────┘
                   │
┌─────────────────▼────────────────────────┐
│  PostgreSQL + pgvector                    │
│  organizacoes > projetos > documentos     │
│  > chunks (embeddings) > conversas        │
│  > mensagens (fontes + tokens)            │
└─────────────────▲────────────────────────┘
                   │
┌─────────────────┴────────────────────────┐
│  Knowledge Engine (ingestão offline)      │
│  packages/core/ingest.js                  │
│  - Lê arquivos .md                        │
│  - Divide em chunks (~1500 chars)         │
│  - Gera embeddings (Ollama local)         │
│  - Insere no banco com metadados          │
└──────────────────────────────────────────┘
```

---

## Estrutura do repositório

```
supportai/
├── docker-compose.yml           # Postgres + pgvector (auto-init do schema)
├── sql/01_schema.sql            # Schema multi-tenant com pgvector
├── packages/core/               # Knowledge Engine + RAG
│   ├── ingest.js                # Ingestão de documentos
│   ├── search.js                # Teste de busca via CLI
│   └── rag.js                   # Lógica RAG multi-provider
├── apps/
│   ├── api/                     # Copilot Runtime (Next.js, porta 3001)
│   │   └── pages/api/
│   │       ├── chat.js          # Endpoint principal
│   │       └── health.js        # Health check
│   └── widget/                  # Widget embedável
│       ├── src/widget.js        # Web Component <assistant-ai>
│       ├── build.js             # Build com esbuild
│       └── demo.html            # Página de demonstração
└── demo/
    ├── docs-erp-hospitalar/     # Documentação fictícia (demo ativa)
    └── docs-erp-juridico/       # Em construção
```

---

## Rodando localmente

### Pré-requisitos

- Node.js 20+
- Docker + Docker Compose
- Um provedor de IA (ver tabela abaixo)

### Provedores suportados

| `AI_PROVIDER` | Chat | Embeddings | Custo | Requisito |
|---|---|---|---|---|
| `groq` (recomendado) | Groq API — Llama 3.1 8B | Ollama local | Gratuito | Conta em console.groq.com + Ollama |
| `ollama` | Ollama local — Llama 3.2 | Ollama local | Zero | Ollama instalado |
| `openai` | GPT-4o mini | text-embedding-3-small | Pago | Billing ativo |
| `mock` | Simulado (trechos brutos) | Feature hashing | Zero | Nada |

### 1. Subir o banco

```bash
docker compose up -d
```

Sobe PostgreSQL com pgvector. O schema é aplicado automaticamente a partir de `sql/01_schema.sql`.

### 2. Instalar Ollama

Acesse [ollama.com](https://ollama.com), instale e execute:

```bash
ollama pull nomic-embed-text   # embeddings (~270MB)
ollama pull llama3.2            # chat local, opcional se usar Groq (~2GB)
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example packages/core/.env
cp apps/api/.env.example apps/api/.env.local
```

Preencha `GROQ_API_KEY` nos dois arquivos. Chave gratuita em [console.groq.com](https://console.groq.com).

Não commite `.env` ou `.env.local` — já estão no `.gitignore`.

### 4. Ingerir a documentação de demo

```bash
cd packages/core
npm install
node ingest.js erp-hospitalar ../../demo/docs-erp-hospitalar
```

### 5. Testar via CLI (opcional)

```bash
node search.js erp-hospitalar "o que é uma glosa técnica?"
```

### 6. Subir a API

```bash
cd apps/api
npm install
npm run dev
# http://localhost:3001
```

### 7. Buildar e testar o widget

```bash
cd apps/widget
npm install
npm run build
npx serve .
```

Abra `demo.html` e teste com perguntas como:

- *"Se o paciente faltar 3 vezes em 90 dias, ele fica bloqueado de agendar?"*
- *"O que é uma glosa técnica e qual o prazo para recurso?"*
- *"Como desbloquear um usuário após tentativas de login incorretas?"*

---

## Embedando em outro site

```html
<script src="https://sua-url/widget.js"></script>
<assistant-ai
  project="erp-hospitalar"
  api-url="https://sua-api.exemplo.com"
  color="#6d4aff"
  greeting="Olá! Como posso ajudar?"
></assistant-ai>
```

| Atributo | Obrigatório | Descrição |
|---|---|---|
| `project` | Sim | Slug do projeto (definido na ingestão) |
| `api-url` | Sim | URL base da API (Copilot Runtime) |
| `position` | Não | `bottom-right` (padrão) ou `bottom-left` |
| `color` | Não | Cor de destaque em hex |
| `greeting` | Não | Mensagem inicial do assistente |

---

## Decisões de design

**Respostas baseadas exclusivamente em documentação.** O LLM não complementa com conhecimento geral. Se a informação não foi ingerida, o assistente não responde.

**Multi-tenant desde o início.** Cada projeto é isolado. Um ISV pode ter múltiplos projetos sob a mesma conta sem vazamento de contexto entre eles.

**Sem acesso a banco de produção de terceiros.** O conhecimento vem apenas da documentação fornecida pelo ISV. Acesso a dados reais via Tools/Actions é funcionalidade de fase futura, com controle explícito do ISV.

**Sem lock-in de provedor.** Groq, Ollama, OpenAI e modo mock são configuráveis por variável de ambiente, sem mudança de código.

---

## Roadmap

| Fase | Objetivo | Stack |
|---|---|---|
| 1 — Concluída | Documentação + FAQ + Chat (RAG + widget multi-provider) | JavaScript |
| 2 | Ingestão de Swagger/OpenAPI | Python |
| 3 | Tools Runtime — consulta de dados reais via ferramentas | Python |
| 4 | Action Runtime — execução de ações dentro do software | Python |
| 5 | Copilot Especializado — especialista como operador do sistema | Python |
| 6 | White Label Platform | — |

---

## Contribuindo

Projeto em estágio inicial. Issues e PRs são bem-vindos.

## Licença

A definir.
