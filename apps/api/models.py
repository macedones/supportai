# ============================================================
# Modelos Pydantic — request/response da API.
#
# No JS original esses formatos nao existiam de forma explicita
# (eram so objetos passados pra res.json()). Em FastAPI, declarar
# isso como classes traz validacao automatica: se o cliente mandar
# um campo errado ou faltando, a API rejeita antes mesmo de rodar
# o codigo do endpoint, com um erro 422 detalhado.
# ============================================================

from typing import Literal

from pydantic import BaseModel, Field


# ---------- /api/chat ----------

class ChatRequest(BaseModel):
    project_slug: str
    message: str
    session_id: str | None = None


class Fonte(BaseModel):
    documento_nome: str
    secao: str | None = None
    distancia: float | None = None


class ChatResponse(BaseModel):
    resposta: str
    fontes: list[Fonte]
    tokens_usados: int
    conversa_id: str
    mensagem_id: str


# ---------- /api/feedback ----------

class FeedbackRequest(BaseModel):
    mensagem_id: str
    avaliacao: Literal["positiva", "negativa"]


class FeedbackResponse(BaseModel):
    ok: bool = True


# ---------- /api/health ----------

class HealthResponse(BaseModel):
    status: str
    database: str
    detalhe: str | None = None


# ---------- /api/metrics/{slug} ----------

class ProjetoMetricas(BaseModel):
    nome: str
    status: str
    total_documentos: int
    total_chunks: int


class ConversasMetricas(BaseModel):
    total: int
    total_perguntas: int
    total_respostas: int


class QualidadeMetricas(BaseModel):
    respostas_com_fonte: int
    respostas_sem_fonte: int
    taxa_cobertura_pct: int | None
    tokens_total: int
    tokens_medio: int


class FeedbackMetricas(BaseModel):
    positivas: int
    negativas: int
    sem_avaliacao: int
    taxa_satisfacao_pct: int | None


class DocumentoCitado(BaseModel):
    documento: str
    vezes_citado: int


class MetricsResponse(BaseModel):
    projeto: ProjetoMetricas
    conversas: ConversasMetricas
    qualidade: QualidadeMetricas
    feedback: FeedbackMetricas
    documentos_mais_citados: list[DocumentoCitado] = Field(default_factory=list)


# ---------- erros ----------

class ErroResponse(BaseModel):
    erro: str
