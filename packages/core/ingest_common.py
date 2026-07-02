# ============================================================
# Funcoes compartilhadas entre os scripts de ingestao
# (ingest.py para .md, ingest_openapi.py para Swagger/OpenAPI,
# e futuros ingestores).
#
# Extraido de ingest.py para permitir reaproveitar o mesmo
# pipeline (organizacao/projeto/documento/chunks/embeddings)
# a partir de fontes diferentes, sem duplicar logica de banco.
# ============================================================

import json
import re

from embeddings import gerar_embedding

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

NOMES_PROJETOS = {
    "erp-hospitalar": "MedSys ERP Hospitalar",
    "erp-juridico": "JurisSys ERP Juridico",
}


# ------------------------------------------------------------
# Divide um texto em chunks por paragrafo, respeitando um
# tamanho maximo, com sobreposicao entre chunks consecutivos.
# ------------------------------------------------------------
def dividir_em_chunks(texto: str) -> list[str]:
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]

    chunks = []
    atual = ""

    for paragrafo in paragrafos:
        if len(atual + "\n\n" + paragrafo) > CHUNK_SIZE and len(atual) > 0:
            chunks.append(atual)
            # overlap: pega o final do chunk anterior para dar contexto ao proximo
            overlap_texto = atual[-CHUNK_OVERLAP:]
            atual = overlap_texto + "\n\n" + paragrafo
        else:
            atual = (atual + "\n\n" + paragrafo) if atual else paragrafo

    if atual.strip():
        chunks.append(atual)

    return chunks


def extrair_secao(texto: str) -> str | None:
    """Retorna o titulo do primeiro cabecalho Markdown encontrado no texto."""
    for linha in texto.split("\n"):
        match = re.match(r"^#{1,6}\s+(.*)", linha)
        if match:
            return match.group(1).strip()
    return None


def obter_ou_criar_organizacao(conexao) -> str:
    with conexao.cursor() as cursor:
        cursor.execute("SELECT id FROM organizacoes WHERE nome = %s LIMIT 1", ("Demo",))
        existente = cursor.fetchone()
        if existente:
            return existente["id"]

        cursor.execute(
            "INSERT INTO organizacoes (nome, plano) VALUES (%s, %s) RETURNING id",
            ("Demo", "free"),
        )
        return cursor.fetchone()["id"]


def obter_ou_criar_projeto(conexao, org_id: str, slug: str) -> str:
    with conexao.cursor() as cursor:
        cursor.execute("SELECT id FROM projetos WHERE slug = %s LIMIT 1", (slug,))
        existente = cursor.fetchone()
        if existente:
            return existente["id"]

        nome = NOMES_PROJETOS.get(slug, slug)

        cursor.execute(
            """
            INSERT INTO projetos (org_id, nome, slug, status, persona_tom, idioma_padrao)
            VALUES (%s, %s, %s, 'processando', 'tecnico_e_direto', 'pt-BR')
            RETURNING id
            """,
            (org_id, nome, slug),
        )
        return cursor.fetchone()["id"]


def obter_ou_criar_documento(conexao, projeto_id: str, nome_arquivo: str, tipo: str) -> str:
    """
    Cria (ou reseta, se ja existir) o registro de um documento.
    Se ja existir, apaga os chunks antigos para permitir reprocessamento
    idempotente (reingerir o mesmo arquivo substitui o conteudo anterior).
    """
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM documentos WHERE projeto_id = %s AND nome_arquivo = %s",
            (projeto_id, nome_arquivo),
        )
        documento_existente = cursor.fetchone()

        if documento_existente:
            documento_id = documento_existente["id"]
            cursor.execute("DELETE FROM chunks WHERE documento_id = %s", (documento_id,))
            cursor.execute(
                """
                UPDATE documentos
                SET status_processamento = 'processando', total_chunks = 0, processado_em = NULL, tipo = %s
                WHERE id = %s
                """,
                (tipo, documento_id),
            )
            return documento_id

        cursor.execute(
            """
            INSERT INTO documentos (projeto_id, nome_arquivo, tipo, status_processamento)
            VALUES (%s, %s, %s, 'processando')
            RETURNING id
            """,
            (projeto_id, nome_arquivo, tipo),
        )
        return cursor.fetchone()["id"]


def inserir_chunks_no_documento(
    conexao, documento_id: str, projeto_id: str, nome_arquivo: str, chunks: list[tuple[str, str | None]]
) -> None:
    """
    Gera embedding e insere cada chunk, na ordem da lista.

    chunks: lista de tuplas (texto_chunk, secao) ja prontas para persistir
    (ja divididas em pedacos <= CHUNK_SIZE).
    """
    with conexao.cursor() as cursor:
        for i, (texto_chunk, secao) in enumerate(chunks):
            print(f"  -> embedding chunk {i + 1}/{len(chunks)}...", end="")
            embedding = gerar_embedding(texto_chunk)
            print(" ok")

            metadados = {"documento_nome": nome_arquivo, "secao": secao}
            vetor_textual = f"[{','.join(str(v) for v in embedding)}]"

            cursor.execute(
                """
                INSERT INTO chunks (documento_id, projeto_id, conteudo, ordem, embedding, metadados)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (documento_id, projeto_id, texto_chunk, i, vetor_textual, json.dumps(metadados)),
            )


def finalizar_documento(conexao, documento_id: str, total_chunks: int) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            UPDATE documentos
            SET status_processamento = 'concluido', total_chunks = %s, processado_em = now()
            WHERE id = %s
            """,
            (total_chunks, documento_id),
        )


def ativar_projeto(conexao, projeto_id: str) -> None:
    with conexao.cursor() as cursor:
        cursor.execute("UPDATE projetos SET status = 'ativo' WHERE id = %s", (projeto_id,))
