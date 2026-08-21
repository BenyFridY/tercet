"""Fase 4 / T5 — os três formatos de recibo (D-27): emitir 1, ingerir 2. Tudo grátis.

1. **EMITIR `offer-and-receipt` oficial** (primeira implementação pública): sobre uma
   venda REAL nossa já liquidada no livro (nós somos o resource server dela; assinante
   = chave do payTo, o caminho simples do §4.5.1). Recibo verificado e gravado em
   `verification` (evidência, não booleano).
   *Correção de desenho registrada:* o doc da fase falava em emitir sobre as 13 compras
   do censo — mas o spec diz que quem assina é o VENDEDOR; nas compras do censo o
   vendedor são eles (e nenhum emite a extensão — achado do censo). Emitimos sobre a
   venda em que somos o vendedor.
2. **INGERIR MPP real**: o desafio `WWW-Authenticate: Payment` capturado AO VIVO do
   censo (dripstack fala MPP e x402 no mesmo endpoint) vira request+quote com
   rail='mpp' — o schema é agnóstico de trilho SEM migration.
3. **INGERIR AP2 sintético** (rotulado — D-12): um mandate de exemplo vira
   request+quote+authz com rail='ap2', rail_evidence marcada "sintetico".

Uso: uv run python scripts/fase4/formatos_run.py
"""

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from mesa import db, recibo_x402
from mesa.config import Settings
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
URL_BRINQUEDO = "http://127.0.0.1:8402/brinquedo"
CANDIDATOS = Path(__file__).resolve().parents[1] / "fase3" / "candidatos.json"


