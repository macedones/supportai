from pathlib import Path

from ingest_common import dividir_em_chunks, extrair_secao

from .base import DocumentoExtraido, SourceProvider


class MarkdownProvider(SourceProvider):
    """
    Le todos os arquivos .md de uma pasta. Cada arquivo ja e' dividido
    em chunks aqui (dividir_em_chunks) e a secao de cada chunk e'
    extraida do primeiro cabecalho Markdown encontrado nele
    (extrair_secao) — mesmo comportamento do ingest.py original.

    O pipeline generico (ingest_common.ingerir_via_provider) roda
    dividir_em_chunks() de novo sobre cada bloco, mas como o texto ja
    esta dentro do limite de tamanho isso e' um no-op — sem regressao
    em relacao ao fluxo anterior.
    """

    tipo = "md"
    nome = "md"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        pasta = Path(origem).resolve()

        if not pasta.is_dir():
            raise NotADirectoryError(f"Pasta nao encontrada: {pasta}")

        arquivos = sorted(pasta.glob("*.md"))
        if not arquivos:
            raise FileNotFoundError(f"Nenhum arquivo .md encontrado em {pasta}")

        documentos = []
        for arquivo in arquivos:
            conteudo = arquivo.read_text(encoding="utf-8")
            pedacos = dividir_em_chunks(conteudo)
            blocos = [(extrair_secao(pedaco), pedaco) for pedaco in pedacos]
            documentos.append(DocumentoExtraido(nome_arquivo=arquivo.name, blocos=blocos))

        return documentos
