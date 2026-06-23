# SupportAI — Assistant AI Platform

> Plataforma open source que transforma a documentação de um software em um
> **especialista virtual embedável** — um assistente de IA que conhece
> profundamente aquele produto específico e responde dúvidas de suporte
> citando as fontes da documentação oficial.

A ideia central: ISVs (fabricantes de software) enviam sua documentação
(manuais, FAQs), e a plataforma gera automaticamente um chat especializado
que pode ser embedado em qualquer site com uma única tag — sem alterar
profundamente o software existente.

---

## Como funciona

Um usuário pergunta ao assistente algo específico do sistema que usa.
A IA busca nos documentos ingeridos, monta o contexto e responde como
um especialista daquele produto — citando a fonte exata.

**Exemplo real testado:**

> "O que é uma glosa técnica e qual o prazo para recurso?"

Resposta gerada (Groq + Llama 3.1, zero custo):
> *"Uma glosa técnica é a recusa de pagamento por parte da operadora de saúde,
> geralmente por questionamento sobre a pertinência clínica do procedimento.
> O prazo para recurso varia por operadora, geralmente entre 30 e 90 dias corridos
> a partir do recebimento do demonstrativo.
> (manual-modulo-faturamento.md, seção "Tipos de Glosa")"*

Essa resposta não vem do conhecimento geral do LLM — vem exclusivamente
dos documentos que o ISV forneceu. É isso que diferencia um especialista
virtual de um chatbot genérico.

---

## Status atual

| Componente | Status |
|---|---|
| Schema multi-tenant (PostgreSQL + pgvector) | ✅ Pronto |
| Knowledge Engine — ingestão de MD, chunking, embeddings | ✅ Pronto |
| Copilot Runtime — API de chat com RAG | ✅ Pronto |
| Widget embedável `<assistant-ai>` — Web Component | ✅ Pronto |
| Multi-provider (Groq, Ollama, OpenAI, Mock) | ✅ Pronto |
| Demo: MedSys ERP Hospitalar | ✅ Funcional |
| Management Portal | 🔲 Em andamento |
| Demo: ERP Jurídico | 🔲 Em andamento |
| Ingestão de Swagger/OpenAPI (Python) | 🔲 Fase 2 |

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

## Como rodar localmente

### Pré-requisitos

- Node.js 20+
- Docker + Docker Compose
- Um provedor de IA (veja abaixo — recomendamos Groq + Ollama, ambos gratuitos)

### Provedores de IA suportados

| `AI_PROVIDER` | Chat | Embeddings | Custo | Requisito |
|---|---|---|---|---|
| `groq` ✅ **recomendado** | Groq API — Llama 3.1 8B | Ollama local | Gratuito | Conta em [console.groq.com](https://console.groq.com) + Ollama |
| `ollama` | Ollama local — Llama 3.2 | Ollama local | Zero | Ollama instalado |
| `openai` | GPT-4o mini | text-embedding-3-small | Pago | Billing ativo |
| `mock` | Simulado (trechos brutos) | Feature hashing | Zero | Nada |

### 1. Subir o banco de dados

```bash
docker compose up -d
```

Sobe PostgreSQL com pgvector. O schema é aplicado automaticamente
a partir de `sql/01_schema.sql`.

### 2. Instalar Ollama e baixar os modelos

Acesse [ollama.com](https://ollama.com), instale, e rode:

```bash
ollama pull nomic-embed-text   # embeddings (~270MB)
ollama pull llama3.2            # chat local, opcional se usar groq (~2GB)
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example packages/core/.env
cp apps/api/.env.example apps/api/.env.local
```

Edite os dois arquivos e preencha sua `GROQ_API_KEY`
(gratuita em [console.groq.com](https://console.groq.com)).

O `.env.example` documenta todas as opções disponíveis.

> ⚠️ Nunca commite `.env` ou `.env.local` — já estão no `.gitignore`.

### 4. Processar a documentação de demo

```bash
cd packages/core
npm install
node ingest.js erp-hospitalar ../../demo/docs-erp-hospitalar
```

### 5. Testar via linha de comando (opcional)

```bash
node search.js erp-hospitalar "o que é uma glosa técnica?"
```

### 6. Subir a API

```bash
cd apps/api
npm install
npm run dev
# API disponível em http://localhost:3001
```

### 7. Buildar e testar o widget

```bash
cd apps/widget
npm install
npm run build
npx serve .
# Abra o demo.html na URL indicada
```

O widget aparece no canto inferior direito. Experimente perguntar:

- *"Se o paciente faltar 3 vezes em 90 dias, ele fica bloqueado de agendar?"*
- *"O que é uma glosa técnica e qual o prazo para recurso?"*
- *"Como desbloquear um usuário após tentativas de login incorretas?"*

---

## Como embedar em outro site

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

## Filosofia do projeto

**Especialista, não chatbot.** A IA responde com base exclusivamente nos
documentos fornecidos pelo ISV, citando a fonte de cada informação.
Não inventa, não generaliza além do que foi ingerido.

**Multi-tenant desde o início.** Cada "projeto" é um especialista isolado.
Um ISV pode ter múltiplos projetos (ex: ERP Hospitalar e ERP Jurídico)
sob a mesma conta, sem vazamento de contexto entre eles.

**IA não acessa banco de produção de terceiros.** O conhecimento vem de
documentação fornecida pelo ISV. Acesso a dados reais (via Tools/Actions)
é funcionalidade avançada de fases futuras, com controle explícito do ISV.

**Open core.** O núcleo (RAG, widget, demos) é aberto. O Management Portal
e funcionalidades enterprise serão o produto comercial futuro.

**Zero lock-in de provedor de IA.** Suporte nativo a Groq, Ollama, OpenAI
e modo mock — configurável por variável de ambiente, sem mudança de código.

---

## Roadmap

| Fase | Objetivo | Linguagem |
|---|---|---|
| **1 — Concluída** | Documentação + FAQ + Chat (RAG + widget multi-provider) | JavaScript |
| 2 | Ingestão de Swagger/OpenAPI | **Python** |
| 3 | Tools Runtime — consulta de dados reais via ferramentas | **Python** |
| 4 | Action Runtime — execução de ações dentro do software | **Python** |
| 5 | Copilot Especializado — especialista como operador do sistema | **Python** |
| 6 | White Label Platform — distribuição em escala | — |

---

## Contribuindo

Projeto em estágio inicial. Contribuições são bem-vindas.
Issues e PRs podem ser abertos diretamente no repositório.

Quer contribuir mas não sabe por onde começar? Veja as issues abertas
ou rode a demo localmente e compartilhe seu feedback.

## Licença

A definir.