def emitir_oficial(conn: Any, s: Settings) -> None:
    """1 — emite o recibo oficial sobre uma venda liquidada em que SOMOS o vendedor."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT q.id, q.asset_network_caip2, q.pay_to, a.payer_ref, se.external_ref,"
            " r.resource_key_hash FROM quote q"
            " JOIN authz a ON a.quote_id = q.id"
            " JOIN settlement_leg sl ON sl.authorization_id = a.id"
            " JOIN settlement se ON se.id = sl.settlement_id"
            " JOIN request r ON r.id = q.request_id"
            " WHERE lower(q.pay_to) = lower(%s) AND r.transport = 'http'"
            " ORDER BY se.block_ts_utc DESC LIMIT 20",
            (s.seller_payto,),
        )
        vendas = cur.fetchall()
    # D-11: o livro só tem o hash — casamos com os canônicos CONHECIDOS do brinquedo
    # (a Fase 1 canonicalizava "GET <url>"; o censo usa a URL crua — aceitamos ambos)
    conhecidos = {hashlib.sha256(c.encode()).digest(): URL_BRINQUEDO
                  for c in (f"GET {URL_BRINQUEDO}", URL_BRINQUEDO)}
    venda = next((v for v in vendas if bytes(v[5]) in conhecidos), None)
    if venda is None:
        console.print("[yellow]1) nenhuma venda liquidada do brinquedo no livro — "
                      "pulando[/yellow]")
        return
    qid, network, pay_to, payer, tx, _rhash = venda

    artefato = recibo_x402.emitir_recibo(
        s.seller_pk.get_secret_value(), network=str(network), resource_url=URL_BRINQUEDO,
        payer=str(payer), issued_at=int(db.now_utc().timestamp()), transaction=str(tx))
    signer = recibo_x402.signatario(artefato)
    assert signer.lower() == str(pay_to).lower(), "signer != payTo (autorização §4.5.1)"

    db.insert_verification(
        conn, subject_type="delivery", subject_ref=f"quote:{qid}",
        method="x402-ext-offer-receipt/eip712", result="verified",
        evidence={"artefato": artefato, "signer": signer,
                  "regra_autorizacao": "signer==payTo (§4.5.1)",
                  "settlement_tx": str(tx)})
    console.print(f"1) recibo OFICIAL emitido e verificado — venda {str(tx)[:14]}…, "
                  f"signer==payTo ✓, gravado em verification")


def _parse_mpp(header: str) -> list[dict[str, Any]]:
    """Desafios `Payment k="v", ...` do WWW-Authenticate (múltiplos por header)."""
    desafios = []
    for bloco in re.split(r"(?:^|,\s*)Payment\s+", header):
        if not bloco.strip():
            continue
        params = dict(re.findall(r'(\w+)="([^"]*)"', bloco))
        if "request" in params:
            try:
                params["request_json"] = json.loads(base64.b64decode(
                    params["request"] + "=" * (-len(params["request"]) % 4)))
            except (ValueError, KeyError):
                params["request_json"] = None
        desafios.append(params)
    return desafios


def ingerir_mpp(conn: Any, tracer: Any) -> None:
    """2 — captura AO VIVO um desafio MPP do censo e ingere como rail='mpp'."""
    dados = json.loads(CANDIDATOS.read_text(encoding="utf-8"))
    alvo = next(c for c in dados["candidatos"] if c["dominio"] == "dripstack.xyz")
    with tracer.start_as_current_span("ingestao.mpp",
                                      attributes={"mpp.dominio": alvo["dominio"]}):
        trace_id, span_id = ids_do_span_atual()
        r = httpx.get(alvo["url"], timeout=15,
                      headers={"User-Agent": "mesa-censo/0.1 (format ingestion)"})
    header = r.headers.get("www-authenticate", "")
    desafios = [d for d in _parse_mpp(header) if d.get("request_json")]
    if not desafios:
        console.print("[yellow]2) fonte não devolveu desafio MPP legível — pulando[/yellow]")
        return
    d = next((x for x in desafios if x.get("method") == "tempo"), desafios[0])
    req = d["request_json"]
    chain_id = (req.get("methodDetails") or {}).get("chainId")

    rid = db.insert_request(
        conn, rail="mpp", resource_key_hash=hashlib.sha256(alvo["url"].encode()).digest(),
        method="GET", status_http=r.status_code, body_sha256=None, body_bytes=None,
        content_type=r.headers.get("content-type"), delivered=False,
        trace_id=trace_id, span_id=span_id, transport="http", origin="direct")
    db.insert_quote(
        conn, request_id=rid, amount_minor=int(req["amount"]), decimals=6,
        asset_network_caip2=f"eip155:{chain_id}" if chain_id else "mpp:desconhecida",
        asset_contract=str(req.get("currency", "")), pay_to=str(req.get("recipient", "")),
        scheme=f"mpp/{d.get('method', '?')}-{d.get('intent', '?')}")
    console.print(f"2) desafio MPP REAL ingerido (método {d.get('method')}, "
                  f"chain {chain_id}, amount {req['amount']}) — rail='mpp', sem migration")


def ingerir_ap2(conn: Any, tracer: Any, s: Settings) -> None:
    """3 — mandate AP2 SINTÉTICO (rotulado, D-12) vira tripla com rail='ap2'."""
    mandate = {  # forma do exemplo do spec AP2 (Google Agent Payments Protocol)
        "mandate_type": "intent",
        "user_ref": "did:example:usuario-demo",
        "merchant": "https://merchant.example/api",
        "max_amount": {"value": "5.00", "currency": "USD"},
        "expiry": "2026-09-01T00:00:00Z",
        "sintetico": True,
    }
    with tracer.start_as_current_span("ingestao.ap2-sintetico"):
        trace_id, span_id = ids_do_span_atual()
    rid = db.insert_request(
        conn, rail="ap2",
        resource_key_hash=hashlib.sha256(str(mandate["merchant"]).encode()).digest(),
        method="MANDATE", status_http=None, body_sha256=None, body_bytes=None,
        content_type=None, delivered=False, trace_id=trace_id, span_id=span_id,
        transport="function", origin="direct")
    qid = db.insert_quote(
        conn, request_id=rid, amount_minor=500, decimals=2,
        asset_network_caip2="fiat:USD", asset_contract="USD",
        pay_to=str(mandate["merchant"]), scheme="ap2/intent-mandate")
    db.insert_authz(
        conn, quote_id=qid, rail="ap2", payer_ref=str(mandate["user_ref"]),
        authorized_max_minor=500, valid_from_utc=None,
        valid_until_utc=None,
        rail_evidence={"ap2_mandate": mandate, "sintetico": True,
                       "fonte": "amostra construída a partir do spec AP2 (D-12: "
                                "proxy rotulado como proxy)"},
        state="authorized")
    console.print("3) mandate AP2 sintético (ROTULADO) ingerido — rail='ap2', "
                  "tripla completa, sem migration")


def main() -> None:
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)
    tracer = configurar_tracer(conn, "mesa-ingestao")
    emitir_oficial(conn, s)
    ingerir_mpp(conn, tracer)
    ingerir_ap2(conn, tracer, s)
    console.print("[bold green]T5: 1 formato emitido (oficial) + 2 ingeridos "
                  "(MPP real, AP2 sintético) — zero migrations novas[/bold green]")


if __name__ == "__main__":
    main()
