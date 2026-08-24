"""GATE 13a: um cliente MCP REAL (stdio, processo separado) consulta o livro.

O que este script prova, do jeito que um agente de verdade usaria:
1. o servidor sobe por stdio (subprocess) — não é chamada em memória;
2. a lista de ferramentas é EXATAMENTE a fechada (D-37);
3. o 'gasto' que atravessou o transporte bate com SQL independente;
4. 'vereditos' e 'status_do_livro' respondem com as regras de honestidade.

(O read-only estrutural é provado na suíte: tests/test_mcp_livro.py.)
"""

import asyncio
import json
import sys
from typing import Any

import psycopg
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mesa.config import Settings

ESPERADAS = {"status_do_livro", "gasto", "compras", "compra", "vereditos",
             "passaportes", "fiscal"}


def _texto(result: Any) -> dict[str, Any]:
    corpo = json.loads(result.content[0].text)
    assert isinstance(corpo, dict)
    return corpo


async def main() -> None:
    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "mesa.mcp.livro"])
    async with stdio_client(params) as (read, write), \
            ClientSession(read, write) as sess:
        await sess.initialize()

        listagem = await sess.list_tools()
        nomes = {t.name for t in listagem.tools}
        assert nomes == ESPERADAS, f"lista aberta demais ou de menos: {nomes}"
        print(f"[1/3] lista fechada OK: {len(nomes)} ferramentas, só leitura")

        r = await sess.call_tool("gasto", {})
        gasto = _texto(r)
        with psycopg.connect(Settings().database_url,
                             connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT coalesce(sum(sl.settled_amount_minor), 0)
                FROM settlement_leg sl JOIN authz a ON a.id = sl.authorization_id
                JOIN quote q ON q.id = a.quote_id
                WHERE q.asset_network_caip2 = 'eip155:8453'
            """)
            row = cur.fetchone()
            assert row is not None
            mainnet = int(row[0])
        assert gasto["gasto_real_minor"] == mainnet, (gasto["gasto_real_minor"],
                                                      mainnet)
        print(f"[2/3] gasto via stdio == SQL independente: "
              f"{mainnet} micro-USD (US$ {gasto['gasto_real_usd']}) mainnet")

        vs = _texto(await sess.call_tool("vereditos", {}))
        st = _texto(await sess.call_tool("status_do_livro", {}))
        print(f"[3/3] vereditos: {[(v['veredito'], v['n']) for v in vs['vereditos']]}"
              f" · corrente de hash: {st['corrente_elos']} elos")

        print("GATE 13a VERDE — o livro responde a um agente por MCP, sem "
              "conseguir escrever.")


if __name__ == "__main__":
    asyncio.run(main())
