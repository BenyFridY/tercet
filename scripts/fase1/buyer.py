"""Loop do comprador: paga N vezes e grava a tripla no livro (usa mesa.http.buyer).

Uso: uv run python scripts/buyer.py [n]   (default n=10)
"""

import asyncio
import sys
import uuid

from rich.console import Console
from x402.http.clients import x402HttpxClient

from mesa import db
from mesa.config import Settings
from mesa.http.buyer import Captured, make_client, record_purchase

console = Console()
BASE = "http://127.0.0.1:8402"


async def main(n: int) -> None:
    s = Settings()
    conn = db.connect()
    applied = db.apply_migrations(conn)
    if applied:
        console.print(f"migrations aplicadas: {applied}")

    trace_id = uuid.uuid4().hex
    root_span = uuid.uuid4().hex[:16]
    db.insert_span(
        conn, trace_id=trace_id, span_id=root_span, parent_span_id=None,
        name="mesa.fds1.buyer_loop", agent_ref="buyer-script",
        attributes={"n": n}, started_utc=db.now_utc(),
    )

    captured = Captured()
    xc = make_client(s, captured)
    ok = 0
    async with x402HttpxClient(xc, base_url=BASE, timeout=120.0) as http:
        for i in range(n):
            captured.reset()
            r = await http.get("/brinquedo")
            classe = record_purchase(
                conn, captured=captured, canonical=f"GET {BASE}/brinquedo",
                trace_id=trace_id, span_id=root_span, status_http=r.status_code,
                content=r.content, content_type=r.headers.get("content-type"),
            )
            ok += classe == "tripla"
            console.print(f"  {i + 1}/{n}: HTTP {r.status_code} · {classe}")
    console.print(f"\n{ok}/{n} triplas no livro (trace {trace_id[:8]}…)")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 10))
