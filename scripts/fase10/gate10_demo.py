"""Fase 10 — GATE 10: o ciclo completo do passaporte, com dado real e dinheiro de teste.

O que este script prova, em ordem (cada passo é um assert — se algo divergir, quebra):

1. EMISSÃO dos 3 passaportes reais do livro (caos/testnet, mcp/testnet, censo/mainnet),
   com atribuição on-chain das liquidações sem par.
2. A POLÍTICA do vendedor, offline: caos RECUSADO (nonce reusado + órfãos), mcp
   RECUSADO (1 órfão — o achado da fase), censo ACEITO.
3. O CICLO ao vivo na testnet: sem passaporte → 403; passaporte recusado → 403 com
   motivos; prova de posse de ladrão de arquivo → 403; passaporte aceito → o vendedor
   MUDA OS TERMOS e vende o /lote de 0,10 USDC — e a compra cai no livro.
4. O LIVRO FECHA: coletor casa as compras novas por (authorizer, nonce).

Custo: ~1,00 USDC de TESTE (recarga de 0,90 para a carteira do censo na Sepolia +
0,10 do lote). Dinheiro real: zero. A recarga é 0,90 DE PROPÓSITO: o spend_controls
do próprio SDK recusa >US$1/pagamento por padrão, e a demo respeita a trava em vez
de desligá-la (a primeira rodada bateu nela — bom sinal, ficou registrado).

Uso: uv run python scripts/fase10/gate10_demo.py
"""

import asyncio
import base64
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI
from rich.console import Console
from web3 import Web3
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.clients import x402HttpxClient
from x402.http.middleware.fastapi import payment_middleware
from x402.http.types import PaymentOption, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from mesa import checagens, collector, db, rede_segura
from mesa import passaporte as pp
from mesa.config import CAIP2_BASE_MAINNET, CAIP2_BASE_SEPOLIA, USDC_BASE_SEPOLIA, Settings
from mesa.http.buyer import Captured, make_client, record_purchase
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
SAIDA = Path(__file__).parent / "saida"
LOTE = "http://127.0.0.1:8410"
RECARGA = "http://127.0.0.1:8411"
RECARGA_MINOR = 900_000     # 0,90 de teste (< teto de $1/pagamento do SDK) — ~9 lotes
LOTE_MINOR = 100_000        # o teto maior: 0,10 (o varejo é 0,01)


def _b64(obj: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


def _headers_portador(artefato: dict[str, Any], pk: str, rota: str) -> dict[str, str]:
    prova = pp.prova_de_posse(pk, passaporte_hash_hex=pp.passaporte_hash(
        artefato["payload"]), rota=rota, ts_unix=int(time.time()))
    return {"x-passaporte": _b64(artefato), "x-passaporte-prova": _b64(prova)}


def _app_recarga(payto: str, facilitator_url: str) -> FastAPI:
    """Vendedor descartável cuja única função é o payTo ser a carteira do censo:
    a recarga é uma compra x402 NORMAL — o facilitator paga o gas, o livro registra."""
    app = FastAPI(title="recarga")
    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=facilitator_url))
    rs = x402ResourceServer(facilitator)
    rs.register(CAIP2_BASE_SEPOLIA, ExactEvmServerScheme())  # type: ignore[no-untyped-call]
    mw = payment_middleware({"GET /recarga": RouteConfig(accepts=PaymentOption(
        scheme="exact", pay_to=payto, price="$0.90", network=CAIP2_BASE_SEPOLIA))}, rs)
    app.middleware("http")(mw)

    @app.get("/recarga")
    async def recarga() -> dict[str, Any]:
        return {"produto": "recarga de USDC de teste", "entregue": True}
    return app


def _subir(app: Any, porta: int) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta,
                                           log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(60):
        try:
            httpx.get(f"http://127.0.0.1:{porta}/openapi.json", timeout=1.0)
            return
        except httpx.HTTPError:
            time.sleep(0.25)
    raise SystemExit(f"servidor na porta {porta} não subiu")


