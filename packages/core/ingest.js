// ============================================================
// Knowledge Engine — Script de Ingestao
//
// O que este script faz:
// 1. Le todos os arquivos .md de uma pasta de demo (ex: demo/docs-erp-hospitalar)
// 2. Cria (ou reaproveita) um registro em "projetos" para esse persona
// 3. Para cada arquivo .md:
//    - Cria um registro em "documentos"
//    - Divide o conteudo em chunks (pedacos de texto)
//    - Gera o embedding de cada chunk via OpenAI
//    - Insere os chunks na tabela "chunks"
//
// Como rodar:
//   node ingest.js <slug-do-projeto> <pasta-com-os-md>
//
// Exemplo:
//   node ingest.js erp-hospitalar ../../demo/docs-erp-hospitalar
// ============================================================

import "dotenv/config";
import fs from "node:fs/promises";
import path from "node:path";
import pg from "pg";
import { gerarEmbedding } from "./rag.js";

const EMBEDDING_DIMENSIONS = 1536;

// Tamanho aproximado de cada chunk, em caracteres.
// ~1500 caracteres ~= 350-400 tokens, um bom equilibrio para RAG de FAQ/manuais.
const CHUNK_SIZE = 1500;
const CHUNK_OVERLAP = 200;

const [, , projetoSlug, pastaDocumentos] = process.argv;

if (!projetoSlug || !pastaDocumentos) {
  console.error("Uso: node ingest.js <slug-do-projeto> <pasta-com-os-md>");
  console.error("Exemplo: node ingest.js erp-hospitalar ../../demo/docs-erp-hospitalar");
  process.exit(1);
}

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });

// ------------------------------------------------------------
// Divide um texto em chunks por parágrafo, respeitando um
// tamanho maximo, com sobreposicao entre chunks consecutivos.
//
// Estrategia simples e previsivel: parte por blocos separados
// por linha em branco (paragrafos/secoes do markdown), e vai
// agrupando ate atingir CHUNK_SIZE. Isso evita cortar uma frase
// no meio, o que prejudicaria a qualidade do embedding.
// ------------------------------------------------------------
function dividirEmChunks(texto) {
  const paragrafos = texto
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  const chunks = [];
  let atual = "";

  for (const paragrafo of paragrafos) {
    if ((atual + "\n\n" + paragrafo).length > CHUNK_SIZE && atual.length > 0) {
      chunks.push(atual);
      // overlap: pega o final do chunk anterior para dar contexto ao proximo
      const overlapTexto = atual.slice(-CHUNK_OVERLAP);
      atual = overlapTexto + "\n\n" + paragrafo;
    } else {
      atual = atual ? atual + "\n\n" + paragrafo : paragrafo;
    }
  }

  if (atual.trim()) {
    chunks.push(atual);
  }

  return chunks;
}

