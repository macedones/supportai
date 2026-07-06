# ============================================================
# Parser puro de specs Swagger 2.0 / OpenAPI 3.x.
#
# Sem I/O de banco — apenas: le o arquivo, resolve $ref locais, e
# devolve uma lista de blocos (secao, texto) semanticos:
# - Visao geral da API
# - 1 bloco por endpoint (metodo + path), com parametros, request
#   body e respostas — schemas referenciados sao expandidos inline
#   (nao so citados pelo nome) para o RAG nao precisar recuperar
#   dois chunks separados pra responder uma pergunta sobre 1 endpoint
# - 1 bloco por schema/model nomeado (components.schemas / definitions)
#
# Usado por providers/openapi_provider.py (arquitetura de conectores)
# e por ingest_openapi.py (CLI de compatibilidade).
# ============================================================

import json
from pathlib import Path

import yaml

METODOS_HTTP = ("get", "post", "put", "patch", "delete", "options", "head")


# ------------------------------------------------------------
# Leitura e resolucao de $ref locais (components/schemas ou
# definitions). Nao resolve $ref externos (outro arquivo/URL) —
# cobre o caso comum de specs autocontidas em um unico arquivo.
# ------------------------------------------------------------
def carregar_spec(caminho: Path) -> dict:
    conteudo = caminho.read_text(encoding="utf-8")
    if caminho.suffix.lower() == ".json":
        return json.loads(conteudo)
    return yaml.safe_load(conteudo)


def _versao_spec(spec: dict) -> str:
    if "openapi" in spec:
        return "openapi3"
    if "swagger" in spec:
        return "swagger2"
    raise ValueError('Spec invalida: nao encontrei a chave "openapi" nem "swagger" na raiz do arquivo.')


def _schemas_da_spec(spec: dict, versao: str) -> dict:
    if versao == "openapi3":
        return (spec.get("components") or {}).get("schemas") or {}
    return spec.get("definitions") or {}


def _resolver_ref(spec: dict, ref: str) -> dict | None:
    """Resolve um $ref local no formato '#/a/b/c'."""
    if not ref.startswith("#/"):
        return None
    node = spec
    for parte in ref[2:].split("/"):
        if not isinstance(node, dict) or parte not in node:
            return None
        node = node[parte]
    return node


def _resolver_schema(spec: dict, schema: dict | None, _profundidade: int = 0) -> dict:
    """Segue $ref ate achar um schema concreto (com guarda contra recursao)."""
    if not schema or _profundidade > 10:
        return schema or {}
    if "$ref" in schema:
        resolvido = _resolver_ref(spec, schema["$ref"])
        return _resolver_schema(spec, resolvido, _profundidade + 1)
    return schema


def _texto(valor) -> str:
    """Normaliza campos de texto vindos da spec (strip de espacos/quebras
    residuais de scalars YAML dobrados como '>')."""
    return str(valor).strip() if valor else ""


