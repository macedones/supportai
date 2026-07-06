# ============================================================
# Contrato base da arquitetura de conectores (SourceProvider).
#
# Ideia central: o pipeline RAG (chunking, embeddings, insercao no
# banco) NUNCA muda — ele vive em ingest_common.ingerir_via_provider().
# Um provider so precisa saber ler a origem (pasta, arquivo, URL,
# repositorio, espaco de wiki...) e devolver DocumentoExtraido(s) com
# blocos de texto ja organizados por secao.
#
# Para adicionar uma fonte nova (ex: Confluence de verdade), basta
# implementar uma classe com extrair() e registrar em providers/__init__.py.
# Nada em ingest_common.py, rag.py, embeddings.py ou nos routers da API
# precisa mudar.
# ============================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DocumentoExtraido:
    """
    Uma unidade logica de documento pronta para ingestao.

    nome_arquivo: vira documentos.nome_arquivo (usado tambem como
        rotulo de fonte nas citacoes do RAG, ex: "manual.pdf")
    blocos: lista de (secao, texto). "secao" pode ser None quando a
        fonte nao tem uma nocao natural de secao (ex: um .txt solto).
        Cada bloco ainda passa por dividir_em_chunks() no pipeline
        generico, entao nao ha problema em blocos grandes aqui.
    """

    nome_arquivo: str
    blocos: list[tuple[str | None, str]] = field(default_factory=list)


class SourceProvider(ABC):
    """
    Contrato que qualquer fonte de ingestao deve implementar.
    """

    #: valor gravado em documentos.tipo — precisa estar entre os
    #: permitidos pela constraint chk_documentos_tipo (sql/01_schema.sql):
    #: 'pdf', 'docx', 'md', 'txt', 'html', 'faq', 'openapi'
    tipo: str

    #: chave curta usada no registro de providers e na CLI (ingest_source.py)
    nome: str

    @abstractmethod
    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        """
        Le a origem (formato especifico de cada provider: pasta local,
        caminho de arquivo, URL, "repo#subpasta", etc.) e retorna os
        documentos extraidos dela, prontos para o pipeline generico.
        """
        raise NotImplementedError