// ------------------------------------------------------------
// Extrai a "secao" de um chunk a partir do ultimo cabecalho
// markdown (#, ##, ###) presente no texto. Usado em metadados
// para alimentar "fontes_utilizadas" depois.
// ------------------------------------------------------------
function extrairSecao(texto) {
  const linhas = texto.split("\n");
  for (const linha of linhas) {
    const match = linha.match(/^#{1,6}\s+(.*)/);
    if (match) return match[1].trim();
  }
  return null;
}

async function obterOuCriarOrganizacao(client) {
  const existente = await client.query(
    `SELECT id FROM organizacoes WHERE nome = $1 LIMIT 1`,
    ["Demo"]
  );
  if (existente.rows.length > 0) return existente.rows[0].id;

  const inserido = await client.query(
    `INSERT INTO organizacoes (nome, plano) VALUES ($1, $2) RETURNING id`,
    ["Demo", "free"]
  );
  return inserido.rows[0].id;
}

async function obterOuCriarProjeto(client, orgId, slug) {
  const existente = await client.query(
    `SELECT id FROM projetos WHERE slug = $1 LIMIT 1`,
    [slug]
  );
  if (existente.rows.length > 0) return existente.rows[0].id;

  // Mapeamento simples de slug -> nome amigavel.
  // Se aparecer um slug novo, usa o proprio slug como nome.
  const nomes = {
    "erp-hospitalar": "MedSys ERP Hospitalar",
    "erp-juridico": "JurisSys ERP Juridico",
  };
  const nome = nomes[slug] ?? slug;

  const inserido = await client.query(
    `INSERT INTO projetos (org_id, nome, slug, status, persona_tom, idioma_padrao)
     VALUES ($1, $2, $3, 'processando', 'tecnico_e_direto', 'pt-BR')
     RETURNING id`,
    [orgId, nome, slug]
  );
  return inserido.rows[0].id;
}

async function ingerirDocumento(client, projetoId, caminhoArquivo) {
  const nomeArquivo = path.basename(caminhoArquivo);
  console.log(`\nProcessando: ${nomeArquivo}`);

  const conteudo = await fs.readFile(caminhoArquivo, "utf-8");
  const chunks = dividirEmChunks(conteudo);
  console.log(`  -> ${chunks.length} chunk(s) gerado(s)`);

  // Cria (ou reseta) o registro do documento.
  // Se o documento ja existir (mesmo nome no mesmo projeto), apaga
  // os chunks antigos para permitir reprocessamento idempotente.
  const documentoExistente = await client.query(
    `SELECT id FROM documentos WHERE projeto_id = $1 AND nome_arquivo = $2`,
    [projetoId, nomeArquivo]
  );

  let documentoId;
  if (documentoExistente.rows.length > 0) {
    documentoId = documentoExistente.rows[0].id;
    await client.query(`DELETE FROM chunks WHERE documento_id = $1`, [documentoId]);
    await client.query(
      `UPDATE documentos
       SET status_processamento = 'processando', total_chunks = 0, processado_em = NULL
       WHERE id = $1`,
      [documentoId]
    );
  } else {
    const inserido = await client.query(
      `INSERT INTO documentos (projeto_id, nome_arquivo, tipo, status_processamento)
       VALUES ($1, $2, 'md', 'processando')
       RETURNING id`,
      [projetoId, nomeArquivo]
    );
    documentoId = inserido.rows[0].id;
  }

  // Gera embedding e insere cada chunk.
  for (let i = 0; i < chunks.length; i++) {
    const textoChunk = chunks[i];
    const secao = extrairSecao(textoChunk);

    process.stdout.write(`  -> embedding chunk ${i + 1}/${chunks.length}...`);
    const embedding = await gerarEmbedding(textoChunk);
    process.stdout.write(" ok\n");

    const metadados = {
      documento_nome: nomeArquivo,
      secao: secao,
    };

    await client.query(
      `INSERT INTO chunks (documento_id, projeto_id, conteudo, ordem, embedding, metadados)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        documentoId,
        projetoId,
        textoChunk,
        i,
        `[${embedding.join(",")}]`, // pgvector aceita o formato textual "[v1,v2,...]"
        JSON.stringify(metadados),
      ]
    );
  }

  await client.query(
    `UPDATE documentos
     SET status_processamento = 'concluido', total_chunks = $2, processado_em = now()
     WHERE id = $1`,
    [documentoId, chunks.length]
  );

  console.log(`  -> documento "${nomeArquivo}" concluido (${chunks.length} chunks)`);
}

async function main() {
  if (!process.env.OPENAI_API_KEY || process.env.OPENAI_API_KEY.startsWith("sk-coloque")) {
    console.error("ERRO: defina OPENAI_API_KEY no arquivo .env antes de rodar a ingestao.");
    process.exit(1);
  }

  const pastaAbsoluta = path.resolve(process.cwd(), pastaDocumentos);
  const arquivos = (await fs.readdir(pastaAbsoluta)).filter((f) => f.endsWith(".md"));

  if (arquivos.length === 0) {
    console.error(`Nenhum arquivo .md encontrado em ${pastaAbsoluta}`);
    process.exit(1);
  }

  console.log(`Projeto: ${projetoSlug}`);
  console.log(`Pasta: ${pastaAbsoluta}`);
  console.log(`Arquivos encontrados: ${arquivos.join(", ")}`);

  const client = await pool.connect();

  try {
    const orgId = await obterOuCriarOrganizacao(client);
    const projetoId = await obterOuCriarProjeto(client, orgId, projetoSlug);

    for (const arquivo of arquivos) {
      await ingerirDocumento(client, projetoId, path.join(pastaAbsoluta, arquivo));
    }

    await client.query(`UPDATE projetos SET status = 'ativo' WHERE id = $1`, [projetoId]);

    console.log("\n✅ Ingestao concluida com sucesso.");
    console.log(`Projeto ID: ${projetoId}`);
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((err) => {
  console.error("\n❌ Erro durante a ingestao:", err.message);
  process.exit(1);
});
