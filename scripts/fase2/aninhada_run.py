"""T4 (Fase 2): a compra ANINHADA não desaparece — recibo propagado, delegada no livro.

O agente paga a ferramenta MCP; o servidor MCP, para atender, COMPRA do vendedor HTTP
com a carteira dele; o recibo dessa compra volta assinado dentro da resposta. Prova:
  1. DUAS compras no livro penduradas no mesmo passo: origin='direct' e origin='delegated';
  2. a delegada tem origin_ref (quem comprou) e origin_receipt_sig (assinatura verificada);
  3. o coletor casa AS DUAS liquidações na chain por (authorizer, nonce) — authorizers
     DIFERENTES (comprador vs servidor), mesmo payTo;
  4. reconciliação: ok sobe exatamente +2, zero órfãos novos.

Pré-condição: vendedor HTTP (porta 8402) E vendedor MCP (8403) rodando; MCP_SERVER_PK
no .env com saldo. Custo declarado: 0,02 USDC de testnet (0,01 direto + 0,01 delegado).
"""

import asyncio
import sys
import time
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from opentelemetry.trace import StatusCode
from rich.console import Console

from mesa import db
from mesa.collector import main as coletar
from mesa.config import Settings
from mesa.mcp.buyer import (
    CapturedMcp,
    make_mcp_client,
    record_delegated_purchases,
    record_mcp_purchase,
    result_text_of,
)
from mesa.mcp.seller import MCP_HOST, MCP_PORT
from mesa.otel import configurar_tracer, ids_do_span_atual
from mesa.reconcile import Veredito, carregar, reconciliar

MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"
CANONICAL = f"mcp://{MCP_HOST}:{MCP_PORT}/tool/consultar"

console = Console()


def _contar_ok(conn: Any) -> tuple[int, int]:
    compras, liqs = carregar(conn)
    r = reconciliar(compras, liqs)
    return len(r[Veredito.OK]), len(r[Veredito.ORFAO_CHAIN])


async def rodar(settings: Settings, conn: Any) -> tuple[str, str, CapturedMcp, Any]:
    tracer = configurar_tracer(conn, service_name="driver-t4")
    captured = CapturedMcp()
    result: Any = None
    t_id = s_id = ""

    async with streamable_http_client(MCP_URL) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            xmcp = make_mcp_client(settings, session, captured)
            with tracer.start_as_current_span("tarefa.pesquisa-com-fornecedor") as raiz:
                with tracer.start_as_current_span("passo.consultar-delegando") as sp:
                    t_id, s_id = ids_do_span_atual()
                    result = await xmcp.call_tool(
                        "consultar", {"pergunta": "fato com insumo de terceiro?"}
                    )
                    sp.set_status(StatusCode.OK)
                raiz.set_status(StatusCode.OK)
    return t_id, s_id, captured, result


def main() -> int:
    settings = Settings()
    if not settings.mcp_server_pk:
        raise SystemExit("MCP_SERVER_PK ausente no .env — gere a carteira do servidor antes.")
    conn = db.connect()
    try:
        ok_antes, orfaos_antes = _contar_ok(conn)

        trace_id, span_id, captured, result = asyncio.run(rodar(settings, conn))
        assert result is not None and not result.is_error, (
            f"tool call falhou: {result_text_of(result) if result else result}"
        )

        classe = record_mcp_purchase(
            conn, captured=captured, canonical=CANONICAL, tool_name="consultar",
            trace_id=trace_id, span_id=span_id,
            result_text=result_text_of(result), is_error=bool(result.is_error),
        )
        n_delegadas = record_delegated_purchases(
            conn, captured=captured, trace_id=trace_id, span_id=span_id
        )
        console.print(f"compra direta: {classe} · delegadas gravadas: {n_delegadas}")
        assert classe == "tripla" and n_delegadas == 1

        # As duas linhas no mesmo passo, com papéis distintos e assinatura no lugar
        with conn.cursor() as cur:
            cur.execute(
                "SELECT origin, origin_ref, origin_receipt_sig IS NOT NULL"
                " FROM request WHERE trace_id=%s AND span_id=%s ORDER BY origin",
                (trace_id, span_id),
            )
            linhas = cur.fetchall()
        console.print(f"requests no passo: {linhas}")
        assert len(linhas) == 2, f"esperava 2 compras no passo, veio {len(linhas)}"
        assert linhas[0][0] == "delegated" and linhas[1][0] == "direct"
        assert linhas[0][1] and linhas[0][1].lower() == settings.mcp_server_address.lower()
        assert linhas[0][2] is True, "delegada sem assinatura de recibo"

        # O coletor tem que casar AS DUAS liquidações DESTE run (authorizers diferentes,
        # mesmo payTo). Assert nas DUAS authz específicas — contagem global contamina
        # entre experimentos. Retry: o settle leva segundos para aparecer no RPC.
        nonce_direta = str(dict(dict(captured.payload.payload).get("authorization") or {})
                           .get("nonce", "")).lower()
        rec_env = (captured.result_meta or {})["mesa/upstream-receipts"][0]
        nonce_delegada = str(rec_env["recibo"]["authorization"]["nonce"]).lower()

        def _estados() -> dict[str, str]:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lower((rail_evidence->'authorization')->>'nonce'), state"
                    " FROM authz WHERE lower((rail_evidence->'authorization')->>'nonce')"
                    " IN (%s, %s)", (nonce_direta, nonce_delegada),
                )
                return {r[0]: r[1] for r in cur.fetchall()}

        console.print("\n[bold]rodando o coletor (com retry — a chain leva segundos)...[/]")
        estados: dict[str, str] = {}
        for tentativa in range(6):
            if tentativa:
                time.sleep(15)
            coletar(5000)
            estados = _estados()
            console.print(f"  tentativa {tentativa + 1}: {estados}")
            if set(estados.values()) == {"settled"}:
                break
        assert estados.get(nonce_direta) == "settled", "a compra DIRETA não casou na chain"
        assert estados.get(nonce_delegada) == "settled", "a compra DELEGADA não casou na chain"

        ok_depois, orfaos_depois = _contar_ok(conn)
        console.print(f"ok: {ok_antes} -> {ok_depois} · órfãos-chain: "
                      f"{orfaos_antes} -> {orfaos_depois}")

        console.print("\n[bold green]T4: OK — a compra aninhada NÃO desapareceu: "
                      "delegada no livro, assinada, e casada na chain.[/]")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
