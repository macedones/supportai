# ============================================================
# Copilot Runtime — Versao de linha de comando
#
# Wrapper fino sobre rag.py, util para testar o RAG rapidamente
# sem precisar subir a API.
#
# Como rodar:
#   python search.py <slug-do-projeto> "<pergunta>"
#
# Exemplo:
#   python search.py erp-hospitalar "como tratar uma glosa administrativa?"
# ============================================================

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from db import obter_conexao
from rag import responder_pergunta


def _validar_provider() -> None:
    ai_provider = os.environ.get("AI_PROVIDER", "openai")

    if ai_provider == "mock":
        print("AI_PROVIDER=mock — busca sem chamadas externas (resposta simulada).\n")
    elif ai_provider in ("groq", "ollama"):
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        print(f"AI_PROVIDER={ai_provider} — embeddings via Ollama ({ollama_url}).\n")
    elif ai_provider == "openai":
        chave = os.environ.get("OPENAI_API_KEY", "")
        if not chave or chave.startswith("sk-coloque"):
            print("ERRO: defina OPENAI_API_KEY no .env para usar AI_PROVIDER=openai.")
            print("Alternativa gratuita: AI_PROVIDER=groq (console.groq.com) ou AI_PROVIDER=ollama.")
            sys.exit(1)


def main() -> None:
    if len(sys.argv) != 3:
        print('Uso: python search.py <slug-do-projeto> "<pergunta>"')
        print('Exemplo: python search.py erp-hospitalar "como tratar uma glosa administrativa?"')
        sys.exit(1)

    projeto_slug, pergunta = sys.argv[1], sys.argv[2]

    _validar_provider()

    conexao = obter_conexao()

    try:
        with conexao.cursor() as cursor:
            cursor.execute(
                "SELECT id, nome, persona_tom FROM projetos WHERE slug = %s",
                (projeto_slug,),
            )
            projeto = cursor.fetchone()

        if not projeto:
            print(f'Projeto com slug "{projeto_slug}" nao encontrado. Rode o ingest.py primeiro.')
            sys.exit(1)

        print(f"\nProjeto: {projeto['nome']}")
        print(f"Pergunta: {pergunta}\n")

        resultado = responder_pergunta(conexao, projeto, pergunta)

        print("--- Fontes utilizadas ---")
        for i, fonte in enumerate(resultado["fontes"]):
            secao = f" > {fonte['secao']}" if fonte.get("secao") else ""
            print(f"[{i + 1}] {fonte['documento_nome']}{secao} (distancia: {fonte['distancia']})")
        print("-------------------------\n")

        print("--- Resposta do especialista ---")
        print(resultado["resposta"])
        print("---------------------------------")

        print(f"\n(tokens usados: {resultado['tokens_usados']})")
    finally:
        conexao.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print(f"\nErro: {erro}")
        sys.exit(1)
