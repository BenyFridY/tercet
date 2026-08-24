"""Fase 13 — GATE 13b: export contábil (partidas dobradas do livro).

A parte pura (montar/validar/renderizar) roda SEM banco; a parte de carga
segue o padrão do test_app (Postgres de pé ou skip; livro vazio é válido).
"""

import csv
import dataclasses
import io
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mesa import contabil


def _compras() -> list[contabil.CompraContabil]:
    return [
        contabil.CompraContabil(date(2026, 8, 21), "api.exemplo.io", "censo",
                                Decimal("0.150000"), "0xaa"),
        contabil.CompraContabil(date(2026, 8, 22), "outra.dev", "censo",
                                Decimal("0.122000"), "0xbb"),
    ]


def test_lancamento_agrega_e_arredonda_half_up() -> None:
    lanc = contabil.montar_lancamento(_compras(), 2026, 8)
    assert lanc.valor_exato == Decimal("0.272000")
    assert lanc.valor_2c == Decimal("0.27")
    assert lanc.n_compras == 2
    assert lanc.data == date(2026, 8, 22)
    assert contabil.validar(lanc, _compras(), 2026, 8) == []


def test_sem_compras_e_materialidade_falham_nomeando() -> None:
    with pytest.raises(ValueError, match="sem-compras"):
        contabil.montar_lancamento([], 2026, 8)
    micro = [contabil.CompraContabil(date(2026, 8, 21), "x", "-",
                                     Decimal("0.002000"), "0xcc")]
    with pytest.raises(ValueError, match="abaixo-da-materialidade"):
        contabil.montar_lancamento(micro, 2026, 8)


def test_validar_morde_adulteracao() -> None:
    compras = _compras()
    lanc = contabil.montar_lancamento(compras, 2026, 8)
    mesma_conta = dataclasses.replace(lanc, conta_credito=lanc.conta_debito)
    assert "debito-e-credito-na-mesma-conta" in contabil.validar(
        mesma_conta, compras, 2026, 8)
    valor_errado = dataclasses.replace(lanc, valor_2c=Decimal("9.99"))
    assert "arredondamento-nao-confere-com-o-exato" in contabil.validar(
        valor_errado, compras, 2026, 8)
    detalhe_furado = compras[:1]
    assert "detalhe-nao-soma-no-exato" in contabil.validar(
        lanc, detalhe_furado, 2026, 8)
    fora = dataclasses.replace(lanc, data=date(2026, 9, 1))
    assert "data-fora-da-competencia" in contabil.validar(
        fora, compras, 2026, 8)


def _parse(texto: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(texto)))


def test_qbo_e_xero_fecham_as_partidas() -> None:
    lanc = contabil.montar_lancamento(_compras(), 2026, 8)
    qbo = _parse(contabil.render_qbo(lanc))
    deb = sum(Decimal(r["Debits"]) for r in qbo if r["Debits"])
    cred = sum(Decimal(r["Credits"]) for r in qbo if r["Credits"])
    assert deb == cred == lanc.valor_2c
    assert all(r["Journal No."] == lanc.numero for r in qbo)

    xero = _parse(contabil.render_xero(lanc))
    assert sum(Decimal(r["Amount"]) for r in xero) == 0  # sinal fecha em zero

    detalhe = _parse(contabil.render_detalhe(_compras()))
    assert sum(Decimal(r["usd_exato_6c"]) for r in detalhe) == lanc.valor_exato
    assert {r["tx"] for r in detalhe} == {"0xaa", "0xbb"}


def test_carga_do_livro_bate_com_sql_independente() -> None:
    from mesa import db
    from mesa.app import dados
    try:
        conn = db.connect()
    except SystemExit:
        pytest.skip("Postgres fora do ar")
    db.apply_migrations(conn)
    conn.close()
    with dados.conectar_leitura() as conn, conn.cursor() as cur:
        compras = contabil.carregar_compras(conn, dados.mapa_dominios(), 2026, 8)
        cur.execute("""
            SELECT count(*), coalesce(sum(sl.settled_amount_minor), 0)
            FROM settlement_leg sl JOIN authz a ON a.id = sl.authorization_id
            JOIN quote q ON q.id = a.quote_id
            JOIN request r ON r.id = q.request_id
            WHERE q.asset_network_caip2 = 'eip155:8453' AND a.rail = 'x402'
              AND sl.settled_amount_minor > 0
              AND extract(year FROM (r.ts_utc AT TIME ZONE
                  'America/Sao_Paulo')) = 2026
              AND extract(month FROM (r.ts_utc AT TIME ZONE
                  'America/Sao_Paulo')) = 8
        """)
        row: Any = cur.fetchone()
    assert len(compras) == int(row[0])
    total = sum((c.usd_exato for c in compras), Decimal(0))
    assert total == Decimal(int(row[1])) / contabil.MICRO
