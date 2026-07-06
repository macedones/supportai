from pathlib import Path

from openapi_parser import carregar_spec, gerar_blocos

from .base import DocumentoExtraido, SourceProvider


class OpenAPIProvider(SourceProvider):
    """
    Le uma spec Swagger 2.0 / OpenAPI 3.x (.json, .yaml, .yml) e gera
    um documento com um bloco por endpoint e por schema. Ver
    openapi_parser.py para os detalhes do parsing.
    """

    tipo = "openapi"
    nome = "openapi"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        caminho = Path(origem).resolve()

        if not caminho.exists():
            raise FileNotFoundError(f"Spec nao encontrada: {caminho}")
        if caminho.suffix.lower() not in (".json", ".yaml", ".yml"):
            raise ValueError("Formato nao suportado. Use um arquivo .json, .yaml ou .yml.")

        spec = carregar_spec(caminho)
        blocos = gerar_blocos(spec)

        return [DocumentoExtraido(nome_arquivo=caminho.name, blocos=blocos)]
