"""Fase 13 — GATE 13a: o livro como ferramentas MCP, read-only estrutural (D-37).

Mesmo requisito do test_app: Postgres de pé (CI sobe um vazio; local usa o livro
real). Livro VAZIO é estado válido — as ferramentas respondem do mesmo jeito.
"""

import asyncio
import json
from typing import Any

import psycopg
import pytest

from mesa import db, reconcile
from mesa.app import dados
from mesa.mcp.livro import criar_servidor

FERRAMENTAS = {"status_do_livro", "gasto", "compras", "compra", "vereditos",
               "passaportes", "fiscal"}


@pytest.fixture(scope="module")
def servidor() -> Any:
    try:
        conn = db.connect()
    except SystemExit:
        pytest.skip("Postgres fora do ar — os testes do MCP precisam do banco")
    db.apply_migrations(conn)
    conn.close()
    return criar_servidor()


def _chamar(servidor: Any, nome: str,
            args: dict[str, Any] | None = None) -> dict[str, Any]:
    r = asyncio.run(servidor.call_tool(nome, args or {}))
    assert not r.is_error, r
    out = json.loads(r.content[0].text)
    assert isinstance(out, dict)
    return out


def test_lista_de_ferramentas_e_fechada(servidor: Any) -> None:
    """D-37: só leitura, nomes fixos — nenhuma ferramenta de escrita exposta."""
    ts = asyncio.run(servidor.list_tools())
    assert {t.name for t in ts} == FERRAMENTAS


def test_gasto_bate_com_query_independente(servidor: Any) -> None:
    """O mesmo critério do gate 12a: o número da ferramenta == SQL recomputado."""
    out = _chamar(servidor, "gasto")
    with dados.conectar_leitura() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT coalesce(sum(sl.settled_amount_minor), 0)
            FROM settlement_leg sl JOIN authz a ON a.id = sl.authorization_id
            JOIN quote q ON q.id = a.quote_id
            WHERE q.asset_network_caip2 = 'eip155:8453'
        """)
        row = cur.fetchone()
        assert row is not None
        mainnet_minor = int(row[0])
    assert out["gasto_real_minor"] == mainnet_minor


def test_compras_filtra_e_limita(servidor: Any) -> None:
    out = _chamar(servidor, "compras", {"limite": 5})
    assert out["devolvidas"] <= 5
    assert len(out["linhas"]) == out["devolvidas"]
    liq = _chamar(servidor, "compras", {"estado": "liquidado", "limite": 100})
    assert all(ln["estado"] == "liquidado" for ln in liq["linhas"])
    test = _chamar(servidor, "compras", {"rede": "eip155:84532", "limite": 100})
    assert all(ln["rede"] == "eip155:84532" for ln in test["linhas"])


def test_gaveta_de_uma_compra(servidor: Any) -> None:
    out = _chamar(servidor, "compras", {"estado": "liquidado", "limite": 1})
    if not out["linhas"]:
        pytest.skip("livro sem compra liquidada (CI vazia) — a gaveta não tem alvo")
    rid = out["linhas"][0]["rid"]
    g = _chamar(servidor, "compra", {"rid": rid})
    assert g["compra"]["rid"] == rid
    assert isinstance(g["eventos"], list)


def test_compra_inexistente_diz_erro_sem_estourar(servidor: Any) -> None:
    g = _chamar(servidor, "compra",
                {"rid": "00000000-0000-0000-0000-000000000000"})
    assert "erro" in g


def test_vereditos_batem_com_reconciliacao(servidor: Any) -> None:
    out = _chamar(servidor, "vereditos")
    with dados.conectar_leitura() as conn:
        compras_, liqs = reconcile.carregar(conn)
    vs = reconcile.reconciliar(compras_, liqs)
    esperado = {v.value: len(itens) for v, itens in vs.items() if itens}
    assert {d["veredito"]: d["n"] for d in out["vereditos"]} == esperado
    assert out["n_compras"] == len(compras_)


def test_fiscal_responde_com_competencia(servidor: Any) -> None:
    out = _chamar(servidor, "fiscal")
    assert len(out["competencia"]) == 7  # aaaa-mm
    assert out["n_ops_mainnet"] >= 0


def test_a_conexao_do_mcp_nao_consegue_escrever(servidor: Any) -> None:
    """D-37 = D-35 no MCP: a sessão do servidor recusa INSERT/UPDATE/DELETE."""
    with dados.conectar_leitura() as conn, conn.cursor() as cur:  # noqa: SIM117
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            cur.execute("INSERT INTO span (trace_id, span_id, name, started_utc)"
                        " VALUES ('nunca', 'nunca', 'nunca', now())")
        conn.rollback()
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            cur.execute("UPDATE authz SET state = 'hackeado'")
        conn.rollback()
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            cur.execute("DELETE FROM ledger_hash")
        conn.rollback()
