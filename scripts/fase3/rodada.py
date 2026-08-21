"""Fase 3 / T4 — a rodada PAGA do censo. 💰 SÓ RODA COM O "VAI" EXPLÍCITO DO BENY.

Sem o argumento --vai o script é um ensaio: mostra o que compraria e quanto custaria,
e PARA. Com --vai, compra 1× de cada fonte aprovada na sondagem.

Os tetos são DUROS e moram NO SELETOR do SDK — a função que escolhe qual cotação
aceitar roda ANTES de qualquer assinatura. Se nenhum aceite couber nos tetos
(US$ 1/compra, US$ 20/rodada, USDC canônico, Base mainnet, exact), o seletor levanta
exceção e a compra daquela fonte simplesmente não acontece (fail-closed).

O payload comprado NUNCA é executado: só hash + tamanho + content-type no livro (D-11).
Falha no meio da rodada não derruba o resto: cada fonte vira resultado, inclusive
"pagou-sem-entrega" — que é exatamente o número 3 do censo medindo o que promete.

Uso: uv run python scripts/fase3/rodada.py          (ensaio, não gasta)
     uv run python scripts/fase3/rodada.py --vai    (a rodada real)
"""

import asyncio
import base64
import binascii
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eth_account import Account
from rich.console import Console
from rich.table import Table
from web3 import Web3
from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.http.constants import PAYMENT_RESPONSE_HEADER
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmClientScheme

from mesa import db
from mesa.config import (
    CAIP2_BASE_MAINNET,
    CENSO_TETO_POR_COMPRA_MINOR,
    CENSO_TETO_RODADA_MINOR,
    USDC_BASE_MAINNET,
    Settings,
)
from mesa.http.buyer import Captured, record_purchase
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
DIR = Path(__file__).parent
SONDAGEM = DIR / "sondagem_resultado.json"
CANDIDATOS = DIR / "candidatos.json"
SAIDA = DIR / "rodada_resultado.json"


class Orcamento:
    """O teto da rodada como estado vivo: o seletor consulta ANTES de cada assinatura."""

    def __init__(self, teto_minor: int) -> None:
        self.teto = teto_minor
        self.gasto = 0

    def cabe(self, valor: int) -> bool:
        return valor <= CENSO_TETO_POR_COMPRA_MINOR and self.gasto + valor <= self.teto

    def debitar(self, valor: int) -> None:
        self.gasto += valor


def make_cliente_censo(settings: Settings, captured: Captured,
                       orcamento: Orcamento) -> x402Client:
    """Cliente x402 do censo: mainnet + seletor com os tetos DENTRO (fail-closed)."""

    def seletor(_version: int, requirements: list[Any]) -> Any:
        for req in requirements:
            if str(req.network) != CAIP2_BASE_MAINNET:
                continue
            if str(req.scheme).lower() != "exact":
                continue
            if str(req.asset).lower() != USDC_BASE_MAINNET.lower():
                continue
            if not orcamento.cabe(int(req.get_amount())):
                continue
            return req
        raise ValueError("nenhum aceite dentro dos tetos do censo — compra abortada")

    signer = EthAccountSigner(Account.from_key(settings.census_pk))
    xc = x402Client(payment_requirements_selector=seletor)
    xc.register(CAIP2_BASE_MAINNET, ExactEvmClientScheme(signer))

    def after_creation(ctx: Any) -> None:
        captured.req = ctx.selected_requirements
        captured.payload = ctx.payment_payload

    def on_response(ctx: Any) -> None:
        captured.settle_claim = (
            ctx.settle_response.model_dump() if ctx.settle_response is not None else None
        )

    xc.on_after_payment_creation(after_creation)
    xc.on_payment_response(on_response)
    return xc


def _saldo_usdc(settings: Settings) -> int:
    w3 = Web3(Web3.HTTPProvider(settings.rpc_url_mainnet))
    abi = [{"name": "balanceOf", "inputs": [{"type": "address"}],
            "outputs": [{"type": "uint256"}], "stateMutability": "view",
            "type": "function"}]
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_BASE_MAINNET), abi=abi)
    return int(usdc.functions.balanceOf(
        Web3.to_checksum_address(settings.census_address)).call())


def _settle_claim_do_header(r: Any) -> dict[str, Any] | None:
    header = r.headers.get(PAYMENT_RESPONSE_HEADER)
    if not header:
        return None
    try:
        decodificado = json.loads(base64.b64decode(header))
        return decodificado if isinstance(decodificado, dict) else None
    except (ValueError, binascii.Error):
        return None


async def _comprar(settings: Settings, orcamento: Orcamento,
                   fonte: dict[str, Any], corpo_exemplo: dict[str, Any] | None,
                   ) -> tuple[Captured, dict[str, Any]]:
    """UMA compra. Devolve (captured, resultado-parcial). Nunca levanta."""
    captured = Captured()
    metodo = str(fonte.get("metodo") or "GET")
    try:
        xc = make_cliente_censo(settings, captured, orcamento)
        async with x402HttpxClient(xc, timeout=90.0) as http:
            if metodo == "GET":
                r = await http.get(fonte["url"])
            else:
                r = await http.request(metodo, fonte["url"], json=corpo_exemplo or {})
            conteudo = await r.aread()
        return captured, {
            "status": r.status_code, "conteudo": conteudo,
            "content_type": r.headers.get("content-type"),
            "settle_claim_header": _settle_claim_do_header(r), "erro": None,
        }
    except Exception as e:  # noqa: BLE001 — fonte externa: QUALQUER falha vira resultado
        return captured, {"status": None, "conteudo": None, "content_type": None,
                          "settle_claim_header": None,
                          "erro": f"{type(e).__name__}: {e}"}


