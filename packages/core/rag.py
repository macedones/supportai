# ============================================================
# Copilot Runtime — Logica central do RAG (reutilizavel)
#
# Equivalente as secoes "CHAT / GERACAO DE RESPOSTA" e
# "PIPELINE COMPLETO" do rag.js original.
#
# PROVEDOR DE IA (AI_PROVIDER):
#   "openai"  — OpenAI API (embeddings + chat). Requer billing.
#   "groq"    — Groq API (chat gratuito) + Ollama (embeddings locais).
#   "ollama"  — Tudo local via Ollama. Zero custo.
#   "mock"    — Nenhuma chamada externa. Util para CI e onboarding.
# ============================================================

import os

import requests

from embeddings import gerar_embedding

TOP_K = 4

AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai")

CHAT_MODELS = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.1-8b-instant",
    "ollama": "llama3.2",
}


def _ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def montar_system_prompt(nome_projeto: str, persona_tom: str, contexto: str) -> str:
    """Equivalente a montarSystemPrompt() do rag.js."""
    tons = {
        "tecnico_e_direto": "tecnico, direto e objetivo, sem rodeios",
        "amigavel_e_didatico": "amigavel, didatico, explicando com calma",
    }
    tom_descricao = tons.get(persona_tom, "profissional e prestativo")

    return f"""Voce e o especialista virtual do sistema "{nome_projeto}".

Seu tom de comunicacao deve ser {tom_descricao}.

Responda SOMENTE com base no CONTEXTO fornecido abaixo, que foi extraido
da documentacao oficial do sistema. Se a resposta nao estiver no contexto,
diga claramente que nao encontrou essa informacao na documentacao
disponivel — NAO invente informacoes.

Sempre que possivel, cite o nome do documento e a secao de onde veio
a informacao usada na resposta.

CONTEXTO:
{contexto}"""


# ------------------------------------------------------------
# chamar_llm: abstrai a chamada ao modelo de chat.
#
# OpenAI, Groq e Ollama (via /v1) expõem a mesma interface REST
# de "chat completions", então usamos uma única função interna
# trocando apenas a URL base e a chave de API.
# ------------------------------------------------------------
def _chat_completions(base_url: str, api_key: str, model: str, system_prompt: str, pergunta: str) -> dict:
    resposta = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    resposta.raise_for_status()
    dados = resposta.json()
    return {
        "texto": dados["choices"][0]["message"]["content"],
        "tokens": dados.get("usage", {}).get("total_tokens", 0),
    }


def chamar_llm(system_prompt: str, pergunta: str) -> dict:
    if AI_PROVIDER == "groq":
        return _chat_completions(
            "https://api.groq.com/openai/v1",
            os.environ.get("GROQ_API_KEY", ""),
            CHAT_MODELS["groq"],
            system_prompt,
            pergunta,
        )

    if AI_PROVIDER == "ollama":
        return _chat_completions(
            f"{_ollama_url()}/v1",
            "ollama",  # valor exigido pela chamada, ignorado pelo Ollama
            CHAT_MODELS["ollama"],
            system_prompt,
            pergunta,
        )

    # openai (padrão)
    return _chat_completions(
        "https://api.openai.com/v1",
        os.environ.get("OPENAI_API_KEY", ""),
        CHAT_MODELS["openai"],
        system_prompt,
        pergunta,
    )


def _montar_resposta_mock(pergunta: str, chunks: list) -> str:
    trechos = []
    for i, row in enumerate(chunks):
        meta = row["metadados"]
        resumo = " ".join(row["conteudo"][:220].split())
        origem = f"{meta['documento_nome']} > {meta['secao']}" if meta.get("secao") else meta["documento_nome"]
        trechos.append(f"[Trecho {i + 1} - {origem}]\n{resumo}...")

    trechos_texto = "\n\n".join(trechos)

    return f"""[MODO MOCK - nenhuma chamada externa foi feita]

Pergunta: "{pergunta}"

Trechos recuperados (busca por sobreposicao de palavras):

{trechos_texto}

---
Para respostas reais: defina AI_PROVIDER=groq, ollama ou openai no .env."""


# ============================================================
# PIPELINE COMPLETO
# ============================================================

def buscar_chunks_relevantes(conexao, projeto_id: str, pergunta: str) -> list:
    """Equivalente a buscarChunksRelevantes() do rag.js."""
    embedding_pergunta = gerar_embedding(pergunta)
    vetor_textual = f"[{','.join(str(v) for v in embedding_pergunta)}]"

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.conteudo, c.metadados, (c.embedding <=> %s) AS distancia
            FROM chunks c
            WHERE c.projeto_id = %s
            ORDER BY c.embedding <=> %s
            LIMIT %s
            """,
            (vetor_textual, projeto_id, vetor_textual, TOP_K),
        )
        return cursor.fetchall()


def responder_pergunta(conexao, projeto: dict, pergunta: str) -> dict:
    """Equivalente a responderPergunta() do rag.js."""
    chunks = buscar_chunks_relevantes(conexao, projeto["id"], pergunta)

    if not chunks:
        return {
            "resposta": "Nenhum documento foi processado para este projeto.",
            "fontes": [],
            "tokens_usados": 0,
        }

    fontes = [
        {
            "documento_nome": row["metadados"]["documento_nome"],
            "secao": row["metadados"].get("secao"),
            "distancia": round(float(row["distancia"]), 4),
        }
        for row in chunks
    ]

    if AI_PROVIDER == "mock":
        return {
            "resposta": _montar_resposta_mock(pergunta, chunks),
            "fontes": fontes,
            "tokens_usados": 0,
        }

    contexto = "\n\n---\n\n".join(
        f"[Trecho {i + 1} - {row['metadados']['documento_nome']}]\n{row['conteudo']}"
        for i, row in enumerate(chunks)
    )

    system_prompt = montar_system_prompt(
        nome_projeto=projeto["nome"],
        persona_tom=projeto["persona_tom"],
        contexto=contexto,
    )

    resultado_llm = chamar_llm(system_prompt, pergunta)

    return {
        "resposta": resultado_llm["texto"],
        "fontes": fontes,
        "tokens_usados": resultado_llm["tokens"],
    }
