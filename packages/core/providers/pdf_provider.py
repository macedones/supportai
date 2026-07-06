from pathlib import Path

from pypdf import PdfReader

from .base import DocumentoExtraido, SourceProvider


class PDFProvider(SourceProvider):
    """
    Extrai texto de arquivos PDF — um arquivo, ou todos os .pdf de
    uma pasta. Cada PDF vira 1 documento; cada pagina vira 1 bloco
    (secao = "Pagina N"), preservando a localizacao original para
    quem for auditar a fonte citada numa resposta depois.

    Limitacao conhecida: extrai apenas texto selecionavel (camada de
    texto do PDF). PDFs escaneados como imagem pura retornam paginas
    vazias e sao ignorados com um aviso — OCR fica fora do escopo
    desta primeira versao.
    """

    tipo = "pdf"
    nome = "pdf"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        caminho = Path(origem).resolve()

        if caminho.is_dir():
            arquivos = sorted(caminho.glob("*.pdf"))
        elif caminho.is_file():
            arquivos = [caminho]
        else:
            raise FileNotFoundError(f"Nao encontrado: {caminho}")

        if not arquivos:
            raise FileNotFoundError(f"Nenhum .pdf encontrado em {caminho}")

        documentos = []
        for arquivo in arquivos:
            leitor = PdfReader(str(arquivo))
            blocos: list[tuple[str | None, str]] = []

            for i, pagina in enumerate(leitor.pages, start=1):
                texto = (pagina.extract_text() or "").strip()
                if texto:
                    blocos.append((f"Pagina {i}", texto))

            if not blocos:
                print(f"  aviso: nenhum texto extraido de {arquivo.name} (PDF escaneado sem OCR?)")
                continue

            documentos.append(DocumentoExtraido(nome_arquivo=arquivo.name, blocos=blocos))

        if not documentos:
            raise ValueError(f"Nenhum texto extraivel encontrado em {caminho}")

        return documentos
