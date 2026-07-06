from .base import DocumentoExtraido, SourceProvider


class ConfluenceProvider(SourceProvider):
    """
    [PLACEHOLDER — nao implementado ainda]

    Ingestao a partir de um espaco do Confluence via REST API.

    Para implementar de verdade, falta:
    - Credenciais via .env: CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL,
      CONFLUENCE_API_TOKEN (API token, nao senha — Confluence Cloud
      usa Basic Auth com email + token)
    - Paginar GET /wiki/rest/api/content?spaceKey={origem}&limit=50
      ate esgotar os resultados (campo "_links.next")
    - Para cada pagina, buscar o corpo em formato "storage" (que e'
      HTML) com ?expand=body.storage
    - Reaproveitar HTMLProvider._blocos_de_html() pra transformar
      esse HTML em blocos (secao, texto) — e' o mesmo formato, so'
      muda de onde o HTML vem
    - Cada pagina do Confluence vira 1 DocumentoExtraido (nome_arquivo
      = titulo da pagina + ".html", pra manter tipo='html' na constraint)
    """

    tipo = "html"
    nome = "confluence"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        raise NotImplementedError(
            "ConfluenceProvider ainda nao foi implementado. Requer credenciais de API "
            "(CONFLUENCE_BASE_URL / CONFLUENCE_EMAIL / CONFLUENCE_API_TOKEN) e integracao "
            "com a REST API do Confluence. Ver a docstring desta classe para o plano de implementacao."
        )