def _nome_schema_do_ref(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


# ------------------------------------------------------------
# Descreve um schema (objeto/array/tipo primitivo) em texto
# legivel, listando campos, tipos, obrigatoriedade e descricao.
# Usado tanto para schemas nomeados quanto para request/response
# bodies inline.
# ------------------------------------------------------------
def _descrever_schema(spec: dict, schema: dict | None, prefixo: str = "", _profundidade: int = 0) -> list[str]:
    linhas: list[str] = []
    if not schema or _profundidade > 4:
        return linhas

    if "$ref" in schema:
        nome = _nome_schema_do_ref(schema["$ref"])
        linhas.append(f"{prefixo}- (referencia ao schema `{nome}`)")
        return linhas

    tipo = schema.get("type")

    if tipo == "array":
        linhas.append(f"{prefixo}- Lista de:")
        item_bruto = schema.get("items") or {}
        item_schema = _resolver_schema(spec, item_bruto)
        if "$ref" in item_bruto:
            nome = _nome_schema_do_ref(item_bruto["$ref"])
            linhas.append(f"{prefixo}  (cada item e um `{nome}`, campos abaixo)")
        linhas.extend(_descrever_schema(spec, item_schema, prefixo + "  ", _profundidade + 1))
        return linhas

    propriedades = schema.get("properties")
    if propriedades:
        obrigatorios = set(schema.get("required") or [])
        for nome_campo, campo in propriedades.items():
            campo_resolvido = _resolver_schema(spec, campo)
            tipo_campo = campo_resolvido.get("type", "objeto")
            if "$ref" in (campo or {}):
                tipo_campo = _nome_schema_do_ref(campo["$ref"])
            marcador = "obrigatorio" if nome_campo in obrigatorios else "opcional"
            descricao_campo = _texto(campo_resolvido.get("description", ""))
            enum = campo_resolvido.get("enum")
            partes = [f"{prefixo}- `{nome_campo}` ({tipo_campo}, {marcador})"]
            if descricao_campo:
                partes.append(f": {descricao_campo}")
            if enum:
                partes.append(f" — valores possiveis: {', '.join(str(v) for v in enum)}")
            linhas.append("".join(partes))
        return linhas

    if tipo:
        descricao = _texto(schema.get("description", ""))
        linhas.append(f"{prefixo}- tipo `{tipo}`" + (f": {descricao}" if descricao else ""))

    return linhas


def _bloco_visao_geral(spec: dict, versao: str) -> tuple[str, str]:
    info = spec.get("info") or {}
    titulo = info.get("title", "API")
    descricao = _texto(info.get("description", ""))
    versao_api = info.get("version", "")

    if versao == "openapi3":
        servidores = [s.get("url", "") for s in (spec.get("servers") or [])]
    else:
        esquema = (spec.get("schemes") or ["https"])[0]
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        servidores = [f"{esquema}://{host}{base_path}"] if host else []

    linhas = [f"# {titulo}"]
    if versao_api:
        linhas.append(f"Versao da API: {versao_api}")
    if descricao:
        linhas.append(f"\n{descricao}")
    if servidores:
        linhas.append("\nURL(s) base:")
        linhas.extend(f"- {s}" for s in servidores if s)

    total_endpoints = sum(
        1 for _ in _iterar_operacoes(spec)
    )
    linhas.append(f"\nEsta API possui {total_endpoints} endpoint(s) documentado(s).")

    return "Visao geral da API", "\n".join(linhas)


def _iterar_operacoes(spec: dict):
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for metodo, operacao in item.items():
            if metodo.lower() in METODOS_HTTP and isinstance(operacao, dict):
                yield path, metodo.lower(), operacao


def _bloco_endpoint(spec: dict, versao: str, path: str, metodo: str, operacao: dict) -> tuple[str, str]:
    secao = f"{metodo.upper()} {path}"
    linhas = [f"## {secao}"]

    resumo = operacao.get("summary")
    if resumo:
        linhas.append(f"\n**Resumo:** {resumo}")

    descricao = _texto(operacao.get("description"))
    if descricao:
        linhas.append(f"\n**Descricao:** {descricao}")

    tags = operacao.get("tags")
    if tags:
        linhas.append(f"\n**Categoria:** {', '.join(tags)}")

    # Parametros (path, query, header) — formato comum ao Swagger 2 e OpenAPI 3
    parametros = operacao.get("parameters") or []
    if parametros:
        linhas.append("\n**Parametros:**")
        for param in parametros:
            param = _resolver_schema(spec, param) if "$ref" in (param or {}) else param
            nome_param = param.get("name", "?")
            local_param = param.get("in", "?")
            obrigatorio = "obrigatorio" if param.get("required") else "opcional"
            tipo_param = param.get("type") or (param.get("schema") or {}).get("type", "string")
            descricao_param = _texto(param.get("description", ""))
            linha = f"- `{nome_param}` ({local_param}, {tipo_param}, {obrigatorio})"
            if descricao_param:
                linha += f": {descricao_param}"
            linhas.append(linha)

    # Request body — OpenAPI 3 usa requestBody, Swagger 2 usa parametro "in: body"
    if versao == "openapi3" and operacao.get("requestBody"):
        conteudo = (operacao["requestBody"].get("content") or {})
        for media_type, media in conteudo.items():
            schema_bruto = media.get("schema") or {}
            schema = _resolver_schema(spec, schema_bruto)
            linhas.append(f"\n**Corpo da requisicao ({media_type}):**")
            if "$ref" in schema_bruto:
                nome = _nome_schema_do_ref(schema_bruto["$ref"])
                linhas.append(f"- Schema: `{nome}`")
            linhas.extend(_descrever_schema(spec, schema))
    else:
        for param in parametros:
            if param.get("in") == "body":
                schema_bruto = param.get("schema") or {}
                schema = _resolver_schema(spec, schema_bruto)
                linhas.append("\n**Corpo da requisicao:**")
                if "$ref" in schema_bruto:
                    nome = _nome_schema_do_ref(schema_bruto["$ref"])
                    linhas.append(f"- Schema: `{nome}`")
                linhas.extend(_descrever_schema(spec, schema))

    # Respostas
    respostas = operacao.get("responses") or {}
    if respostas:
        linhas.append("\n**Respostas possiveis:**")
        for codigo, resposta in respostas.items():
            descricao_resp = _texto((resposta or {}).get("description", ""))
            linhas.append(f"- `{codigo}`: {descricao_resp}")

            if versao == "openapi3":
                conteudo_resp = (resposta or {}).get("content") or {}
                for media_type, media in conteudo_resp.items():
                    schema_bruto = media.get("schema") or {}
                    if not schema_bruto:
                        continue
                    schema_resp = _resolver_schema(spec, schema_bruto)
                    if "$ref" in schema_bruto:
                        nome = _nome_schema_do_ref(schema_bruto["$ref"])
                        linhas.append(f"  - corpo da resposta ({media_type}): schema `{nome}`")
                    linhas.extend(_descrever_schema(spec, schema_resp, prefixo="    "))
            else:
                schema_bruto = resposta.get("schema") if isinstance(resposta, dict) else None
                if schema_bruto:
                    schema_resp = _resolver_schema(spec, schema_bruto)
                    if "$ref" in schema_bruto:
                        nome = _nome_schema_do_ref(schema_bruto["$ref"])
                        linhas.append(f"  - corpo da resposta: schema `{nome}`")
                    linhas.extend(_descrever_schema(spec, schema_resp, prefixo="    "))

    return secao, "\n".join(linhas)


def _bloco_schema(nome: str, schema: dict, spec: dict) -> tuple[str, str]:
    secao = f"Schema: {nome}"
    linhas = [f"## Modelo de dados: {nome}"]

    descricao = _texto(schema.get("description"))
    if descricao:
        linhas.append(f"\n{descricao}")

    linhas.append("\n**Campos:**")
    campos = _descrever_schema(spec, schema)
    linhas.extend(campos if campos else ["- (schema sem campos detalhados)"])

    exemplo = schema.get("example")
    if exemplo:
        linhas.append("\n**Exemplo:**")
        linhas.append("```json")
        linhas.append(json.dumps(exemplo, ensure_ascii=False, indent=2))
        linhas.append("```")

    return secao, "\n".join(linhas)


def gerar_blocos(spec: dict) -> list[tuple[str, str]]:
    """
    Retorna a lista de blocos (secao, texto) extraidos da spec:
    visao geral + 1 por endpoint + 1 por schema nomeado.
    Nao acessa banco — funcao pura, testavel isoladamente.
    """
    versao = _versao_spec(spec)
    blocos = [_bloco_visao_geral(spec, versao)]

    for path, metodo, operacao in _iterar_operacoes(spec):
        blocos.append(_bloco_endpoint(spec, versao, path, metodo, operacao))

    schemas = _schemas_da_spec(spec, versao)
    for nome, schema in schemas.items():
        blocos.append(_bloco_schema(nome, schema, spec))

    return blocos
