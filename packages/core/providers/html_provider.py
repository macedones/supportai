from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import DocumentoExtraido, SourceProvider

_TAGS_IGNORADAS = ("script", "style", "nav", "footer", "header", "noscript")
_TAGS_CABECALHO = ("h1", "h2", "h3")
_TAGS_TEXTO = ("p", "li", "td", "pre")


class HTMLProvider(SourceProvider):
    """
    Extrai texto visivel de HTML — locais (pasta com .html/.htm) ou
    remotos (uma URL http/https). Remove script/style/nav/footer e
    usa h1/h2/h3 como marcador de secao, agrupando o texto que vem
    depois de cada cabecalho no mesmo bloco.
    """

    tipo = "html"
    nome = "html"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        if origem.startswith("http://") or origem.startswith("https://"):
            return [self._extrair_url(origem)]

        caminho = Path(origem).resolve()
        if caminho.is_dir():
            arquivos = sorted(caminho.glob("*.html")) + sorted(caminho.glob("*.htm"))
        elif caminho.is_file():
            arquivos = [caminho]
        else:
            raise FileNotFoundError(f"Nao encontrado: {caminho}")

        if not arquivos:
            raise FileNotFoundError(f"Nenhum .html encontrado em {caminho}")

        return [self._extrair_arquivo(arquivo) for arquivo in arquivos]

    def _extrair_arquivo(self, caminho: Path) -> DocumentoExtraido:
        html = caminho.read_text(encoding="utf-8", errors="ignore")
        return DocumentoExtraido(nome_arquivo=caminho.name, blocos=self._blocos_de_html(html))

    def _extrair_url(self, url: str) -> DocumentoExtraido:
        resposta = requests.get(url, timeout=15, headers={"User-Agent": "SupportAI-Ingest/1.0"})
        resposta.raise_for_status()

        caminho_url = urlparse(url).path.strip("/").replace("/", "_")
        nome = f"{caminho_url or urlparse(url).netloc}.html"

        return DocumentoExtraido(nome_arquivo=nome, blocos=self._blocos_de_html(resposta.text))

    def _blocos_de_html(self, html: str) -> list[tuple[str | None, str]]:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(_TAGS_IGNORADAS):
            tag.decompose()

        blocos: list[tuple[str | None, str]] = []
        secao_atual: str | None = None
        texto_atual: list[str] = []
        corpo = soup.body or soup

        for elemento in corpo.descendants:
            nome_tag = getattr(elemento, "name", None)

            if nome_tag in _TAGS_CABECALHO:
                if texto_atual:
                    blocos.append((secao_atual, "\n\n".join(texto_atual).strip()))
                    texto_atual = []
                secao_atual = elemento.get_text(strip=True)
            elif nome_tag in _TAGS_TEXTO:
                texto = elemento.get_text(" ", strip=True)
                if texto:
                    texto_atual.append(texto)

        if texto_atual:
            blocos.append((secao_atual, "\n\n".join(texto_atual).strip()))

        return [b for b in blocos if b[1]]
