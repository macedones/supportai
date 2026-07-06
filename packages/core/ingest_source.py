# ============================================================
# CLI generica de ingestao — funciona com QUALQUER SourceProvider
# registrado em providers/__init__.py. E' o ponto de entrada unico
# para os conectores novos (pdf, html, git, ...).
#
# ingest.py e ingest_openapi.py continuam existindo como atalhos de
# compatibilidade (mesma linha de comando de sempre), mas por baixo
# rodam exatamente este mesmo pipeline generico.
#
# Uso:
#   python ingest_source.py <provider> <slug-do-projeto> <origem>
#   python ingest_source.py --list
#
# Exemplos:
#   python ingest_source.py md erp-hospitalar ../../demo/docs-erp-hospitalar
#   python ingest_source.py openapi medsys-api ../../demo/openapi-erp-hospitalar/openapi.yaml
#   python ingest_source.py pdf minha-doc ../../demo/manual.pdf
#   python ingest_source.py html minha-doc https://docs.exemplo.com/guia
#   python ingest_source.py git meu-projeto "https://github.com/org/repo#docs"
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
from providers import PROVIDERS


def _listar_providers() -> None:
    print("Providers disponiveis:\n")
    for chave, classe in PROVIDERS.items():
        primeira_linha = (classe.__doc__ or "").strip().splitlines()
        resumo = primeira_linha[0] if primeira_linha else ""
        print(f"  {chave:12s} tipo='{classe.tipo}'  {resumo}")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] in ("--list", "-l"):
        _listar_providers()
        return

    if len(sys.argv) != 4:
        print("Uso: python ingest_source.py <provider> <slug-do-projeto> <origem>")
        print("     python ingest_source.py --list")
        sys.exit(1)

    nome_provider, projeto_slug, origem = sys.argv[1], sys.argv[2], sys.argv[3]

    if nome_provider not in PROVIDERS:
        print(f'Provider "{nome_provider}" desconhecido.')
        print('Rode "python ingest_source.py --list" para ver as opcoes.')
        sys.exit(1)

    validar_ai_provider()

    provider = PROVIDERS[nome_provider]()

    print(f"Provider: {nome_provider} (tipo='{provider.tipo}')")
    print(f"Projeto: {projeto_slug}")
    print(f"Origem: {origem}")

    conexao = obter_conexao()

    try:
        org_id = obter_ou_criar_organizacao(conexao)
        conexao.commit()

        projeto_id = obter_ou_criar_projeto(conexao, org_id, projeto_slug)
        conexao.commit()

        processados = ingerir_via_provider(conexao, projeto_id, provider, origem)

        ativar_projeto(conexao, projeto_id)
        conexao.commit()

        print(f"\nIngestao concluida com sucesso. {len(processados)} documento(s) processado(s).")
        print(f"Projeto ID: {projeto_id}")
    finally:
        conexao.close()


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as erro:
        print(f"\nProvider ainda nao implementado: {erro}")
        sys.exit(1)
    except Exception as erro:
        print("\nErro durante a ingestao:")
        print(erro)
        sys.exit(1)
