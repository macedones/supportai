# SupportAI

Plataforma open source para transformar documentação de software em um assistente de suporte embedável. ISVs fornecem seus manuais e FAQs; a plataforma gera um chat especializado que responde com base exclusivamente nesses documentos, citando a fonte de cada informação.

O assistente não usa o conhecimento geral do LLM, responde apenas com o que foi ingerido. Isso diferencia um especialista virtual de um chatbot genérico.

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
| Copilot Runtime — API de chat com RAG (FastAPI) | Pronto |
| Widget embedável `<assistant-ai>` — Web Component | Pronto |
| Multi-provider (Groq, Ollama, OpenAI, Mock) | Pronto |
| Demo: MedSys ERP Hospitalar | Funcional |
| Management Portal | Em andamento |
| Demo: ERP Jurídico | Em andamento |
| Ingestão de Swagger/OpenAPI | Fase 2 |

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
│  apps/api — FastAPI, porta 3001           │
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
│  packages/core/ingest.py                  │
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
│   ├── db.py                    # Conexão com o Postgres
│   ├── embeddings.py            # Geração de embeddings multi-provider
│   ├── rag.py                   # Lógica RAG (busca + chat com LLM)
│   ├── ingest.py                # Ingestão de documentos
│   └── search.py                # Teste de busca via CLI
├── apps/
│   ├── api/                     # Copilot Runtime (FastAPI, porta 3001)
│   │   ├── main.py               # App FastAPI, CORS, rotas
│   │   ├── database.py           # Dependency de conexão com o banco
│   │   ├── models.py             # Schemas Pydantic
│   │   ├── rag_service.py        # Orquestra conversa + RAG
│   │   └── routers/
│   │       ├── chat.py
│   │       ├── feedback.py
│   │       ├── health.py
│   │       └── metrics.py
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

- Python 3.11+
- Node.js 20+ (apenas para o widget, que roda no navegador)
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

### 3. Criar o ambiente virtual e instalar dependências

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r packages/core/requirements.txt
pip install -r apps/api/requirements.txt
```

### 4. Configurar variáveis de ambiente

```bash
cp .env.example packages/core/.env
cp .env.example apps/api/.env
```

Preencha `GROQ_API_KEY` nos dois arquivos. Chave gratuita em [console.groq.com](https://console.groq.com).

Não commite arquivos `.env` — já estão no `.gitignore`.

### 5. Ingerir a documentação de demo

```bash
cd packages/core
python ingest.py erp-hospitalar ../../demo/docs-erp-hospitalar
```

### 6. Testar via CLI (opcional)

```bash
python search.py erp-hospitalar "o que é uma glosa técnica?"
```

### 7. Subir a API

```bash
cd apps/api
uvicorn main:app --reload --port 3001
# http://localhost:3001
# Documentação interativa: http://localhost:3001/docs
```

### 8. Buildar e testar o widget

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

**Widget desacoplado do backend.** O widget (`apps/widget`) é um Web Component em JavaScript puro, já que precisa rodar no navegador do site do ISV — o restante da plataforma (Knowledge Engine e API) é 100% Python.

---

## Roadmap

| Fase | Objetivo |
|---|---|
| 1 — Concluída | Documentação + FAQ + Chat (RAG + widget multi-provider) |
| 2 | Ingestão de Swagger/OpenAPI |
| 3 | Tools Runtime — consulta de dados reais via ferramentas |
| 4 | Action Runtime — execução de ações dentro do software |
| 5 | Copilot Especializado — especialista como operador do sistema |
| 6 | White Label Platform |

---

## Contribuindo

Projeto em estágio inicial. Issues e PRs são bem-vindos.

## Licença

A definir.
