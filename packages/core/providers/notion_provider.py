from .base import DocumentoExtraido, SourceProvider


class NotionProvider(SourceProvider):
    """
    [PLACEHOLDER — nao implementado ainda]

    Ingestao a partir de uma pagina/database do Notion via API oficial.

    Para implementar de verdade, falta:
    - Credenciais via .env: NOTION_API_TOKEN (integration token) e o
      ID da pagina ou database raiz (origem = esse ID)
    - Autorizar a integration a acessar as paginas desejadas
      (compartilhamento manual no Notion — nao tem "espaco inteiro"
      como o Confluence)
    - GET /v1/blocks/{id}/children (paginado via "next_cursor"),
      recursivo para paginas aninhadas
    - Reconstruir o texto a partir dos block types do Notion
      (paragraph, heading_1/2/3, bulleted_list_item, code, etc.) —
      cada heading_N vira um marcador de secao, no mesmo espirito do
      HTMLProvider
    - Cada pagina do Notion vira 1 DocumentoExtraido
    """

    tipo = "html"
    nome = "notion"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        raise NotImplementedError(
            "NotionProvider ainda nao foi implementado. Requer NOTION_API_TOKEN e "
            "integracao com a Notion API (GET /v1/blocks/{id}/children). "
            "Ver a docstring desta classe para o plano de implementacao."
        )
