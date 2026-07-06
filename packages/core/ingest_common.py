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
import os
import re
import sys

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


def validar_ai_provider() -> None:
    """
    Confere se o AI_PROVIDER configurado no .env tem o necessario pra
    gerar embeddings (chave de API, etc.) antes de comecar a ingerir
    — evita descobrir isso so' depois de processar metade dos documentos.

    Estava duplicado em ingest.py e ingest_openapi.py; centralizado
    aqui pra ser reaproveitado por qualquer CLI de ingestao.
    """
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


def ingerir_via_provider(conexao, projeto_id: str, provider, origem: str) -> list[str]:
    """
    Pipeline GENERICO de ingestao — funciona identico para qualquer
    SourceProvider (MarkdownProvider, OpenAPIProvider, PDFProvider,
    HTMLProvider, GitRepositoryProvider, ...).

    So' o provider.extrair(origem) muda entre fontes; o resto —
    chunking, embedding, insercao no banco, idempotencia — e' sempre
    este mesmo codigo. Essa e' a ideia central da arquitetura de
    conectores: adicionar uma fonte nova nunca exige tocar aqui.

    Retorna a lista de nomes de arquivo processados.
    """
    documentos = provider.extrair(origem)
    processados = []

    for doc in documentos:
        print(f"\nProcessando: {doc.nome_arquivo} (via {provider.nome})")

        # Cada bloco do provider pode ser maior que CHUNK_SIZE — nesse
        # caso e' subdividido aqui, preservando a mesma secao nos
        # sub-chunks resultantes.
        chunks: list[tuple[str, str | None]] = []
        for secao, texto in doc.blocos:
            for sub_texto in dividir_em_chunks(texto):
                chunks.append((sub_texto, secao))

        print(f"  -> {len(chunks)} chunk(s) gerado(s)")

        documento_id = obter_ou_criar_documento(conexao, projeto_id, doc.nome_arquivo, tipo=provider.tipo)
        inserir_chunks_no_documento(conexao, documento_id, projeto_id, doc.nome_arquivo, chunks)
        finalizar_documento(conexao, documento_id, len(chunks))
        conexao.commit()

        print(f"  -> \"{doc.nome_arquivo}\" concluido ({len(chunks)} chunks)")
        processados.append(doc.nome_arquivo)

    return processados
