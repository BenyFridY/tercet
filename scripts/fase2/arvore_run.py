"""T3 (Fase 2): a árvore de atribuição REAL — spans OTel no livro, compras nos passos certos.

Uma tarefa de 5 passos (raiz + 4 filhos), com DUAS compras MCP pagas reais em passos
DIFERENTES. Prova do critério de pronto:
  1. >=3 spans reais no livro, árvore íntegra (uma raiz, sem órfãos);
  2. cada compra pendurada no span exato em que aconteceu;
  3. a soma bate em qualquer altura (folha, meio, topo) — conferida aqui E nos testes puros.

Pre-condição: vendedor MCP rodando (uv run python -m mesa.mcp.seller) + Postgres de pé.
Custo declarado: 0,02 USDC de testnet (2 compras de 0,01).
"""

import asyncio
import sys
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from opentelemetry.trace import StatusCode
from rich.console import Console

from mesa import arvore, db
from mesa.config import Settings
from mesa.mcp.buyer import CapturedMcp, make_mcp_client, record_mcp_purchase, result_text_of
from mesa.mcp.seller import MCP_HOST, MCP_PORT
from mesa.otel import configurar_tracer, ids_do_span_atual

MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"
CANONICAL = f"mcp://{MCP_HOST}:{MCP_PORT}/tool/consultar"
PRECO_MINOR = 10_000  # 0,01 USDC

console = Console()


@dataclass
class CompraFeita:
    """Compra capturada DENTRO do span; gravada depois do run (a FK exige o span no livro)."""

    trace_id: str
    span_id: str
    captured: CapturedMcp
    result_text: str | None
    is_error: bool


async def rodar_tarefa(settings: Settings, conn: Any) -> tuple[str, list[CompraFeita]]:
    tracer = configurar_tracer(conn, service_name="driver-t3")
    compras: list[CompraFeita] = []
    trace_id_da_tarefa = ""

    async with streamable_http_client(MCP_URL) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def comprar(pergunta: str) -> None:
                """Uma compra dentro do span ATUAL — os IDs saem do contexto OTel, não da mão."""
                captured = CapturedMcp()
                xmcp = make_mcp_client(settings, session, captured)
                t_id, s_id = ids_do_span_atual()
                result = await xmcp.call_tool("consultar", {"pergunta": pergunta})
                compras.append(
                    CompraFeita(
                        trace_id=t_id,
                        span_id=s_id,
                        captured=captured,
                        result_text=result_text_of(result),
                        is_error=bool(result.is_error),
                    )
                )

            with tracer.start_as_current_span("tarefa.responder-pergunta") as raiz:
                trace_id_da_tarefa = ids_do_span_atual()[0]
                with tracer.start_as_current_span("passo.preparar") as sp:
                    sp.set_status(StatusCode.OK)  # passo sem compra — na árvore com gasto 0
                with tracer.start_as_current_span("passo.comprar-dado") as sp:
                    await comprar("qual o fato de hoje?")
                    sp.set_status(StatusCode.OK)
                with tracer.start_as_current_span("passo.comprar-confirmacao") as sp:
                    await comprar("confirma o fato?")
                    sp.set_status(StatusCode.OK)
                with tracer.start_as_current_span("passo.sintetizar") as sp:
                    sp.set_status(StatusCode.OK)
                raiz.set_status(StatusCode.OK)

    return trace_id_da_tarefa, compras


def main() -> int:
    settings = Settings()
    conn = db.connect()
    try:
        trace_id, compras = asyncio.run(rodar_tarefa(settings, conn))

        # Grava as compras DEPOIS do run: todos os spans já estão no livro (on_end).
        for c in compras:
            classe = record_mcp_purchase(
                conn,
                captured=c.captured,
                canonical=CANONICAL,
                tool_name="consultar",
                trace_id=c.trace_id,
                span_id=c.span_id,
                result_text=c.result_text,
                is_error=c.is_error,
            )
            console.print(f"compra no span [bold]{c.span_id}[/]: {classe}")

        nos, gasto = arvore.carregar_arvore(conn, trace_id)
        problemas = arvore.verificar(nos, gasto)
        acc = arvore.rollup(nos, gasto)

        console.print(f"\n[bold]trace {trace_id}[/] — {len(nos)} spans")
        por_id = {n.span_id: n for n in nos}
        for n in sorted(nos, key=lambda x: (x.parent_span_id or "", x.name)):
            pai = por_id[n.parent_span_id].name if n.parent_span_id in por_id else "-"
            console.print(
                f"  {n.name:32} pai={pai:28} proprio={gasto.get(n.span_id, 0):>6}"
                f" acumulado={acc[n.span_id]:>6}"
            )

        # ---- Os asserts do critério de pronto (T3): ESTRUTURA, não contagem ----
        # (o SDK mcp 2.0 tem OTel embutido: os spans "MCP send tools/call" dele entram
        #  na MESMA árvore — ruído do mundo real que o livro DEVE registrar. Cada compra
        #  aparece com 2 tools/call: o que levou payment-required + o repetido com prova.)
        assert problemas == [], f"árvore quebrada: {problemas}"
        raizes = [n for n in nos if n.parent_span_id is None]
        assert len(raizes) == 1 and raizes[0].name == "tarefa.responder-pergunta"
        raiz = raizes[0]
        nossos = {n.name for n in nos if n.parent_span_id == raiz.span_id}
        assert {"passo.preparar", "passo.comprar-dado", "passo.comprar-confirmacao",
                "passo.sintetizar"} <= nossos, f"passos faltando sob a raiz: {nossos}"
        assert len(nos) >= 5, f"esperava >=5 spans, veio {len(nos)}"
        spans_com_compra = {c.span_id for c in compras}
        nomes_com_compra = {por_id[s].name for s in spans_com_compra}
        assert nomes_com_compra == {"passo.comprar-dado", "passo.comprar-confirmacao"}, (
            f"compras nos passos errados: {nomes_com_compra}"
        )
        for s in spans_com_compra:
            assert gasto.get(s) == PRECO_MINOR, f"gasto próprio errado no span {s}"
        assert acc[raiz.span_id] == 2 * PRECO_MINOR, "a soma NÃO bateu no topo"
        assert arvore.total_das_raizes(nos, acc) == sum(gasto.values()), "topo != total"
        sem_compra_na_raiz = [
            n for n in nos
            if n.parent_span_id == raiz.span_id and n.span_id not in spans_com_compra
        ]
        assert all(acc[n.span_id] == 0 for n in sem_compra_na_raiz), (
            "passo sem compra com gasto acumulado"
        )

        console.print("\n[bold green]T3: OK — a soma bate em toda altura, "
                      "e cada compra está no passo exato.[/]")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
