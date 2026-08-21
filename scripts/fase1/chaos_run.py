"""T5 — o GATE 1: ~pagamentos com erros DE PROPÓSITO, e o livro tem que explicar cada um.

Tabela-oráculo (PLANO, refinada pela Tarefa 0 — o SDK é serve-then-settle e não liquida
em resposta de erro):

  cenário                     | induzido como                          | veredito esperado
  ----------------------------+----------------------------------------+---------------------------
  normal (x6)                 | GET /brinquedo                         | ok
  free-ride (x2)              | GET /free-ride (rota sem x402)         | uncollected
  fail-handler (x2)           | header x-chaos: fail-handler           | autorizada-sem-liquidacao
  kill-after-settle (x2)      | header x-chaos: kill-after-settle      | pago-sem-entrega
  replay cru (x1)             | reenviar PAYMENT-SIGNATURE via httpx   | replay-extra
  compra não instrumentada(x1)| pagar sem gravar no livro              | orfao-chain (novo)

Mais o legado: 10 ok da T3 e 2 orfao-chain da T2 (pagamentos anteriores ao livro).
GATE: os vereditos batem EXATAMENTE com o esperado — como assert, não olhômetro.
"""

import asyncio
import copy
import uuid

import httpx
from rich.console import Console
from x402.http.clients import x402HttpxClient
from x402.http.constants import PAYMENT_SIGNATURE_HEADER
from x402.http.utils import encode_payment_signature_header

from mesa import collector, db
from mesa.config import Settings
from mesa.http.buyer import Captured, make_client, record_purchase
from mesa.reconcile import Veredito, carregar, reconciliar

console = Console()
BASE = "http://127.0.0.1:8402"


async def main() -> None:
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)

    trace_id = uuid.uuid4().hex
    root_span = uuid.uuid4().hex[:16]
    db.insert_span(
        conn, trace_id=trace_id, span_id=root_span, parent_span_id=None,
        name="mesa.fds1.chaos", agent_ref="chaos-script",
        attributes={"tarefa": "t5-gate1"}, started_utc=db.now_utc(),
    )

    captured = Captured()
    xc = make_client(s, captured)
    replay_material: Captured | None = None

    async def compra(path: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
        nonlocal replay_material
        captured.reset()
        try:
            r = await http.get(path, headers=headers)
            status: int | None = r.status_code
            content, ctype = r.content, r.headers.get("content-type")
        except (httpx.HTTPError, RuntimeError) as exc:
            console.print(f"    (transporte falhou, registrando mesmo assim: {type(exc).__name__})")
            status, content, ctype = None, None, None
        classe = record_purchase(
            conn, captured=captured, canonical=f"GET {BASE}{path}",
            trace_id=trace_id, span_id=root_span,
            status_http=status, content=content, content_type=ctype,
        )
        if path == "/brinquedo" and headers is None and captured.payload is not None:
            replay_material = copy.copy(captured)  # guarda um pagamento OK para o replay
        console.print(f"    HTTP {status} · gravado: {classe}")
        return (status or 0), (content or b"")

    async with x402HttpxClient(xc, base_url=BASE, timeout=120.0) as http:
        console.print("[bold]1/6[/] 6 pagamentos normais")
        for _ in range(6):
            await compra("/brinquedo")

        console.print("[bold]2/6[/] 2 free-rides (rota sem x402 — vendedor entrega sem cobrar)")
        for _ in range(2):
            await compra("/free-ride")

        console.print("[bold]3/6[/] 2 fail-handler (paga, handler quebra; SDK NÃO liquida)")
        for _ in range(2):
            await compra("/brinquedo", headers={"x-chaos": "fail-handler"})

        console.print("[bold]4/6[/] 2 kill-after-settle (liquida e a resposta morre)")
        for _ in range(2):
            await compra("/brinquedo", headers={"x-chaos": "kill-after-settle"})

    console.print("[bold]5/6[/] replay cru: reenviando a MESMA autorização, sem SDK")
    assert replay_material is not None and replay_material.payload is not None
    header = encode_payment_signature_header(replay_material.payload)
    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as raw:
        r = await raw.get("/brinquedo", headers={PAYMENT_SIGNATURE_HEADER: header})
    record_purchase(
        conn, captured=replay_material, canonical=f"GET {BASE}/brinquedo",
        trace_id=trace_id, span_id=root_span,
        status_http=r.status_code, content=r.content,
        content_type=r.headers.get("content-type"),
    )
    console.print(f"    HTTP {r.status_code} · segunda authz com o MESMO nonce gravada")

    console.print("[bold]6/6[/] 1 compra NÃO instrumentada (paga de verdade, livro não vê)")
    fantasma = Captured()
    xc2 = make_client(s, fantasma)
    async with x402HttpxClient(xc2, base_url=BASE, timeout=120.0) as http2:
        r2 = await http2.get("/brinquedo")
    console.print(f"    HTTP {r2.status_code} · NADA gravado de propósito")

    console.print("\naguardando blocos e rodando o coletor…")
    await asyncio.sleep(6)
    collector.main(500)

    compras, liquidacoes = carregar(conn)
    resultado = reconciliar(compras, liquidacoes)
    contagem = {v: len(rows) for v, rows in resultado.items()}
    console.print(f"\nvereditos: { {k.value: v for k, v in contagem.items()} }")

    esperado: dict[Veredito, int] = {
        Veredito.OK: 16,                        # 10 da T3 + 6 normais de agora
        Veredito.UNCOLLECTED: 2,                # free-rides
        Veredito.AUTORIZADA_SEM_LIQUIDACAO: 2,  # fail-handler (SDK não liquida em erro)
        Veredito.PAGO_SEM_ENTREGA: 2,           # kill-after-settle
        Veredito.REPLAY_EXTRA: 1,               # o reenvio cru
        Veredito.FALHOU_SEM_PAGAR: 0,
        Veredito.ORFAO_CHAIN: 3,                # 2 da T2 (pré-livro) + 1 não instrumentada
    }
    falhas = [
        f"{v.value}: esperado {n}, veio {contagem[v]}"
        for v, n in esperado.items() if contagem[v] != n
    ]
    if falhas:
        console.print(f"\n[bold red]GATE 1 VERMELHO[/] — {falhas}")
        raise SystemExit(1)
    console.print(
        "\n[bold green]GATE 1 VERDE[/] — todo órfão tem um cenário que o explica, "
        "e todo cenário produziu o órfão previsto. O livro fecha com dado sujo."
    )


if __name__ == "__main__":
    asyncio.run(main())
