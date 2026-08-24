"""Fase 12 — GATE 12a: o app serve as 5 telas com dado REAL e não consegue escrever.

Os testes precisam do Postgres de pé (CI sobe um vazio; local usa o livro real).
Livro VAZIO é estado válido: as telas respondem 200 do mesmo jeito — isso também
está sendo testado quando a CI roda num banco recém-migrado.
"""

from typing import Any

import psycopg
import pytest

from mesa import db
from mesa.app import dados
from mesa.app.main import _fmt_usd, app

TELAS = ["/blotter", "/tca", "/risco", "/laboratorio", "/livros"]


@pytest.fixture(scope="module")
def cliente() -> Any:
    try:
        conn = db.connect()
    except SystemExit:
        pytest.skip("Postgres fora do ar — os testes do app precisam do banco")
    db.apply_migrations(conn)
    conn.close()
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_todas_as_telas_respondem(cliente: Any) -> None:
    for rota in TELAS:
        r = cliente.get(rota)
        assert r.status_code == 200, f"{rota}: {r.status_code}"
        assert "APPEND-ONLY" in r.text  # o rodapé de honestidade está em toda tela


def test_raiz_redireciona_para_o_blotter(cliente: Any) -> None:
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/blotter"


def test_numeros_do_blotter_batem_com_query_independente(cliente: Any) -> None:
    """O gasto REAL da tela == a soma recomputada por SQL próprio (nunca digitado)."""
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
    html = cliente.get("/blotter").text
    assert f"$ {_fmt_usd(mainnet_minor)}" in html


def test_vereditos_dos_livros_batem_com_a_reconciliacao(cliente: Any) -> None:
    from mesa import reconcile

    with dados.conectar_leitura() as conn:
        compras, liquidacoes = reconcile.carregar(conn)
    vereditos = reconcile.reconciliar(compras, liquidacoes)
    html = cliente.get("/livros").text
    for v, itens in vereditos.items():
        if itens:
            assert str(v).upper() in html, f"veredito {v} sumiu da tela"


def test_gaveta_de_compra(cliente: Any) -> None:
    with dados.conectar_leitura() as conn, conn.cursor() as cur:
        cur.execute("SELECT id::text FROM request ORDER BY ts_utc LIMIT 1")
        row = cur.fetchone()
    if row is None:
        pytest.skip("livro vazio — sem compra para abrir")
    r = cliente.get(f"/api/compra/{row[0]}")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["rid"] == row[0] and "eventos" in corpo


def test_compra_inexistente_da_404(cliente: Any) -> None:
    assert cliente.get(
        "/api/compra/00000000-0000-0000-0000-000000000000").status_code == 404


def test_o_app_nao_consegue_escrever(cliente: Any) -> None:
    """D-35: read-only ESTRUTURAL — a sessão do app recusa INSERT/UPDATE/DELETE."""
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


def test_operacoes_lista_fechada(cliente: Any) -> None:
    """D-36: a tela só aciona a lista FECHADA — nome inventado é 404, nunca executa."""
    r = cliente.get("/operacoes")
    assert r.status_code == 200 and "SEMPRE testnet" in r.text
    assert cliente.post("/api/operacao/rm-rf-tudo").status_code == 404
    assert cliente.get("/api/operacao").status_code == 200


def test_operacoes_incluem_os_exports_da_f13(cliente: Any) -> None:
    """Fase 14: contabil e carf entram na lista FECHADA; livros lista os exports."""
    from mesa.app import jobs
    assert {"contabil", "carf"} <= set(jobs.OPERACOES)
    html = cliente.get("/operacoes").text
    assert "export contábil" in html and "CARF" in html
    assert "EXPORTS (F13)" in cliente.get("/livros").text


def test_blotter_periodo_e_card_de_atencao(cliente: Any) -> None:
    """Fase 14b (padrão Stripe/OpenRouter): janela de período recomputada no
    SERVIDOR (cards+gráfico+tabela juntos) e a fila de atenção nomeada."""
    assert cliente.get("/blotter?dias=7").status_code == 200
    assert cliente.get("/blotter?dias=30").status_code == 200
    html = cliente.get("/blotter").text
    assert "Precisa de atenção" in html
    assert "__atencao" in html  # a opção do filtro que junta os dois estados
    assert "EXPORTAR CSV" in html  # leva a evidência embora (linhas filtradas)
    assert "Top fontes · dinheiro real" in html  # top-N da janela, só dinheiro real


def test_marca_tercet_no_topo(cliente: Any) -> None:
    """Fase 14: o martelo caiu — a tela veste tercet."""
    html = cliente.get("/blotter").text
    assert "tercet" in html and "<title>tercet · blotter</title>" in html


def test_testnet_sempre_rotulada(cliente: Any) -> None:
    """D-12 na interface: se o livro tem compra testnet, a tela DIZ testnet."""
    with dados.conectar_leitura() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM quote"
                    " WHERE asset_network_caip2 = 'eip155:84532'")
        row = cur.fetchone()
        assert row is not None
        tem_testnet = int(row[0]) > 0
    if not tem_testnet:
        pytest.skip("livro sem compras testnet")
    assert "TESTNET" in cliente.get("/blotter").text
