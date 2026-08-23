"""Fase 11: PTAX point-in-time (D-30: python-bcb) — a cotação da DATA CERTA.

As duas regras que valem mais que o código (docs/fase11.md, e a regra vem do contador):
- A data da operação é a de **São Paulo**: um pagamento às 22h de SP é 01h UTC do dia
  seguinte — usar a data UTC erraria a conversão de toda compra noturna.
- **Point-in-time**: dia sem cotação (fim de semana, feriado) usa a última cotação
  ANTERIOR disponível — nunca a seguinte, que não existia na data. Cada cotação usada
  é persistida em `fx_ptax` (migration 0004) para regeneração determinística.

`fx_ptax` é dado de referência externo, fora da corrente de hash (não é o livro).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

TZ_SP = ZoneInfo("America/Sao_Paulo")
FONTE = "bcb-ptax-CotacaoDolarDia"
DIAS_MAX_RETROCESSO = 7  # mais que isso sem cotação = algo muito errado, não mascarar


def data_sp(ts_utc: datetime) -> date:
    """A regra de São Paulo, como função pura."""
    return ts_utc.astimezone(TZ_SP).date()


def _buscar_bcb(d: date) -> tuple[Decimal, Decimal] | None:
    """Cotação de fechamento do dia no BCB (rede). None = dia sem cotação."""
    from bcb import PTAX  # import local: pesado (pandas) e só o caminho online precisa

    ep = PTAX().get_endpoint("CotacaoDolarDia")
    df = ep.query().parameters(dataCotacao=d.strftime("%m-%d-%Y")).collect()
    if df.empty:
        return None
    linha = df.iloc[-1]  # CotacaoDolarDia devolve o boletim de fechamento do dia
    return Decimal(str(linha["cotacaoCompra"])), Decimal(str(linha["cotacaoVenda"]))


def _ler(conn: psycopg.Connection[Any], d: date) -> Decimal | None:
    with conn.cursor() as cur:
        cur.execute("SELECT venda FROM fx_ptax WHERE data_cotacao = %s", (d,))
        row = cur.fetchone()
        return Decimal(row[0]) if row else None


def _gravar(conn: psycopg.Connection[Any], d: date, compra: Decimal, venda: Decimal) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO fx_ptax (data_cotacao, compra, venda, fonte, fetched_utc)"
            " VALUES (%s,%s,%s,%s,%s) ON CONFLICT (data_cotacao) DO NOTHING",
            (d, compra, venda, FONTE, datetime.now(UTC)),
        )
    conn.commit()


def venda_para(conn: psycopg.Connection[Any], d: date) -> tuple[date, Decimal]:
    """A PTAX venda válida PARA a data d: a do próprio dia ou a última anterior.

    Devolve (data_da_cotacao_usada, venda) — a data usada aparece no resumo gerado,
    porque 'usei a cotação de sexta para a compra de sábado' é informação, não detalhe.
    """
    for k in range(DIAS_MAX_RETROCESSO + 1):
        dk = d - timedelta(days=k)
        venda = _ler(conn, dk)
        if venda is not None:
            return dk, venda
        cotacao = _buscar_bcb(dk)
        if cotacao is not None:
            _gravar(conn, dk, cotacao[0], cotacao[1])
            return dk, cotacao[1]
    raise RuntimeError(f"sem PTAX em {DIAS_MAX_RETROCESSO} dias antes de {d} — investigar")
