"""Fase 13 — GATE 13c: a visão CARF (OECD, guia jul/2025), demo rotulada.

A parte pura (montar_xml/validar) roda SEM banco; a agregação segue o padrão
do test_app (Postgres ou skip).
"""

from decimal import Decimal
from typing import Any

import pytest

from mesa import carf


def _agregado() -> carf.AgregadoAno:
    return carf.AgregadoAno(ano=2026, cripto_ativo="USDC",
                            n_transacoes=13, usd_exato=Decimal("0.272000"))


def test_documento_valido_e_nasce_rotulado_teste() -> None:
    xml = carf.montar_xml(_agregado())
    assert carf.validar(xml) == []
    assert b"OECD11" in xml  # New Test Data — o tpAmb=2 do CARF
    assert b"DEMONSTRACAO" in xml  # Warning em texto corrido
    assert b"CARF603" in xml  # compra de bens/servicos (jul/2025)
    assert b">0.27<" in xml  # Amount com 2 casas (regra do guia)
    assert b">0.272000<" in xml  # NumberofUnits com 6 casas


def test_message_ref_id_segue_o_padrao_do_guia() -> None:
    """Regra do guia: país-remetente + ano + país-destinatário + único."""
    xml = carf.montar_xml(_agregado())
    assert b"<carf:MessageRefID>BR2026BR-" in xml


def test_validar_morde_adulteracao_nomeando_o_campo() -> None:
    xml = carf.montar_xml(_agregado())
    assert any(p.startswith("TransferType-fora-da-tabela")
               for p in carf.validar(xml.replace(b"CARF603", b"CARF999")))
    assert any(p.startswith("Amount-sem-2-casas")
               for p in carf.validar(xml.replace(b">0.27<", b">0.272<")))
    assert "MessageType-diferente-de-CARF" in carf.validar(
        xml.replace(b">CARF<", b">XXXX<"))
    assert any(p.startswith("DocTypeIndic-fora-da-tabela")
               for p in carf.validar(xml.replace(b"OECD11", b"OECD99")))
    assert any(p.startswith("NumberofTransactions-nao-positivo")
               for p in carf.validar(xml.replace(
                   b"<carf:NumberofTransactions>13<",
                   b"<carf:NumberofTransactions>0<")))
    assert carf.validar(b"<oi/>x")[0].startswith("xml-malformado")


def test_agregado_do_livro_bate_com_sql_independente() -> None:
    from mesa import db
    from mesa.app import dados
    try:
        conn = db.connect()
    except SystemExit:
        pytest.skip("Postgres fora do ar")
    db.apply_migrations(conn)
    conn.close()
    with dados.conectar_leitura() as conn, conn.cursor() as cur:
        ag = carf.agregar_ano(conn, dados.mapa_dominios(), 2026)
        cur.execute("""
            SELECT count(*), coalesce(sum(sl.settled_amount_minor), 0)
            FROM settlement_leg sl JOIN authz a ON a.id = sl.authorization_id
            JOIN quote q ON q.id = a.quote_id
            JOIN request r ON r.id = q.request_id
            WHERE q.asset_network_caip2 = 'eip155:8453' AND a.rail = 'x402'
              AND sl.settled_amount_minor > 0
              AND extract(year FROM (r.ts_utc AT TIME ZONE
                  'America/Sao_Paulo')) = 2026
        """)
        row: Any = cur.fetchone()
    assert ag.n_transacoes == int(row[0])
    assert ag.usd_exato == Decimal(int(row[1])) / Decimal(1_000_000)
