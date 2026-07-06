# ============================================================
# Registro central de providers de ingestao.
#
# Adicionar uma fonte nova = criar uma classe (herda de SourceProvider,
# implementa extrair()) + adicionar 1 linha aqui. Nada em
# ingest_common.py, rag.py ou nos routers da API precisa mudar —
# essa e' a ideia da arquitetura de conectores.
# ============================================================

from .base import DocumentoExtraido, SourceProvider
from .confluence_provider import ConfluenceProvider
from .git_provider import GitRepositoryProvider
from .gitbook_provider import GitBookProvider
from .html_provider import HTMLProvider
from .markdown_provider import MarkdownProvider
from .notion_provider import NotionProvider
from .openapi_provider import OpenAPIProvider
from .pdf_provider import PDFProvider

PROVIDERS: dict[str, type[SourceProvider]] = {
    "md": MarkdownProvider,
    "openapi": OpenAPIProvider,
    "pdf": PDFProvider,
    "html": HTMLProvider,
    "git": GitRepositoryProvider,
    "confluence": ConfluenceProvider,  # placeholder, ver docstring
    "notion": NotionProvider,          # placeholder, ver docstring
    "gitbook": GitBookProvider,        # placeholder, ver docstring
}

__all__ = [
    "SourceProvider",
    "DocumentoExtraido",
    "PROVIDERS",
    "MarkdownProvider",
    "OpenAPIProvider",
    "PDFProvider",
    "HTMLProvider",
    "GitRepositoryProvider",
    "ConfluenceProvider",
    "NotionProvider",
    "GitBookProvider",
]
