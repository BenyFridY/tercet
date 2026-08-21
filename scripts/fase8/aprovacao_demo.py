"""Fase 8 — demo da aprovação vinculada (D-14). Testnet (dinheiro de mentira).

O vendedor local cobra 0,01 USDC de teste; o teto de aprovação é forçado em 0,001
para que ESTA compra precise de humano. O terminal pergunta; o "s" vale SÓ para a
cotação exata (hash) e entra no livro em authz.principal_ref/principal_evidence —
o blotter mostra o badge D-14 depois de regenerar as telas.

Uso (com o vendedor de pé em outro terminal — uv run uvicorn mesa.http.seller:app --port 8402):
  uv run python scripts/fase8/aprovacao_demo.py
Depois: uv run python scripts/fase8/telas_build.py   (a aprovação aparece na tela)
"""

import asyncio
import getpass
import sys
from typing import Any

from rich.console import Console
from x402.http.clients import x402HttpxClient

from mesa import aprovacao, checagens, db, rede_segura
from mesa.config import CAIP2_BASE_SEPOLIA, Settings
from mesa.http.buyer import Captured, make_client, record_purchase
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
SELLER = "http://127.0.0.1:8402"
TETO_APROVACAO = 1_000  # 0,001 USDC — de propósito ABAIXO do preço do brinquedo


def perguntar_no_terminal(quem: str) -> Any:
    """O callback humano (padrão input_required do MCP, D-30 — no v0, o terminal)."""
    def callback(cotacao: dict[str, Any]) -> Any:
        console.print(f"\n[bold yellow]COMPRA ACIMA DO TETO DE APROVAÇÃO "
                      f"(US$ {TETO_APROVACAO / 1e6:.4f}):[/bold yellow]")
        console.print(f"  pagar US$ {cotacao['amount_minor'] / 1e6:.4f} "
                      f"para {cotacao['pay_to'][:14]}… na rede {cotacao['network']}")
        console.print(f"  escopo (o hash que o seu 'sim' assina): "
                      f"{cotacao['escopo_hex'][:20]}…")
        resposta = input("  aprovar ESTA cotação? [s/N] ").strip().lower()
        return aprovacao.aprovar(cotacao["escopo_hex"], quem, resposta == "s")
    return callback


async def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit("demo interativa: a aprovação é do HUMANO — rode num terminal")
    quem = getpass.getuser()
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)
    tracer = configurar_tracer(conn, "demo-aprovacao-d14")

    captured = Captured()
    ultima: dict[str, Any] = {}

    def callback_gravando(cotacao: dict[str, Any]) -> Any:
        decisao = perguntar_no_terminal(quem)(cotacao)
        ultima["aprovacao"] = decisao
        return decisao

    seletor = checagens.seletor_com_checagens(
        CAIP2_BASE_SEPOLIA, teto_unverified_minor=1_000_000,
        teto_aprovacao_minor=TETO_APROVACAO, pedir_aprovacao=callback_gravando)
    xc = make_client(s, captured, seletor=seletor)
    canonical = f"GET {SELLER}/brinquedo"

    with tracer.start_as_current_span("demo.aprovacao-vinculada"):
        trace_id, span_id = ids_do_span_atual()
        try:
            async with x402HttpxClient(xc, base_url=SELLER, timeout=120.0) as http, \
                    http.stream("GET", "/brinquedo") as r:
                corpo, _trunc = await rede_segura.ler_corpo_limitado_async(r)
            status: int | None = r.status_code
            ctype = r.headers.get("content-type")
        except Exception as e:  # recusa (sem aprovação) também é resultado
            console.print(f"[yellow]compra NÃO aconteceu (fail-closed): {e}[/yellow]")
            return

    classe = record_purchase(
        conn, captured=captured, canonical=canonical, trace_id=trace_id,
        span_id=span_id, status_http=status, content=corpo, content_type=ctype,
        aprovacao=ultima.get("aprovacao"))
    console.print(f"\ncompra aprovada e gravada ({classe}) — aprovador "
                  f"[bold]{quem}[/bold] vinculado à cotação no livro "
                  f"(authz.principal_evidence).")
    console.print("regenerar as telas: uv run python scripts/fase8/telas_build.py")


if __name__ == "__main__":
    asyncio.run(main())
