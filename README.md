# SupportAI — Assistant AI Platform

> Plataforma open source que transforma a documentação de um software em um
> **especialista virtual embedável** — um assistente de IA que conhece
> profundamente aquele produto específico e responde dúvidas de suporte
> citando as fontes da documentação oficial.

Este projeto está em fase de **Prova de Conceito (PoC) / MVP inicial**.
A ideia central: ISVs (fabricantes de software) enviam sua documentação
(manuais, FAQs), e a plataforma gera automaticamente um chat especializado
que pode ser embedado em qualquer site com uma única tag.

---

## Status atual

Schema multi-tenant (PostgreSQL + pgvector)
Knowledge Engine — ingestão de documentos Markdown, chunking e embeddings
Copilot Runtime — API de chat com RAG (busca semântica + LLM)
Widget embedável (`<assistant-ai>`) — Web Component standalone
Demo funcional: **MedSys ERP Hospitalar** (documentação fictícia)

Em andamento: Management Portal, segunda demo (ERP Jurídico)

---

## Arquitetura (visão geral)

```
┌─────────────────────────────────────────┐
│  Widget (<assistant-ai>)                 │
│  apps/widget — Web Component, ~8KB       │
└──────────────────┬────────────────────────┘
                    │ POST /api/chat
┌──────────────────▼────────────────────────┐
│  Copilot Runtime (API)                     │
│  apps/api — Next.js API Routes             │
│  - Busca semântica (pgvector)              │
│  - Monta prompt especializado              │
│  - Chama OpenAI                            │
└──────────────────┬────────────────────────┘
                    │
┌──────────────────▼────────────────────────┐
│  PostgreSQL + pgvector                     │
│  Multi-tenant: organizacoes > projetos     │
│  > documentos > chunks (embeddings)        │
│  > conversas > mensagens                   │
└──────────────────▲────────────────────────┘
                    │
┌──────────────────┴────────────────────────┐
│  Knowledge Engine (ingestão)               │
│  packages/core/ingest.js                   │
│  - Lê arquivos .md                         │
│  - Divide em chunks                        │
│  - Gera embeddings (OpenAI)                │
│  - Insere no banco                         │
└─────────────────────────────────────────────┘
```

---

## Estrutura do repositório

```
supportai/
├── docker-compose.yml          # Postgres + pgvector
├── sql/01_schema.sql            # Schema multi-tenant
├── packages/core/                # Knowledge Engine + RAG
│   ├── ingest.js                 # Script de ingestão de documentos
│   ├── search.js                 # Teste de busca via CLI
│   └── rag.js                    # Lógica RAG compartilhada
├── apps/
│   ├── api/                       # Copilot Runtime (Next.js)
│   │   └── pages/api/
│   │       ├── chat.js             # Endpoint principal
│   │       └── health.js
│   └── widget/                    # Widget embedável
│       ├── src/widget.js           # Código-fonte (Web Component)
│       ├── build.js                # Build (esbuild)
│       └── demo.html               # Página de demonstração
└── demo/
    └── docs-erp-hospitalar/       # Documentação fictícia (demo)
```

---

## Como rodar localmente

### Pré-requisitos

- Node.js 20+
- Docker + Docker Compose
- Conta na OpenAI com billing ativo ([platform.openai.com](https://platform.openai.com))

### 1. Subir o banco de dados

```bash
docker compose up -d
```

Isso sobe um PostgreSQL com a extensão `pgvector` já configurada e o
schema (`sql/01_schema.sql`) aplicado automaticamente.

### 2. Configurar variáveis de ambiente

Existem dois `.env` separados (cada parte do projeto lê o seu):

```bash
# Knowledge Engine
cp .env.example packages/core/.env

# Copilot Runtime (API)
cp apps/api/.env.example apps/api/.env.local
```

Edite os dois arquivos e preencha `OPENAI_API_KEY` com sua chave real.
`DATABASE_URL` já vem correto para o ambiente Docker padrão.

> Nunca commite arquivos `.env` ou `.env.local` — eles já estão no
> `.gitignore`.

#### Testando sem custo de API (modo mock)

Se você não tem (ou ainda não configurou) billing na OpenAI, defina em
ambos os `.env`:

```
AI_PROVIDER=mock
```

Nesse modo, embeddings são gerados localmente (feature hashing) e as
respostas são simuladas, mostrando os trechos recuperados pela busca
vetorial. Isso valida todo o pipeline (ingestão, banco, API, widget)
**sem nenhuma chamada externa**. A qualidade semântica da busca e das
respostas é limitada — para uma demo real, use `AI_PROVIDER=openai`.

### 3. Processar a documentação de demo (ingestão)

```bash
cd packages/core
npm install
node ingest.js erp-hospitalar ../../demo/docs-erp-hospitalar
```

Isso lê os arquivos `.md` de `demo/docs-erp-hospitalar`, gera os embeddings
e popula o banco. Você verá o progresso de cada chunk no terminal.

### 4. Testar via linha de comando (opcional)

```bash
node search.js erp-hospitalar "se o paciente faltar 3 vezes em 90 dias, ele fica bloqueado de agendar?"
```

### 5. Subir a API (Copilot Runtime)

```bash
cd apps/api
npm install
npm run dev
```

API disponível em `http://localhost:3001`.

### 6. Buildar e testar o widget

```bash
cd apps/widget
npm install
npm run build
npx serve .
```

Abra a URL indicada pelo `serve` (ex: `http://localhost:3000`) e acesse
`demo.html`. O widget aparecerá no canto inferior direito da página.

---

## Como embedar o widget em outro site

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
| `color` | Não | Cor de destaque do widget |
| `greeting` | Não | Mensagem inicial do assistente |

---

## Filosofia do projeto

- **A IA não acessa banco de dados de produção de terceiros.** Conhecimento
  vem de documentação fornecida pelo ISV (e, futuramente, de
  Swagger/OpenAPI e ferramentas/APIs autorizadas).
- **Multi-tenant desde o início** — cada "projeto" é um especialista
  isolado, identificado por `projeto_id` em todas as tabelas relevantes.
- **Simplicidade operacional** — stack mínimo necessário (Next.js,
  PostgreSQL + pgvector, OpenAI), sem infraestrutura extra prematura.
- **Open core** — o núcleo (RAG, widget) é aberto; o Management Portal e
  funcionalidades avançadas de runtime serão o produto comercial futuro.

---

## Roadmap

| Fase | Objetivo |
|---|---|
| **1 — Atual** | Documentação + FAQ + Chat (RAG básico + widget) |
| 2 | Ingestão de Swagger/OpenAPI |
| 3 | Tools Runtime — consulta de dados reais via ferramentas |
| 4 | Action Runtime — execução de ações dentro do software |
| 5 | Copilot Especializado — especialista como operador do sistema |
| 6 | White Label Platform — distribuição em escala |

---

## Contribuindo

Este projeto está em estágio inicial e contribuições são bem-vindas.
Issues e PRs podem ser abertos diretamente no repositório.

## Licença

A definir.
