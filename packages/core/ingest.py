# ============================================================
# Knowledge Engine — Script de Ingestao (.md)
#
# O que este script faz:
# 1. Le todos os arquivos .md de uma pasta de demo (ex: demo/docs-erp-hospitalar)
# 2. Cria (ou reaproveita) um registro em "projetos" para esse persona
# 3. Para cada arquivo .md:
#    - Cria um registro em "documentos"
#    - Divide o conteudo em chunks (pedacos de texto)
#    - Gera o embedding de cada chunk
#    - Insere os chunks na tabela "chunks"
#
# Como rodar:
#   python ingest.py <slug-do-projeto> <pasta-com-os-md>
#
# Exemplo:
#   python ingest.py erp-hospitalar ../../demo/docs-erp-hospitalar
#
# Para ingerir specs Swagger/OpenAPI, veja ingest_openapi.py.
# ============================================================

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from db import obter_conexao
from ingest_common import (
    ativar_projeto,
    dividir_em_chunks,
    extrair_secao,
    finalizar_documento,
    inserir_chunks_no_documento,
    obter_ou_criar_documento,
    obter_ou_criar_organizacao,
    obter_ou_criar_projeto,
)


def ingerir_documento(conexao, projeto_id: str, caminho_arquivo: Path) -> None:
    nome_arquivo = caminho_arquivo.name
    print(f"\nProcessando: {nome_arquivo}")

    conteudo = caminho_arquivo.read_text(encoding="utf-8")
    textos_chunks = dividir_em_chunks(conteudo)
    print(f"  -> {len(textos_chunks)} chunk(s) gerado(s)")

    chunks = [(texto, extrair_secao(texto)) for texto in textos_chunks]

    documento_id = obter_ou_criar_documento(conexao, projeto_id, nome_arquivo, tipo="md")
    inserir_chunks_no_documento(conexao, documento_id, projeto_id, nome_arquivo, chunks)
    finalizar_documento(conexao, documento_id, len(chunks))

    conexao.commit()
    print(f"  -> documento \"{nome_arquivo}\" concluido ({len(chunks)} chunks)")


def _validar_provider() -> None:
    ai_provider = os.environ.get("AI_PROVIDER", "openai")

    if ai_provider == "mock":
        print("AI_PROVIDER=mock — ingestao sem chamadas externas (embeddings via feature hashing).")
    elif ai_provider in ("groq", "ollama"):
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        print(f"AI_PROVIDER={ai_provider} — embeddings via Ollama ({ollama_url}).")
        if ai_provider == "groq" and not os.environ.get("GROQ_API_KEY"):
            print("ERRO: defina GROQ_API_KEY no .env para usar AI_PROVIDER=groq.")
            sys.exit(1)
    elif ai_provider == "openai":
        chave = os.environ.get("OPENAI_API_KEY", "")
        if not chave or chave.startswith("sk-coloque"):
            print("ERRO: defina OPENAI_API_KEY no .env para usar AI_PROVIDER=openai.")
            print("Alternativa gratuita: AI_PROVIDER=groq (console.groq.com) ou AI_PROVIDER=ollama.")
            sys.exit(1)


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python ingest.py <slug-do-projeto> <pasta-com-os-md>")
        print("Exemplo: python ingest.py erp-hospitalar ../../demo/docs-erp-hospitalar")
        sys.exit(1)

    projeto_slug, pasta_documentos = sys.argv[1], sys.argv[2]

    _validar_provider()

    pasta_absoluta = Path(pasta_documentos).resolve()
    arquivos = sorted(p for p in pasta_absoluta.glob("*.md"))

    if not arquivos:
        print(f"Nenhum arquivo .md encontrado em {pasta_absoluta}")
        sys.exit(1)

    print(f"Projeto: {projeto_slug}")
    print(f"Pasta: {pasta_absoluta}")
    print(f"Arquivos encontrados: {', '.join(a.name for a in arquivos)}")

    conexao = obter_conexao()

    try:
        org_id = obter_ou_criar_organizacao(conexao)
        conexao.commit()

        projeto_id = obter_ou_criar_projeto(conexao, org_id, projeto_slug)
        conexao.commit()

        for arquivo in arquivos:
            ingerir_documento(conexao, projeto_id, arquivo)

        ativar_projeto(conexao, projeto_id)
        conexao.commit()

        print("\nIngestao concluida com sucesso.")
        print(f"Projeto ID: {projeto_id}")
    finally:
        conexao.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print("\nErro durante a ingestao:")
        print(erro)
        sys.exit(1)