async def main() -> None:
    vai = "--vai" in sys.argv
    settings = Settings()
    if not settings.census_pk:
        raise SystemExit("CENSUS_PK ausente — rodar a T1 primeiro")

    aprovadas = [r for r in json.loads(SONDAGEM.read_text(encoding="utf-8"))["resultados"]
                 if r["cotacao_valida"]]
    corpos = {c["dominio"]: c.get("corpo_exemplo")
              for c in json.loads(CANDIDATOS.read_text(encoding="utf-8"))["candidatos"]}
    estimado = sum(r["preco_cotado_minor"] for r in aprovadas)

    saldo = _saldo_usdc(settings)
    console.print(f"fontes aprovadas: {len(aprovadas)} · estimado: US$ {estimado / 1e6:.4f}"
                  f" · teto da rodada: US$ {CENSO_TETO_RODADA_MINOR / 1e6:.2f}"
                  f" · saldo da carteira: US$ {saldo / 1e6:.2f}")
    if saldo < estimado:
        raise SystemExit("saldo insuficiente para o estimado — financiar antes da rodada")
    if not vai:
        console.print("[yellow]ENSAIO (sem --vai): nada foi comprado. A lista acima é o "
                      "que a rodada faria.[/yellow]")
        return

    conn = db.connect()
    db.apply_migrations(conn)
    tracer = configurar_tracer(conn, "mesa-censo")
    orcamento = Orcamento(CENSO_TETO_RODADA_MINOR)

    # Cada compra é gravada no livro ASSIM que o span dela fecha (a FK request→span
    # só precisa da linha do span FILHO, que o processor insere no fim do `with`).
    # Se o processo morrer no meio, perdemos no máximo a compra em voo — nunca
    # compras já feitas. (A raiz entra no fim; compra nunca pendura na raiz.)
    resultados: list[dict[str, Any]] = []
    with tracer.start_as_current_span("censo.rodada1"):
        for fonte in aprovadas:
            with tracer.start_as_current_span(
                "censo.compra", attributes={"censo.dominio": fonte["dominio"]}
            ):
                trace_id, span_id = ids_do_span_atual()
                captured, res = await _comprar(
                    settings, orcamento, fonte, corpos.get(fonte["dominio"]))
                if captured.payload is not None:  # assinou => o valor conta no teto
                    orcamento.debitar(int(captured.req.get_amount()))
            # aqui o span filho JÁ está no banco — pode gravar a compra
            classe = record_purchase(
                conn, captured=captured, canonical=fonte["url"],
                trace_id=trace_id, span_id=span_id, status_http=res["status"],
                content=res["conteudo"], content_type=res["content_type"],
                method=str(fonte.get("metodo") or "GET"),
            )
            entregue = res["status"] == 200 and bool(res["conteudo"])
            resultados.append({
                "dominio": fonte["dominio"], "url": fonte["url"],
                "classe_no_livro": classe,
                "pagou": captured.payload is not None,
                "valor_pago_minor": (int(captured.req.get_amount())
                                     if captured.req is not None else None),
                "entregue": entregue,
                "status_http": res["status"],
                "bytes": len(res["conteudo"]) if res["conteudo"] else 0,
                "content_type": res["content_type"],
                "settle_claim_presente": res["settle_claim_header"] is not None,
                "erro": res["erro"],
            })
            console.print(
                f"  {fonte['dominio']}: status={res['status']} "
                f"pagou={'sim' if captured.payload is not None else 'não'} "
                f"entregou={'sim' if entregue else 'não'} "
                f"gasto acumulado US$ {orcamento.gasto / 1e6:.4f}"
                + (f" [red]{res['erro']}[/red]" if res["erro"] else "")
            )

    SAIDA.write_text(json.dumps({
        "gerado_utc": datetime.now(UTC).isoformat(),
        "gasto_total_minor": orcamento.gasto,
        "teto_rodada_minor": CENSO_TETO_RODADA_MINOR,
        "resultados": resultados,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    t = Table(title="rodada 1 do censo — o que aconteceu quando PAGAMOS")
    t.add_column("domínio")
    t.add_column("pagou US$", justify="right")
    t.add_column("entregou?")
    t.add_column("status")
    t.add_column("obs")
    for r in resultados:
        t.add_row(
            r["dominio"],
            f"{r['valor_pago_minor'] / 1e6:.4f}" if r["valor_pago_minor"] else "—",
            "sim" if r["entregue"] else ("[red]NÃO[/red]" if r["pagou"] else "não"),
            str(r["status_http"]),
            (r["erro"] or "")[:60],
        )
    console.print(t)
    pagaram = [r for r in resultados if r["pagou"]]
    console.print(
        f"[bold]{len(pagaram)} compras · gasto total US$ {orcamento.gasto / 1e6:.4f} "
        f"(teto US$ {CENSO_TETO_RODADA_MINOR / 1e6:.2f}) · "
        f"{sum(1 for r in resultados if r['entregue'])} entregaram[/bold]"
    )
    console.print(f"gravado em {SAIDA} — próximo: coletor mainnet (T5) confirma na chain")


if __name__ == "__main__":
    asyncio.run(main())
