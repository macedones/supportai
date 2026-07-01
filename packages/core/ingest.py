# ============================================================
# Knowledge Engine — Script de Ingestao
#
# O que este script faz:
# 1. Le todos os arquivos .md de uma pasta de demo (ex: demo/docs-erp-hospitalar)
# 2. Cria (ou reaproveita) um registro em "projetos" para esse persona
# 3. Para cada arquivo .md:
#    - Cria um registro em "documentos"
#    - Divide o conteudo em chunks (pedacos de texto)
#    - Gera o embedding de cada chunk
#    - Insere os chunks na tabela "chunks"
#
# Como rodar:
#   python ingest.py <slug-do-projeto> <pasta-com-os-md>
#
# Exemplo:
#   python ingest.py erp-hospitalar ../../demo/docs-erp-hospitalar
# ============================================================

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from db import obter_conexao
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
# Equivalente a dividirEmChunks() do ingest.js.
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
    """Equivalente a extrairSecao() do ingest.js."""
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


def ingerir_documento(conexao, projeto_id: str, caminho_arquivo: Path) -> None:
    nome_arquivo = caminho_arquivo.name
    print(f"\nProcessando: {nome_arquivo}")

    conteudo = caminho_arquivo.read_text(encoding="utf-8")
    chunks = dividir_em_chunks(conteudo)
    print(f"  -> {len(chunks)} chunk(s) gerado(s)")

    with conexao.cursor() as cursor:
        # Cria (ou reseta) o registro do documento. Se ja existir,
        # apaga os chunks antigos para permitir reprocessamento idempotente.
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
                SET status_processamento = 'processando', total_chunks = 0, processado_em = NULL
                WHERE id = %s
                """,
                (documento_id,),
            )
        else:
            cursor.execute(
                """
                INSERT INTO documentos (projeto_id, nome_arquivo, tipo, status_processamento)
                VALUES (%s, %s, 'md', 'processando')
                RETURNING id
                """,
                (projeto_id, nome_arquivo),
            )
            documento_id = cursor.fetchone()["id"]

        # Gera embedding e insere cada chunk.
        for i, texto_chunk in enumerate(chunks):
            secao = extrair_secao(texto_chunk)

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

        cursor.execute(
            """
            UPDATE documentos
            SET status_processamento = 'concluido', total_chunks = %s, processado_em = now()
            WHERE id = %s
            """,
            (len(chunks), documento_id),
        )

    conexao.commit()
    print(f"  -> documento \"{nome_arquivo}\" concluido ({len(chunks)} chunks)")


def _validar_provider() -> None:
    ai_provider = os.environ.get("AI_PROVIDER", "openai")

    if ai_provider == "mock":
        print("AI_PROVIDER=mock — ingestao sem chamadas externas (embeddings via feature hashing).")
    elif ai_provider in ("groq", "ollama"):
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        print(f"AI_PROVIDER={ai_provider} — embeddings via Ollama ({ollama_url}).")
        if ai_provider == "groq" and not os.environ.get("GROQ_API_KEY"):
            print("ERRO: defina GROQ_API_KEY no .env para usar AI_PROVIDER=groq.")
            sys.exit(1)
    elif ai_provider == "openai":
        chave = os.environ.get("OPENAI_API_KEY", "")
        if not chave or chave.startswith("sk-coloque"):
            print("ERRO: defina OPENAI_API_KEY no .env para usar AI_PROVIDER=openai.")
            print("Alternativa gratuita: AI_PROVIDER=groq (console.groq.com) ou AI_PROVIDER=ollama.")
            sys.exit(1)


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python ingest.py <slug-do-projeto> <pasta-com-os-md>")
        print("Exemplo: python ingest.py erp-hospitalar ../../demo/docs-erp-hospitalar")
        sys.exit(1)

    projeto_slug, pasta_documentos = sys.argv[1], sys.argv[2]

    _validar_provider()

    pasta_absoluta = Path(pasta_documentos).resolve()
    arquivos = sorted(p for p in pasta_absoluta.glob("*.md"))

    if not arquivos:
        print(f"Nenhum arquivo .md encontrado em {pasta_absoluta}")
        sys.exit(1)

    print(f"Projeto: {projeto_slug}")
    print(f"Pasta: {pasta_absoluta}")
    print(f"Arquivos encontrados: {', '.join(a.name for a in arquivos)}")

    conexao = obter_conexao()

    try:
        org_id = obter_ou_criar_organizacao(conexao)
        conexao.commit()

        projeto_id = obter_ou_criar_projeto(conexao, org_id, projeto_slug)
        conexao.commit()

        for arquivo in arquivos:
            ingerir_documento(conexao, projeto_id, arquivo)

        with conexao.cursor() as cursor:
            cursor.execute("UPDATE projetos SET status = 'ativo' WHERE id = %s", (projeto_id,))
        conexao.commit()

        print("\nIngestao concluida com sucesso.")
        print(f"Projeto ID: {projeto_id}")
    finally:
        conexao.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print("\nErro durante a ingestao:")
        print(erro)
        sys.exit(1)
