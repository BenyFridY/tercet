"""Fase 6: o segundo trilho — gasto de LLM (fatura de API) no MESMO livro, sem migration.

O agnosticismo de trilho deixando de ser promessa:
- **O claim** (nosso lado): cada chamada LLM vira request+quote+authz com
  `rail='invoice'`, valor em MICRO-USD (6 casas, inteiro — nunca float), preço da
  tabela PINADA (`registro_precos_llm.json`, com fonte e validade).
- **O statement** (o lado deles): a fatura/extrato de uso do provedor entra como
  settlement + legs, casando com os claims por **(dia, modelo)** — a chave de join
  deste trilho (o x402 usa (authorizer, nonce); cada trilho tem a sua).

Deriva entre claim e statement é ACHADO (mesma lição do censo), não erro.
"""

import csv
import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import psycopg

from mesa import db, integridade

PRECOS_PATH = Path(__file__).parent / "registro_precos_llm.json"
CAIP2_FIAT = "fiat:USD"
MICRO = Decimal(10) ** 6


def carregar_precos() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(PRECOS_PATH.read_text(encoding="utf-8"))
    return dados


def custo_llm_micro_usd(model: str, input_tokens: int, output_tokens: int,
                        quando: date, precos: dict[str, Any] | None = None) -> int:
    """Custo em micro-USD (inteiro), Decimal por dentro, ROUND_HALF_UP no fim."""
    tabela = (precos or carregar_precos())["precos"].get(model)
    if not tabela:
        raise ValueError(f"modelo sem preço pinado: {model}")
    faixa = next(f for f in tabela
                 if f["valido_ate"] is None or quando <= date.fromisoformat(f["valido_ate"]))
    custo = (Decimal(input_tokens) * Decimal(faixa["input_por_mtok_usd"])
             + Decimal(output_tokens) * Decimal(faixa["output_por_mtok_usd"]))
    # tokens estão por MTok: custo_usd = custo/1e6; em micro-USD: custo_usd*1e6 = custo
    return int(custo.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def registrar_custo_llm(conn: psycopg.Connection[Any], *, model: str,
                        input_tokens: int, output_tokens: int,
                        trace_id: str, span_id: str,
                        payer_ref: str = "conta-anthropic-pessoal") -> tuple[uuid.UUID, int]:
    """UM claim de custo LLM no livro: request+quote+authz, rail='invoice'.

    Devolve (authz_id, custo_micro_usd). Pendura no span dado (a tarefa que gastou).
    """
    quando = db.now_utc()
    custo = custo_llm_micro_usd(model, input_tokens, output_tokens, quando.date())
    canonical = f"llm:anthropic:{model}"
    rid = db.insert_request(
        conn, rail="invoice",
        resource_key_hash=hashlib.sha256(canonical.encode()).digest(),
        method="LLM", status_http=None, body_sha256=None, body_bytes=None,
        content_type=None, delivered=True, trace_id=trace_id, span_id=span_id,
        transport="function", origin="direct", tool_name=model)
    qid = db.insert_quote(
        conn, request_id=rid, amount_minor=custo, decimals=6,
        asset_network_caip2=CAIP2_FIAT, asset_contract="USD",
        pay_to="anthropic", scheme="invoice/usage")
    aid = db.insert_authz(
        conn, quote_id=qid, rail="invoice", payer_ref=payer_ref,
        authorized_max_minor=custo, valid_from_utc=None, valid_until_utc=None,
        rail_evidence={"model": model, "input_tokens": input_tokens,
                       "output_tokens": output_tokens,
                       "preco_fonte": carregar_precos()["fonte"],
                       "dia_utc": quando.date().isoformat()},
        state="authorized")
    return aid, custo


def _inserir_settlement_invoice(conn: psycopg.Connection[Any], *, external_ref: str,
                                total_micro_usd: int, dia: date,
                                fonte: str) -> uuid.UUID | None:
    """Settlement do trilho invoice (idempotente); None se já existia."""
    sid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO settlement (id, rail, external_ref, network_caip2,"
            " block_number, block_ts_utc, confirmations, finality, total_amount_minor,"
            " fee_amount_minor) VALUES (%s,%s,%s,%s,NULL,%s,NULL,%s,%s,NULL)"
            " ON CONFLICT (rail, network_caip2, external_ref) DO NOTHING RETURNING id",
            (sid, "invoice", external_ref, CAIP2_FIAT,
             datetime(dia.year, dia.month, dia.day, tzinfo=UTC), "final",
             total_micro_usd),
        )
        if cur.fetchone() is None:
            return None
    integridade.registrar_elo(conn, "settlement", {
        "id": sid, "rail": "invoice", "external_ref": external_ref,
        "network_caip2": CAIP2_FIAT, "block_number": None,
        "block_ts_utc": datetime(dia.year, dia.month, dia.day, tzinfo=UTC),
        "facilitator_ref": None, "total_amount_minor": total_micro_usd,
        "fee_amount_minor": None, "fee_asset_contract": None,
    })
    conn.commit()
    db.insert_settlement_event(conn, settlement_id=sid, kind="observed",
                               block_number=None, confirmations=None,
                               detail={"fonte": fonte})
    return sid


def ingerir_fatura_csv(conn: psycopg.Connection[Any], caminho: Path,
                       rotulo_fonte: str) -> list[dict[str, Any]]:
    """Ingere o extrato (CSV: date,model,input_tokens,output_tokens,cost_usd) e
    reconcilia contra os claims por (dia, modelo). Devolve o relatório por linha.
    """
    relatorio: list[dict[str, Any]] = []
    with caminho.open(encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            dia = date.fromisoformat(linha["date"])
            model = linha["model"]
            statement = int((Decimal(linha["cost_usd"]) * MICRO)
                            .quantize(Decimal(1), rounding=ROUND_HALF_UP))
            external_ref = f"{rotulo_fonte}:{dia.isoformat()}:{model}"
            sid = _inserir_settlement_invoice(
                conn, external_ref=external_ref, total_micro_usd=statement,
                dia=dia, fonte=rotulo_fonte)

            # os claims daquele (dia, modelo) ainda abertos
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT a.id, a.authorized_max_minor FROM authz a"
                    " WHERE a.rail='invoice' AND a.state='authorized'"
                    " AND a.rail_evidence->>'model' = %s"
                    " AND a.rail_evidence->>'dia_utc' = %s",
                    (model, dia.isoformat()),
                )
                claims = cur.fetchall()
                if sid is None:  # já ingerido antes — busca o id p/ os legs
                    cur.execute(
                        "SELECT id FROM settlement WHERE rail='invoice'"
                        " AND network_caip2=%s AND external_ref=%s",
                        (CAIP2_FIAT, external_ref))
                    row = cur.fetchone()
                    assert row is not None
                    sid = row[0]
                for aid, valor in claims:
                    cur.execute(
                        "INSERT INTO settlement_leg (settlement_id, authorization_id,"
                        " settled_amount_minor) VALUES (%s,%s,%s)"
                        " ON CONFLICT DO NOTHING RETURNING 1",
                        (sid, aid, int(valor)))
                    if cur.fetchone() is not None:
                        integridade.registrar_elo(conn, "settlement_leg", {
                            "settlement_id": sid, "authorization_id": aid,
                            "settled_amount_minor": int(valor)})
                    cur.execute("UPDATE authz SET state='settled' WHERE id=%s", (aid,))
            conn.commit()
            for aid, _valor in claims:
                db.insert_authz_event(conn, authorization_id=aid, kind="settled",
                                      detail={"settlement_ref": external_ref})

            soma_claims = sum(int(v) for _, v in claims)
            relatorio.append({
                "dia": dia.isoformat(), "model": model,
                "statement_micro_usd": statement,
                "claims": len(claims), "claims_micro_usd": soma_claims,
                "deriva_micro_usd": statement - soma_claims,
            })
    return relatorio
