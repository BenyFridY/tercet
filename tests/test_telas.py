"""Fase 8: as regras das telas — estado derivado e desperdício, puras, sem banco."""

from datetime import UTC, datetime, timedelta

from mesa.telas import Linha, derivar_estado, marcar_desperdicio

AGORA = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_estados_derivados_do_livro() -> None:
    casos = [
        # (delivered, tem_authz, settled, valid_until, rail) -> estado
        ((True, True, 10_000, None, "x402"), "liquidado"),
        ((False, True, 10_000, None, "x402"), "pago-sem-entrega"),   # caos fase 1
        ((True, True, 0, AGORA - timedelta(hours=2), "x402"), "entregue-sem-cobrar"),
        ((True, True, 0, AGORA + timedelta(hours=2), "x402"), "cobranca-pendente"),
        ((False, True, 0, AGORA - timedelta(hours=2), "x402"), "expirou-sem-uso"),
        ((False, True, 0, AGORA + timedelta(hours=2), "x402"), "autorizado-pendente"),
        ((True, False, 0, None, "x402"), "sem-pagamento"),           # sonda/grátis
        ((True, True, 858, None, "invoice"), "fatura-conciliada"),
        ((False, False, 0, None, "mpp"), "ingerido"),
    ]
    for (delivered, tem_authz, settled, valid_until, rail), esperado in casos:
        assert derivar_estado(delivered=delivered, tem_authz=tem_authz,
                              settled_minor=settled, valid_until=valid_until,
                              agora=AGORA, rail=rail) == esperado


def _linha(i: int, recurso: str, corpo: str | None, settled: int,
           delivered: bool = True) -> Linha:
    return Linha(
        rid=f"r{i}", ts_utc=AGORA + timedelta(minutes=i), recurso_hash=recurso,
        dominio=None, metodo="GET", status_http=200, delivered=delivered,
        body_sha256=corpo, body_bytes=10, rail="x402", agente="a", tarefa="t",
        trace_id="tr", amount_minor=settled or 10, pay_to="0xab", network="eip155:84532",
        valid_until=None, principal_ref=None, settled_minor=settled, tx=None)


def test_desperdicio_repetido_byte_a_byte_paga_de_novo() -> None:
    linhas = [
        _linha(0, "rec1", "corpoA", 10_000),          # 1ª vez do corpoA: novo
        _linha(1, "rec1", "corpoA", 10_000),          # REPETIDO: mesmo byte, pagou
        _linha(2, "rec1", "corpoB", 10_000),          # corpo NOVO: dinâmico legítimo
        _linha(3, "rec1", "corpoA", 0),               # repetido mas não liquidou: 0 gasto
        _linha(4, "rec2", "corpoZ", 5_000),           # outro recurso, 1 compra: fora
        _linha(5, "rec3", "corpoY", 5_000, delivered=False),  # não entregou: fora
    ]
    resumo = marcar_desperdicio(linhas)
    assert [ln.repetido for ln in linhas] == [False, True, False, True, False, False]
    assert linhas[0].dedup_n == 4 and linhas[4].dedup_n == 1
    (r1,) = [r for r in resumo["recursos_repetidos"] if r["recurso_hash"] == "rec1"]
    assert r1["compras"] == 4 and r1["conteudos_distintos"] == 2 and r1["repetidas"] == 2
    assert resumo["gasto_repetido_total_minor"] == 10_000  # só a repetição LIQUIDADA
