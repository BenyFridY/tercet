"""Fase 6 / T2 — GATE 6(a): o custo da compra aparece no painel, com o tx do lado.

Autossuficiente e 100% testnet (dinheiro de mentira):
1. sobe o Jaeger local se preciso (docker, grátis) e espera ficar de pé;
2. sobe o vendedor de brinquedo (porta 8402) como subprocesso;
3. compra 1× o /brinquedo (0,01 USDC de teste) com o seletor SEGURO da Fase 5,
   anota o span com `purchase.*` e grava a compra no livro como sempre;
4. pergunta à API do Jaeger (não a olho): existe o span com
   `purchase.settlement_ref`? — isso é o gate.

Uso: uv run python scripts/fase6/painel_run.py
"""

import asyncio
import hashlib
import subprocess
import sys
import time

import httpx
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from rich.console import Console
from x402.http.clients import x402HttpxClient
from x402.http.constants import PAYMENT_RESPONSE_HEADER

from mesa import checagens, db, exportador
from mesa.config import CAIP2_BASE_SEPOLIA, Settings
from mesa.http.buyer import Captured, make_client, record_purchase
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
JAEGER_UI = "http://localhost:16686"
OTLP = "http://localhost:4318"
SELLER = "http://127.0.0.1:8402"
SERVICO = "mesa-fase6"


def garantir_jaeger() -> None:
    """Jaeger de pé ou sobe via docker (mesmo runbook do Postgres)."""
    for tentativa in range(3):
        try:
            if httpx.get(f"{JAEGER_UI}/api/services", timeout=3).status_code == 200:
                console.print("[1/4] Jaeger de pé")
                return
        except httpx.HTTPError:
            pass
        if tentativa == 0:
            subprocess.run(["docker", "start", "mesa-jaeger"],
                           capture_output=True, text=True, check=False)
        elif tentativa == 1:
            console.print("    criando o container mesa-jaeger…")
            subprocess.run(
                ["docker", "run", "-d", "--name", "mesa-jaeger",
                 "--restart", "unless-stopped",
                 "-e", "COLLECTOR_OTLP_ENABLED=true",
                 "-p", "16686:16686", "-p", "4318:4318",
                 "jaegertracing/all-in-one:1.62.0"],
                capture_output=True, text=True, check=False)
        for _ in range(20):
            time.sleep(1.5)
            try:
                if httpx.get(f"{JAEGER_UI}/api/services", timeout=3).status_code == 200:
                    console.print("[1/4] Jaeger de pé")
                    return
            except httpx.HTTPError:
                continue
    raise SystemExit("Jaeger não subiu — Docker caiu? Runbook: abrir o Docker Desktop.")


def subir_vendedor() -> subprocess.Popen[bytes]:
    proc = subprocess.Popen(  # noqa: S603 — nosso próprio app, args fixos
        [sys.executable, "-m", "uvicorn", "mesa.http.seller:app",
         "--port", "8402", "--log-level", "warning"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.5)
        try:
            if httpx.get(f"{SELLER}/free-ride", timeout=2).status_code == 200:
                console.print("[2/4] vendedor de brinquedo de pé (8402)")
                return proc
        except httpx.HTTPError:
            continue
    proc.kill()
    raise SystemExit("vendedor não subiu em 20s")


async def comprar_e_anotar() -> tuple[str | None, str]:
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)
    tracer = configurar_tracer(conn, SERVICO, otlp_endpoint=OTLP)

    captured = Captured()
    seletor = checagens.seletor_com_checagens(  # Fase 5 no caminho, sempre
        CAIP2_BASE_SEPOLIA, teto_unverified_minor=1_000_000)
    xc = make_client(s, captured, seletor=seletor)
    canonical = f"GET {SELLER}/brinquedo"

    with tracer.start_as_current_span("fase6.tarefa-painel"), \
            tracer.start_as_current_span("compra.brinquedo"):
        trace_id, span_id = ids_do_span_atual()
        async with x402HttpxClient(xc, base_url=SELLER, timeout=120.0) as http:
            r = await http.get("/brinquedo")
            corpo = await r.aread()
        header = r.headers.get(PAYMENT_RESPONSE_HEADER)
        claim_tx = exportador.ref_da_alegacao(
            captured.settle_claim) if captured.settle_claim else None
        if claim_tx is None and header:
            import base64
            import json as _json
            claim_tx = exportador.ref_da_alegacao(
                _json.loads(base64.b64decode(header)))
        assert captured.payload is not None, "pagamento não aconteceu"
        exportador.anotar_span_compra(
            amount_minor=int(captured.req.get_amount()), decimals=6,
            currency="USDC", rail="x402", network=CAIP2_BASE_SEPOLIA,
            settlement_ref=claim_tx,
            resource_hash_hex=hashlib.sha256(canonical.encode()).hexdigest())

    classe = record_purchase(
        conn, captured=captured, canonical=canonical, trace_id=trace_id,
        span_id=span_id, status_http=r.status_code, content=corpo,
        content_type=r.headers.get("content-type"))
    console.print(f"[3/4] compra testnet feita ({classe}) · claim tx: "
                  f"{claim_tx[:18] if claim_tx else '—'}…")

    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    provider.force_flush()
    return claim_tx, trace_id


def conferir_no_jaeger(claim_tx: str | None) -> None:
    for _ in range(10):
        time.sleep(2)
        r = httpx.get(f"{JAEGER_UI}/api/traces",
                      params={"service": SERVICO, "limit": 20}, timeout=10)
        if r.status_code != 200:
            continue
        for trace_obj in r.json().get("data", []):
            for span in trace_obj.get("spans", []):
                tags = {t["key"]: t["value"] for t in span.get("tags", [])}
                # procura o span DESTA rodada (runs antigas também estão no Jaeger)
                if claim_tx and tags.get("purchase.settlement_ref") != claim_tx:
                    continue
                if "purchase.settlement_ref" in tags:
                    assert tags.get("purchase.rail") == "x402"
                    assert tags.get("purchase.currency") == "USDC"
                    console.print(
                        f"[4/4] Jaeger tem o span '{span['operationName']}' com "
                        f"purchase.amount={tags.get('purchase.amount')} e "
                        f"settlement_ref={str(tags['purchase.settlement_ref'])[:18]}…")
                    console.print(f"    veja no navegador: {JAEGER_UI}/search?service={SERVICO}")
                    console.print("[bold green]GATE 6(a) VERDE: o custo da compra está "
                                  "no painel, com a referência da liquidação[/bold green]")
                    return
    raise SystemExit("span da compra NÃO apareceu no Jaeger em 20s — investigar")


def main() -> None:
    garantir_jaeger()
    proc = subir_vendedor()
    try:
        claim_tx, _ = asyncio.run(comprar_e_anotar())
    finally:
        proc.kill()
    conferir_no_jaeger(claim_tx)


if __name__ == "__main__":
    main()
