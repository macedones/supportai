# ============================================================
# Embeddings — geracao de vetores a partir de texto.
#
# Equivalente a secao "EMBEDDINGS" do rag.js original.
# Suporta os mesmos AI_PROVIDER: openai, groq (usa Ollama pra
# embeddings, pois Groq nao oferece), ollama e mock.
# ============================================================

import hashlib
import os
import unicodedata

import requests

EMBEDDING_DIMENSIONS = 1536

# nomic-embed-text (usado por ollama/groq) gera 768 dimensoes.
# O schema usa VECTOR(1536), entao completamos com zeros (padding)
# para manter compatibilidade — os zeros extras nao afetam a
# distancia de cosseno calculada pelo pgvector.
OLLAMA_EMBED_DIMENSIONS = 768

EMBED_MODELS = {
    "openai": "text-embedding-3-small",
    "groq": "nomic-embed-text",
    "ollama": "nomic-embed-text",
}


def _ai_provider() -> str:
    return os.environ.get("AI_PROVIDER", "openai")


def _ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


# ------------------------------------------------------------
# Embedding via Ollama (usado pelos providers "ollama" e "groq").
#
# Equivalente a gerarEmbeddingOllama() do rag.js. Usamos a lib
# "requests" no lugar do http/https nativo do Node — em Python
# nao ha motivo pra usar sockets na mao quando requests resolve
# isso com uma chamada so.
# ------------------------------------------------------------
def gerar_embedding_ollama(texto: str) -> list[float]:
    url = f"{_ollama_url()}/api/embeddings"

    resposta = requests.post(
        url,
        json={"model": EMBED_MODELS["ollama"], "prompt": texto},
        timeout=60,
    )
    resposta.raise_for_status()
    dados = resposta.json()

    vetor = dados.get("embedding")
    if not isinstance(vetor, list):
        raise RuntimeError(f"Ollama nao retornou embedding. Resposta: {dados}")

    # Padding: completa com zeros até 1536 (nomic-embed-text gera 768)
    vetor = list(vetor)
    while len(vetor) < EMBEDDING_DIMENSIONS:
        vetor.append(0.0)
    return vetor


# ------------------------------------------------------------
# Hash simples (djb2) — usado apenas pelo modo mock.
# Mantido idêntico ao do JS para gerar os mesmos vetores.
# ------------------------------------------------------------
def _hash_djb2(texto: str) -> int:
    hash_valor = 5381
    for caractere in texto:
        hash_valor = (hash_valor * 33) ^ ord(caractere)
    return hash_valor & 0xFFFFFFFF


def gerar_embedding_mock(texto: str) -> list[float]:
    vetor = [0.0] * EMBEDDING_DIMENSIONS

    # Normaliza acentos (NFD) e extrai só letras/números, igual ao JS.
    texto_normalizado = unicodedata.normalize("NFD", texto.lower())
    texto_sem_acento = "".join(
        c for c in texto_normalizado if unicodedata.category(c) != "Mn"
    )
    palavras = [p for p in texto_sem_acento.split() if p.isalnum()]

    for palavra in palavras:
        h = _hash_djb2(palavra)
        indice = h % EMBEDDING_DIMENSIONS
        sinal = 1 if (h & 0x10000) else -1
        vetor[indice] += sinal

    norma = sum(v * v for v in vetor) ** 0.5 or 1.0
    return [v / norma for v in vetor]


# ------------------------------------------------------------
# gerar_embedding: roteador central de embeddings, equivalente
# ao gerarEmbedding() do rag.js.
# ------------------------------------------------------------
def gerar_embedding(texto: str) -> list[float]:
    provider = _ai_provider()

    if provider == "mock":
        return gerar_embedding_mock(texto)

    if provider in ("ollama", "groq"):
        return gerar_embedding_ollama(texto)

    # openai (padrão)
    api_key = os.environ.get("OPENAI_API_KEY")
    resposta = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": EMBED_MODELS["openai"], "input": texto},
        timeout=60,
    )
    resposta.raise_for_status()
    return resposta.json()["data"][0]["embedding"]
