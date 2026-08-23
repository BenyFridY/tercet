"""Fase 12 — a demo PONTA A PONTA, autônoma: vendedor → 3 compras x402 → coletor → livro.

Feita para ser disparada pela aba 06 operações do app (D-36), mas roda igual no
terminal. TESTNET SEMPRE (Base Sepolia, USDC de faucet, gas do facilitator) —
dinheiro real: zero. Cada passo imprime o que provou; qualquer divergência quebra.

Uso: uv run python scripts/fase12/demo_ponta_a_ponta.py [n_compras]
"""

import asyncio
import sys
import threading
import time

import httpx
import uvicorn
from x402.http.clients import x402HttpxClient

from mesa import collector, db, rede_segura
from mesa.config import Settings
from mesa.http.buyer import Captured, make_client, record_purchase
from mesa.otel import configurar_tracer, ids_do_span_atual

SELLER = "http://127.0.0.1:8402"


def _vendedor_de_pe() -> bool:
    try:
        httpx.get(f"{SELLER}/openapi.json", timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


def _subir_vendedor() -> None:
    from mesa.http.seller import app  # import aqui: o módulo exige SELLER_PAYTO no env

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8402,
                                           log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(40):
        if _vendedor_de_pe():
            return
        time.sleep(0.25)
    raise SystemExit("vendedor de brinquedo não subiu na porta 8402")


async def main(n: int) -> None:
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)

    if _vendedor_de_pe():
        print(f"1/4 vendedor já estava de pé em {SELLER} — usando o existente")
    else:
        _subir_vendedor()
        print(f"1/4 vendedor de brinquedo de pé em {SELLER} (0,01 USDC, exact, Sepolia)")

    tracer = configurar_tracer(conn, "fase12-demo")
    compradas = 0
    for i in range(n):
        captured = Captured()
        xc = make_client(s, captured)  # seletor SEGURO padrão da testnet (furo 8)
        with tracer.start_as_current_span("fase12.demo-ponta-a-ponta"):
            trace_id, span_id = ids_do_span_atual()
            async with x402HttpxClient(xc, base_url=SELLER, timeout=120.0) as http, \
                    http.stream("GET", "/brinquedo") as r:
                corpo, _trunc = await rede_segura.ler_corpo_limitado_async(r)
        # record_purchase FORA do bloco: o span vira linha no banco quando FECHA,
        # e a FK de request(trace_id, span_id) precisa dela já existindo
        classe = record_purchase(
            conn, captured=captured, canonical=f"GET {SELLER}/brinquedo",
            trace_id=trace_id, span_id=span_id, status_http=r.status_code,
            content=corpo, content_type=r.headers.get("content-type"))
        assert r.status_code == 200 and classe == "tripla", f"compra {i+1} falhou"
        compradas += 1
        print(f"2/4 compra {i+1}/{n}: 200 + tripla no livro (request→quote→authz)")

    print("3/4 esperando a liquidação aterrissar e rodando o coletor…")
    time.sleep(5)
    collector.main(300)  # Transfer(to=payTo) + AuthorizationUsed, casados por txHash

    with conn.cursor() as cur:
        cur.execute("""
            SELECT count(*) FILTER (WHERE l.authorization_id IS NOT NULL), count(*)
            FROM span sp JOIN request r ON r.span_id = sp.span_id
            JOIN quote q ON q.request_id = r.id
            JOIN authz a ON a.quote_id = q.id
            LEFT JOIN settlement_leg l ON l.authorization_id = a.id
            WHERE sp.name = 'fase12.demo-ponta-a-ponta'
        """)
        row = cur.fetchone()
        assert row is not None
        casadas, total = int(row[0]), int(row[1])
    print(f"4/4 {casadas}/{total} compras da demo CASADAS por (authorizer, nonce)")
    assert casadas >= compradas, "compra desta rodada ficou sem liquidação casada"
    print("PONTA A PONTA VERDE: recarregue o blotter — as compras estão lá, liquidadas")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
