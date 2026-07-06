# ============================================================
# CLI de compatibilidade: ingestao de Swagger/OpenAPI.
#
# O parsing de verdade vive em openapi_parser.py (funcao pura,
# sem banco). Este script e' so' a "cola" que conecta o
# OpenAPIProvider (arquitetura de conectores, ver providers/) ao
# banco, preservando exatamente a mesma linha de comando de antes:
#
#   python ingest_openapi.py <slug-do-projeto> <caminho-do-spec>
#
# Para as fontes novas (PDF, HTML, Git, ...) use ingest_source.py,
# que e' generico pra qualquer provider registrado.
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
from providers import OpenAPIProvider


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python ingest_openapi.py <slug-do-projeto> <caminho-do-spec.json|.yaml>")
        print("Exemplo: python ingest_openapi.py minha-api ../../demo/openapi-erp-hospitalar/openapi.yaml")
        sys.exit(1)

    projeto_slug, caminho_spec = sys.argv[1], sys.argv[2]

    validar_ai_provider()

    print(f"Projeto: {projeto_slug}")
    print(f"Spec: {caminho_spec}")

    conexao = obter_conexao()

    try:
        org_id = obter_ou_criar_organizacao(conexao)
        conexao.commit()

        projeto_id = obter_ou_criar_projeto(conexao, org_id, projeto_slug)
        conexao.commit()

        ingerir_via_provider(conexao, projeto_id, OpenAPIProvider(), caminho_spec)

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
