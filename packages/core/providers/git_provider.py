import subprocess
import tempfile
from pathlib import Path

from .base import DocumentoExtraido, SourceProvider
from .markdown_provider import MarkdownProvider


class GitRepositoryProvider(SourceProvider):
    """
    Clona um repositorio git publico (raso, --depth 1) e ingere os
    arquivos .md encontrados dentro dele, reaproveitando o
    MarkdownProvider por composicao — nao reimplementa nada do
    parsing de Markdown.

    origem: "<url-do-repo>" ou "<url-do-repo>#<subpasta>" para
    limitar a ingestao a uma subpasta (ex: so a pasta docs/, sem
    trazer o resto do codigo).

    Requer o binario "git" disponivel no PATH. O clone e' apagado
    automaticamente ao final (diretorio temporario).
    """

    tipo = "md"
    nome = "git"

    def extrair(self, origem: str) -> list[DocumentoExtraido]:
        url, _, subpasta = origem.partition("#")

        with tempfile.TemporaryDirectory(prefix="supportai_git_") as tmp:
            print(f"  clonando {url}...")
            resultado = subprocess.run(
                ["git", "clone", "--depth", "1", url, tmp],
                capture_output=True,
                text=True,
            )
            if resultado.returncode != 0:
                raise RuntimeError(f"Falha ao clonar {url}: {resultado.stderr.strip()}")

            pasta_alvo = Path(tmp) / subpasta if subpasta else Path(tmp)
            if not pasta_alvo.is_dir():
                raise NotADirectoryError(f'Subpasta "{subpasta}" nao existe no repositorio clonado.')

            # MarkdownProvider le do disco de forma sincrona, dentro
            # do "with" — o clone ainda existe nesse ponto.
            return MarkdownProvider().extrair(str(pasta_alvo))
