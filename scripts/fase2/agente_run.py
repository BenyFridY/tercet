"""T6 (Fase 2): o agente decide comprar — e o GATE 2 fecha.

Um agente Claude (claude-sonnet-5, do zero — D-33) recebe uma tarefa, tenta a
ferramenta gratuita, descobre que não resolve, e DECIDE pagar pela fonte. Tudo cai
no livro pendurado na árvore real do run — inclusive a compra que o servidor MCP
delega upstream para atender.

GATE 2, como asserts: (a) a soma por agente/passo/tarefa bate exatamente;
(b) a compra aninhada não desaparece; (c) as compras reais aparecem no livro como
qualquer outra — e casam na chain.

Pré-condição: vendedor HTTP (8402) + vendedor MCP (8403) rodando; ANTHROPIC_API_KEY
em C:\\dev\\mesa.env. Custo declarado por run: ~centavos de API + 0,02 USDC testnet
(0,01 direto + 0,01 delegado).
"""

import asyncio
import sys
import time
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from opentelemetry.trace import StatusCode
from rich.console import Console

from mesa import arvore, db
from mesa.agente import RunDoAgente, rodar_agente
from mesa.collector import main as coletar
from mesa.config import Settings
from mesa.mcp.buyer import record_delegated_purchases, record_mcp_purchase
from mesa.mcp.seller import MCP_HOST, MCP_PORT
from mesa.otel import configurar_tracer, ids_do_span_atual

MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"
CANONICAL = f"mcp://{MCP_HOST}:{MCP_PORT}/tool/consultar"
PRECO_MINOR = 10_000

console = Console()


async def rodar(settings: Settings, conn: Any) -> tuple[str, RunDoAgente]:
    tracer = configurar_tracer(conn, service_name="agente-t6")
    trace_id = ""
    async with (
        streamable_http_client(MCP_URL) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        with tracer.start_as_current_span("tarefa.agente-pesquisa") as raiz:
            trace_id = ids_do_span_atual()[0]
            run = await rodar_agente(settings, session, tracer)
            raiz.set_status(StatusCode.OK)
    return trace_id, run


def main() -> int:
    settings = Settings()
    conn = db.connect()
    try:
        trace_id, run = asyncio.run(rodar(settings, conn))

        console.print(f"\n[bold]resposta do agente[/] ({run.turnos} turnos, "
                      f"{run.chamadas_gratuitas} chamada(s) gratuita(s), "
                      f"{len(run.compras)} compra(s)):")
        console.print(f"  {run.resposta_final[:400]}")

        # Grava DEPOIS do run (spans já no livro): compra direta + delegadas por compra
        delegadas = 0
        for c in run.compras:
            record_mcp_purchase(
                conn, captured=c.captured, canonical=CANONICAL, tool_name="consultar",
                trace_id=c.trace_id, span_id=c.span_id,
                result_text=c.result_text, is_error=c.is_error,
            )
            delegadas += record_delegated_purchases(
                conn, captured=c.captured, trace_id=c.trace_id, span_id=c.span_id
            )

        nos, gasto = arvore.carregar_arvore(conn, trace_id)
        problemas = arvore.verificar(nos, gasto)
        acc = arvore.rollup(nos, gasto)
        por_id = {n.span_id: n for n in nos}

        console.print(f"\n[bold]árvore do run[/] — {len(nos)} spans:")
        for n in sorted(nos, key=lambda x: (x.parent_span_id or "", x.name)):
            pai = por_id[n.parent_span_id].name if n.parent_span_id in por_id else "-"
            console.print(f"  {n.name:34} pai={pai:28} proprio={gasto.get(n.span_id, 0):>6}"
                          f" acumulado={acc[n.span_id]:>6}")

        # ---------- GATE 2 ----------
        # o agente DECIDIU: tentou o grátis antes e comprou ao menos uma vez
        assert run.chamadas_gratuitas >= 1, "o agente nem tentou a ferramenta gratuita"
        assert len(run.compras) >= 1, "o agente não comprou — a tarefa exigia a fonte paga"
        assert "fato pago da mesa" in run.resposta_final, "a resposta não usa o dado comprado"
        assert delegadas == len(run.compras), "compra aninhada DESAPARECEU do recibo propagado"

        # árvore íntegra; compra pendurada no span da DECISÃO (ferramenta.fonte-paga)
        assert problemas == [], f"árvore quebrada: {problemas}"
        for c in run.compras:
            assert por_id[c.span_id].name == "ferramenta.fonte-paga", (
                f"compra fora do passo da decisão: {por_id[c.span_id].name}"
            )
        raiz = next(n for n in nos if n.parent_span_id is None)
        esperado_total = 2 * PRECO_MINOR * len(run.compras)  # direta + delegada por compra
        assert acc[raiz.span_id] == esperado_total, "a soma NÃO bateu no topo"
        assert arvore.total_das_raizes(nos, acc) == sum(gasto.values()), "topo != total"

        # as liquidações casam na chain (direta E delegada, com retry — a chain demora)
        nonces: list[str] = []
        for c in run.compras:
            inner = dict(dict(c.captured.payload.payload).get("authorization") or {})
            nonces.append(str(inner.get("nonce", "")).lower())
            rec = (c.captured.result_meta or {})["mesa/upstream-receipts"][0]
            nonces.append(str(rec["recibo"]["authorization"]["nonce"]).lower())

        def _settled() -> dict[str, str]:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lower((rail_evidence->'authorization')->>'nonce'), state"
                    " FROM authz WHERE lower((rail_evidence->'authorization')->>'nonce')"
                    " = ANY(%s)", (nonces,),
                )
                return {r[0]: r[1] for r in cur.fetchall()}

        console.print("\n[bold]coletor (com retry)...[/]")
        estados: dict[str, str] = {}
        for tentativa in range(6):
            if tentativa:
                time.sleep(15)
            coletar(5000)
            estados = _settled()
            console.print(f"  tentativa {tentativa + 1}: "
                          f"{sum(1 for v in estados.values() if v == 'settled')}/{len(nonces)}"
                          " settled")
            if len(estados) == len(nonces) and set(estados.values()) == {"settled"}:
                break
        assert set(estados.values()) == {"settled"}, f"liquidações não casaram: {estados}"

        console.print("\n[bold green]GATE 2 VERDE — o agente decidiu, o livro registrou, "
                      "a aninhada não desapareceu, a soma bate, a chain confirma.[/]")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
