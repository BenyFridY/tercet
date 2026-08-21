"""Fase 3 / T3 — sondagem: bater em cada candidato SEM pagar. 100% grátis.

Mede os números 1 e 2 do censo (fase3.md):
1. **Responde?** — requisição simples; o esperado é o "pague primeiro" (HTTP 402).
2. **Aceita pagamento?** — a cotação devolvida é válida? (USDC canônico da Base
   mainnet, esquema exact, payTo endereço EVM plausível, valor > 0 e ≤ US$ 1)

Lição da 1ª rodada (21/08): no wire V2 sobre HTTP a cotação vem no HEADER
`payment-required` (JSON em base64), não no corpo — que costuma ser `{}`. O corpo
com `accepts` é o wire v1. A sonda lê o header PRIMEIRO e cai pro corpo. E o
método HTTP vem do índice (fontes POST-only respondem 405 ao GET).

Tudo entra no LIVRO como qualquer requisição (request sem pagamento; quote quando a
cotação é válida), pendurado em spans reais — o censo é uma tarefa como outra
qualquer. Deriva de preço (cotado ≠ anunciado no índice) é ACHADO, não erro.

Saída: scripts/fase3/sondagem_resultado.json + relatório parcial no console —
é ESTE relatório que o Beny olha antes do "vai" da rodada paga (T4).

Uso: uv run python scripts/fase3/sondagem.py
"""

import base64
import binascii
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.table import Table

