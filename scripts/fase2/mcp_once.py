"""T2 (Fase 2): UM tool call MCP pago ponta a ponta, gravado no livro.

Pre-condicao: o vendedor MCP rodando (uv run python -m mesa.mcp.seller).
Prova: resultado entregue + _meta com x402/payment-response (tx real) + tripla no livro
com transport='mcp' e tool_name='consultar'.
"""

import asyncio
import secrets
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mesa import db
from mesa.config import Settings
from mesa.mcp.buyer import CapturedMcp, make_mcp_client, record_mcp_purchase, result_text_of
from mesa.mcp.seller import MCP_HOST, MCP_PORT

MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"
CANONICAL = f"mcp://{MCP_HOST}:{MCP_PORT}/tool/consultar"


async def main() -> int:
    settings = Settings()
    captured = CapturedMcp()

    async with streamable_http_client(MCP_URL) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            xmcp = make_mcp_client(settings, session, captured)
            result = await xmcp.call_tool("consultar", {"pergunta": "qual o fato de hoje?"})

    text = result_text_of(result)
    print(f"is_error={result.is_error} payment_made={result.payment_made}")
    print(f"conteudo: {text}")
    if result.payment_response is not None:
        pr = result.payment_response
        tx = getattr(pr, "transaction", None)
        print(f"payment_response: success={getattr(pr, 'success', None)} tx={tx}")

    # T2 ainda usa span raiz sintetico (a arvore OTel real e a T3)
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    conn = db.connect()
    try:
        db.insert_span(
            conn,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            name="t2-mcp.compra-unica",
            agent_ref="scripts/mcp_once",
            attributes={"fase": "2", "tarefa": "T2"},
            started_utc=db.now_utc(),
        )
        classe = record_mcp_purchase(
            conn,
            captured=captured,
            canonical=CANONICAL,
            tool_name="consultar",
            trace_id=trace_id,
            span_id=span_id,
            result_text=text,
            is_error=bool(result.is_error),
        )
    finally:
        conn.close()

    print(f"livro: {classe} (trace={trace_id} span={span_id})")
    ok = (not result.is_error) and result.payment_made and classe == "tripla"
    print("T2:", "OK" if ok else "FALHOU")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
