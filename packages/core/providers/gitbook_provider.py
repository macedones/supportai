from .base import DocumentoExtraido, SourceProvider


class GitBookProvider(SourceProvider):
    """
    [PLACEHOLDER — nao implementado ainda]

    Ingestao a partir de um espaco publicado no GitBook.

    Caminho mais simples (sem token): a maioria dos GitBooks publica
    paginas estaticas em HTML publico — nesse caso da' pra reaproveitar
    o HTMLProvider direto, apontando pra cada URL publicada
    (ex: HTMLProvider().extrair("https://docs.exemplo.com/pagina")),
    sem precisar de nenhum codigo novo.

    Caminho completo (com token, pra sites privados ou pra descobrir
    a arvore de paginas automaticamente): falta
    - GITBOOK_API_TOKEN (.env)
    - GET /v1/spaces/{space_id}/content via API oficial do GitBook
    - Percorrer a arvore de paginas retornada e extrair o conteudo
      (ja vem em formato de documento estruturado, nao precisa de
      parsing de HTML)
    - Cada pagina vira 1 DocumentoExtraido
    """

    tipo = "html"
    nome = "gitbook"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        raise NotImplementedError(
            "GitBookProvider ainda nao foi implementado como conector dedicado. "
            "Para GitBooks publicos, use o HTMLProvider apontando direto pras URLs "
            "publicadas. Para integracao via API (espacos privados), requer "
            "GITBOOK_API_TOKEN — ver a docstring desta classe."
        )