from mesa import db
from mesa.config import CENSO_TETO_POR_COMPRA_MINOR, USDC_BASE_MAINNET
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
CANDIDATOS = Path(__file__).parent / "candidatos.json"
SAIDA = Path(__file__).parent / "sondagem_resultado.json"
REDES_BASE_MAINNET = {"base", "eip155:8453"}
UA = "mesa-censo/0.1 (x402 buyer census; measurement only)"
ENDERECO_EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _cotacao_valida(corpo: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Procura um aceite pagável nos nossos termos; devolve (aceite, motivo_se_nao)."""
    aceites = corpo.get("accepts")
    if not isinstance(aceites, list) or not aceites:
        return None, "402-sem-accepts"
    motivo = "sem-aceite-base-mainnet"
    for aceite in aceites:
        if not isinstance(aceite, dict):
            continue
        if str(aceite.get("network", "")).lower() not in REDES_BASE_MAINNET:
            continue
        if str(aceite.get("scheme", "")).lower() != "exact":
            motivo = "esquema-nao-exact"
            continue
        if str(aceite.get("asset", "")).lower() != USDC_BASE_MAINNET.lower():
            motivo = "asset-nao-canonico"
            continue
        try:
            preco = int(str(aceite.get("maxAmountRequired", aceite.get("amount"))))
        except (ValueError, TypeError):
            motivo = "preco-ilegivel"
            continue
        if preco <= 0:
            motivo = "preco-zero"
            continue
        if preco > CENSO_TETO_POR_COMPRA_MINOR:
            motivo = "acima-do-teto-usd1"
            continue
        if not ENDERECO_EVM.match(str(aceite.get("payTo", ""))):
            motivo = "payto-invalido"
            continue
        return aceite, ""
    return None, motivo


def _cotacao_do_402(r: httpx.Response) -> dict[str, Any] | None:
    """V2: header `payment-required` em base64. V1: corpo JSON. Nesta ordem."""
    header = r.headers.get("payment-required")
    if header:
        try:
            decodificado = json.loads(base64.b64decode(header))
            if isinstance(decodificado, dict) and "accepts" in decodificado:
                return decodificado
        except (ValueError, binascii.Error):
            pass
    try:
        parsed = r.json()
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, UnicodeDecodeError):
        pass
    return None


def _sondar(cli: httpx.Client, c: dict[str, Any]) -> dict[str, Any]:
    """Uma sondagem SEM pagamento, com o método do índice. Nunca levanta."""
    metodo = c.get("metodo") or "GET"
    try:
        if metodo == "GET":
            r = cli.get(c["url"])
        else:  # POST/PUT/PATCH: corpo de exemplo do índice (o 402 vem ANTES de executar)
            r = cli.request(metodo, c["url"], json=c.get("corpo_exemplo") or {})
    except httpx.HTTPError as e:
        return {"responde": False, "erro": type(e).__name__, "status": None,
                "corpo": None, "content_type": None, "metodo": metodo, "mpp": False}
    corpo_json: dict[str, Any] | None = None
    if r.status_code == 402:
        corpo_json = _cotacao_do_402(r)
    return {"responde": True, "erro": None, "status": r.status_code,
            "corpo": r.content, "content_type": r.headers.get("content-type"),
            "json": corpo_json, "metodo": metodo,
            # sinal da watchlist (D-27): o mesmo endpoint também fala MPP?
            "mpp": r.headers.get("www-authenticate", "").startswith("Payment ")}


def main() -> None:
    dados = json.loads(CANDIDATOS.read_text(encoding="utf-8"))
    candidatos = dados["candidatos"]
    conn = db.connect()
    db.apply_migrations(conn)
    tracer = configurar_tracer(conn, "mesa-censo")

    # 1º passo: sondar DENTRO dos spans, só capturando (o processor grava o span
    # quando ele FECHA — a FK request→span exige gravar o livro DEPOIS da árvore,
    # mesmo padrão da Fase 2)
    sondas: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []
    with tracer.start_as_current_span("censo.sondagem-rodada1"), \
            httpx.Client(timeout=15, follow_redirects=False,
                         headers={"User-Agent": UA}) as cli:
        for c in candidatos:
            with tracer.start_as_current_span(
                "censo.sondagem", attributes={"censo.dominio": c["dominio"]}
            ):
                trace_id, span_id = ids_do_span_atual()
                sondas.append((c, _sondar(cli, c), trace_id, span_id))

    # 2º passo: com todos os spans no banco, gravar requests/quotes no livro
    resultados: list[dict[str, Any]] = []
    for c, s, trace_id, span_id in sondas:
        corpo: bytes | None = s.get("corpo")
        rid = db.insert_request(
            conn, rail="x402",
            resource_key_hash=hashlib.sha256(c["url"].encode()).digest(),
            method=s["metodo"], status_http=s["status"],
            body_sha256=hashlib.sha256(corpo).digest() if corpo else None,
            body_bytes=len(corpo) if corpo is not None else None,
            content_type=s["content_type"], delivered=False,
            trace_id=trace_id, span_id=span_id,
            transport="http", origin="direct",
        )

        aceite = None
        motivo = ""
        if s["status"] == 402 and s.get("json"):
            aceite, motivo = _cotacao_valida(s["json"])
        elif s["status"] == 402:
            motivo = "402-sem-cotacao-legivel"
        elif s["responde"]:
            motivo = f"status-{s['status']}"
        else:
            motivo = f"nao-respondeu ({s['erro']})"

        preco_cotado = None
        if aceite:
            preco_cotado = int(str(aceite.get(
                "maxAmountRequired", aceite.get("amount"))))
            db.insert_quote(
                conn, request_id=rid, amount_minor=preco_cotado,
                decimals=6, asset_network_caip2="eip155:8453",
                asset_contract=str(aceite["asset"]),
                pay_to=str(aceite["payTo"]),
                scheme=str(aceite["scheme"]),
            )
        resultados.append({
            "dominio": c["dominio"], "url": c["url"],
            "metodo": s["metodo"],
            "preco_anunciado_minor": c["preco_anunciado_minor"],
            "responde": s["responde"], "status_http": s["status"],
            "cotacao_valida": aceite is not None,
            "motivo_reprovacao": motivo or None,
            "preco_cotado_minor": preco_cotado,
            "deriva_de_preco": (preco_cotado is not None
                                and preco_cotado != c["preco_anunciado_minor"]),
            "pay_to": str(aceite.get("payTo")) if aceite else None,
            "fala_mpp_tambem": s["mpp"],
            "chamadas_30d": c.get("chamadas_30d"),
            "pagadores_30d": c.get("pagadores_30d"),
        })

    aprovadas = [r for r in resultados if r["cotacao_valida"]]
    custo_estimado = sum(r["preco_cotado_minor"] for r in aprovadas)
    SAIDA.write_text(json.dumps({
        "gerado_utc": datetime.now(UTC).isoformat(),
        "sondadas": len(resultados),
        "respondem": sum(1 for r in resultados if r["responde"]),
        "cotacoes_validas": len(aprovadas),
        "custo_estimado_rodada_minor": custo_estimado,
        "resultados": resultados,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    t = Table(title="sondagem do censo — números 1 e 2 (sem pagar)")
    t.add_column("domínio")
    t.add_column("responde?")
    t.add_column("cotação válida?")
    t.add_column("cotado US$", justify="right")
    t.add_column("obs")
    for r in resultados:
        obs = "PREÇO≠ANUNCIADO" if r["deriva_de_preco"] else (r["motivo_reprovacao"] or "")
        t.add_row(
            r["dominio"],
            "sim" if r["responde"] else "NÃO",
            "sim" if r["cotacao_valida"] else "não",
            f"{r['preco_cotado_minor'] / 1e6:.4f}" if r["preco_cotado_minor"] else "—",
            obs,
        )
    console.print(t)
    console.print(
        f"[bold]{len(resultados)} sondadas · {sum(1 for r in resultados if r['responde'])} "
        f"respondem · {len(aprovadas)} cotações válidas · custo estimado da rodada: "
        f"US$ {custo_estimado / 1e6:.4f}[/bold]"
    )
    console.print(f"gravado em {SAIDA} — este é o relatório do 'vai' (aprovação 3)")


if __name__ == "__main__":
    main()
