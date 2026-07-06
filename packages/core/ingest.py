# ============================================================
# CLI de compatibilidade: ingestao de documentacao .md.
#
# O parsing de verdade vive em providers/markdown_provider.py. Este
# script e' so' a "cola" que conecta o MarkdownProvider (arquitetura
# de conectores, ver providers/) ao banco, preservando exatamente a
# mesma linha de comando de antes:
#
#   python ingest.py <slug-do-projeto> <pasta-com-os-md>
#
# Para as fontes novas (PDF, HTML, Git, OpenAPI...) use
# ingest_source.py, que e' generico pra qualquer provider registrado.
# ============================================================

import sys

from dotenv import load_dotenv

load_dotenv()

from db import obter_conexao
from ingest_common import (
    ativar_projeto,
    ingerir_via_provider,
    obter_ou_criar_organizacao,
    obter_ou_criar_projeto,
    validar_ai_provider,
)
from providers import MarkdownProvider


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python ingest.py <slug-do-projeto> <pasta-com-os-md>")
        print("Exemplo: python ingest.py erp-hospitalar ../../demo/docs-erp-hospitalar")
        sys.exit(1)

    projeto_slug, pasta_documentos = sys.argv[1], sys.argv[2]

    validar_ai_provider()

    print(f"Projeto: {projeto_slug}")
    print(f"Pasta: {pasta_documentos}")

    conexao = obter_conexao()

    try:
        org_id = obter_ou_criar_organizacao(conexao)
        conexao.commit()

        projeto_id = obter_ou_criar_projeto(conexao, org_id, projeto_slug)
        conexao.commit()

        ingerir_via_provider(conexao, projeto_id, MarkdownProvider(), pasta_documentos)

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