async def _comprar(s: Settings, conn: Any, tracer: Any, *, base_url: str, rota: str,
                   pk: str | None, teto_minor: int, span_nome: str,
                   headers: dict[str, str] | None = None) -> tuple[int | None, str]:
    """Uma compra x402 instrumentada — o mesmo caminho de qualquer compra do livro."""
    captured = Captured()
    seletor = checagens.seletor_com_checagens(CAIP2_BASE_SEPOLIA,
                                              teto_unverified_minor=teto_minor)
    xc = make_client(s, captured, pk=pk, seletor=seletor)
    with tracer.start_as_current_span(span_nome):
        trace_id, span_id = ids_do_span_atual()
        async with x402HttpxClient(xc, base_url=base_url, timeout=180.0,
                                   headers=headers or {}) as http, \
                http.stream("GET", rota) as r:
            corpo, _trunc = await rede_segura.ler_corpo_limitado_async(r)
        status: int | None = r.status_code
        ctype = r.headers.get("content-type")
    classe = record_purchase(conn, captured=captured, canonical=f"GET {base_url}{rota}",
                             trace_id=trace_id, span_id=span_id, status_http=status,
                             content=corpo, content_type=ctype)
    return status, classe


async def main() -> None:
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)
    SAIDA.mkdir(exist_ok=True)
    w3_sep = Web3(Web3.HTTPProvider(s.rpc_url))
    w3_main = Web3(Web3.HTTPProvider(s.rpc_url_mainnet))
    agora = datetime.now(UTC)
    tracer = configurar_tracer(conn, "fase10-demo")  # UMA vez — provider global do otel

    # ---------------------------------------------- 1. emissão dos 3 passaportes reais
    console.rule("1. emissão (do livro + atribuição on-chain)")
    carteiras = [
        ("caos", s.buyer_address, CAIP2_BASE_SEPOLIA, w3_sep,
         s.buyer_pk.get_secret_value()),
        ("mcp", s.mcp_server_address, CAIP2_BASE_SEPOLIA, w3_sep,
         s.mcp_server_pk.get_secret_value()),
        ("censo", s.census_address, CAIP2_BASE_MAINNET, w3_main,
         s.census_pk.get_secret_value()),
    ]
    passaportes: dict[str, dict[str, Any]] = {}
    for nome, addr, rede, w3, pk in carteiras:
        art = pp.emitir(conn, w3, payer_ref=addr, rede=rede, pk=pk)
        passaportes[nome] = art
        (SAIDA / f"passaporte-{nome}.json").write_text(
            json.dumps(art, indent=2, ensure_ascii=False), encoding="utf-8")
        m = art["payload"]["metricas"]
        console.print(f"[bold]{nome}[/bold] ({addr[:10]}…, {rede}): "
                      f"{m['autorizacoes']} aut · {m['liquidadas']} liq · "
                      f"{m['nonces_reusados']} nonce reusado · "
                      f"{m['orfaos_chain_inexplicados']} órfã(s)")

    # ------------------------------------------------- 2. a política, offline
    console.rule("2. a política do vendedor (offline)")
    esperado = {"caos": (False, {"nonce-reusado", "liquidacao-fora-do-livro"}),
                "mcp": (False, {"liquidacao-fora-do-livro"}),
                "censo": (True, set())}
    for nome, art in passaportes.items():
        assert pp.verificar_offline(art) == [], f"{nome}: documento inválido?!"
        aceito, motivos = pp.avaliar_politica(art, pp.Politica(), agora)
        ok_esp, motivos_esp = esperado[nome]
        assert aceito == ok_esp and set(motivos) == motivos_esp, \
            f"{nome}: esperava {esperado[nome]}, veio {(aceito, motivos)}"
        veredito = "[green]ACEITO[/green]" if aceito else f"[red]RECUSADO[/red] {motivos}"
        console.print(f"{nome}: {veredito}")
    console.print("[dim]o passaporte é honesto: reprova a carteira do próprio dono[/dim]")

    # ------------------------------------------------- 3. o ciclo ao vivo (testnet)
    console.rule("3. o ciclo ao vivo — o vendedor muda os termos")
    from vendedor_lote import app as app_lote  # irmão de diretório (sys.path[0])
    _subir(app_lote, 8410)
    _subir(_app_recarga(s.census_address, s.facilitator_url), 8411)

    censo_pk = s.census_pk.get_secret_value()
    abi = [{"name": "balanceOf", "type": "function", "stateMutability": "view",
            "inputs": [{"name": "a", "type": "address"}],
            "outputs": [{"name": "", "type": "uint256"}]}]
    usdc = w3_sep.eth.contract(address=Web3.to_checksum_address(USDC_BASE_SEPOLIA), abi=abi)
    saldo = int(usdc.functions.balanceOf(
        Web3.to_checksum_address(s.census_address)).call())
    if saldo < LOTE_MINOR:
        console.print(f"censo tem {saldo} na Sepolia — recarga de 0,90 via compra x402")
        status, classe = await _comprar(
            s, conn, tracer, base_url=RECARGA, rota="/recarga", pk=None,
            teto_minor=RECARGA_MINOR + 1, span_nome="fase10.recarga")
        assert status == 200 and classe == "tripla", f"recarga falhou: {status}/{classe}"
        console.print("[green]recarga entregue e no livro[/green]")

    async with httpx.AsyncClient(base_url=LOTE, timeout=30.0) as cru:
        r1 = await cru.get("/lote")
        assert r1.status_code == 403 and r1.json()["erro"] == "sem-passaporte", r1.text
        console.print("sem passaporte → [red]403 sem-passaporte[/red] (antes de cobrar)")

        r2 = await cru.get("/lote", headers=_headers_portador(
            passaportes["caos"], s.buyer_pk.get_secret_value(), "/lote"))
        assert r2.status_code == 403 and r2.json()["erro"] == "recusado-pela-politica", r2.text
        console.print(f"passaporte do caos → [red]403[/red] {r2.json()['motivos']}")

        r3 = await cru.get("/lote", headers=_headers_portador(
            passaportes["censo"], s.buyer_pk.get_secret_value(), "/lote"))
        assert r3.status_code == 403 and r3.json()["erro"] == "prova-de-posse-invalida", r3.text
        console.print("passaporte do censo + chave ERRADA (ladrão de arquivo) → "
                      "[red]403 prova-de-posse-invalida[/red]")

    status, classe = await _comprar(
        s, conn, tracer, base_url=LOTE, rota="/lote", pk=censo_pk,
        teto_minor=LOTE_MINOR + 1, span_nome="fase10.lote",
        headers=_headers_portador(passaportes["censo"], censo_pk, "/lote"))
    assert status == 200 and classe == "tripla", f"lote falhou: {status}/{classe}"
    console.print("[green]passaporte do censo + posse → 200: o lote de 0,10 foi "
                  "VENDIDO — termos mudados pelo passaporte[/green]")

    # ------------------------------------------------- 4. o livro fecha
    console.rule("4. o coletor casa as compras novas")
    time.sleep(5)
    collector.main(400)                                       # o lote (payTo = seller)
    collector.main(400, payto=s.census_address,               # a recarga (payTo = censo)
                   cursor="base-sepolia-usdc-recarga")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM authz a JOIN quote q ON q.id = a.quote_id
            JOIN request r ON r.id = q.request_id
            LEFT JOIN settlement_leg l ON l.authorization_id = a.id
            WHERE r.ts_utc >= %s AND l.authorization_id IS NULL
        """, (agora,))
        row = cur.fetchone()
        assert row is not None and int(row[0]) == 0, \
            f"{row and row[0]} compra(s) da demo sem liquidação casada"
    console.print("[green]toda compra da demo está liquidada e casada por "
                  "(authorizer, nonce)[/green]")
    console.rule("[bold green]GATE 10 — ciclo completo demonstrado[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
