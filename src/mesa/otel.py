"""T3 (Fase 2): a árvore de atribuição REAL — spans do OpenTelemetry gravados no livro.

Substitui o span sintético das fases anteriores. O processor escuta o fim de cada span
e insere a linha COMPLETA (começo, fim, desfecho) na tabela `span` — IDs originais do
OTel, nunca inventados aqui (D-02). Insert-only: o span só entra no livro quando fecha,
então nunca há UPDATE (D-06). Consequência de desenho: a compra é gravada DEPOIS do
flush dos spans (a FK de request exige o span já no livro) — o driver captura os IDs
na hora da compra e grava no fim do run.
"""

from datetime import UTC, datetime
from typing import Any

import psycopg
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.trace import StatusCode, format_span_id, format_trace_id

from mesa import db


def _ts(nanos: int | None) -> datetime | None:
    if nanos is None:
        return None
    return datetime.fromtimestamp(nanos / 1e9, tz=UTC)


def _outcome(span: ReadableSpan) -> str:
    """Mapeia o status OTel para o label do TCA (span.outcome)."""
    code = span.status.status_code
    if code is StatusCode.OK:
        return "success"
    if code is StatusCode.ERROR:
        return "failure"
    return "unknown"


class LivroSpanProcessor(SpanProcessor):
    """Grava cada span encerrado na tabela `span` do livro, na hora, em ordem."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def on_end(self, span: ReadableSpan) -> None:
        ctx = span.get_span_context()
        if ctx is None:  # pragma: no cover - defensivo
            return
        parent = format_span_id(span.parent.span_id) if span.parent is not None else None
        resource_attrs = span.resource.attributes if span.resource else {}
        agent_ref = str(resource_attrs.get("service.name", "")) or None
        started = _ts(span.start_time)
        if started is None:  # pragma: no cover - OTel sempre carimba início
            started = db.now_utc()
        db.insert_span(
            self._conn,
            trace_id=format_trace_id(ctx.trace_id),
            span_id=format_span_id(ctx.span_id),
            parent_span_id=parent,
            name=span.name,
            agent_ref=agent_ref,
            attributes=dict(span.attributes) if span.attributes else None,
            started_utc=started,
            ended_utc=_ts(span.end_time),
            outcome=_outcome(span),
        )

    def shutdown(self) -> None:  # pragma: no cover - nada a liberar (conexão é do dono)
        return

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True  # sincrono: on_end já gravou


def configurar_tracer(conn: psycopg.Connection[Any], service_name: str) -> trace.Tracer:
    """TracerProvider com o processor do livro. service_name vira span.agent_ref."""
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(LivroSpanProcessor(conn))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("mesa")


def ids_do_span_atual() -> tuple[str, str]:
    """(trace_id, span_id) do span ativo — é neles que a compra pendura."""
    ctx = trace.get_current_span().get_span_context()
    return format_trace_id(ctx.trace_id), format_span_id(ctx.span_id)
