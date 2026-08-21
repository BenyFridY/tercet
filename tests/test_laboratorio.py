"""Fase 7: o motor do Laboratório — point-in-time por tipo, walk-forward, IC."""

import dataclasses

from mesa.laboratorio import (
    Desfecho,
    Orcamento,
    PontoDeDecisao,
    backtest,
    politicas_da_rodada1,
    wilson,
)


def _cenario() -> tuple[list[PontoDeDecisao], dict[int, Desfecho]]:
    pontos = [
        PontoDeDecisao(0, "a" * 8, 1_000, 4),
        PontoDeDecisao(1, "b" * 8, 2_000, 4),
        PontoDeDecisao(2, "c" * 8, 500_000, 4),   # cara e que FALHA
        PontoDeDecisao(3, "d" * 8, 200_000, 4),
    ]
    desfechos = {
        0: Desfecho(True, 1_000),
        1: Desfecho(True, 2_000),
        2: Desfecho(False, 0),      # não entregou e não cobrou
        3: Desfecho(True, 200_000),
    }
    return pontos, desfechos


def test_point_in_time_por_tipo() -> None:
    """O PontoDeDecisao NÃO TEM campo de desfecho — a política não consegue trapacear."""
    campos = {f.name for f in dataclasses.fields(PontoDeDecisao)}
    assert "entregue" not in campos and "liquidado_minor" not in campos


def test_walk_forward_respeita_orcamento_na_ordem() -> None:
    pontos, desfechos = _cenario()

    def teto_3k(p: PontoDeDecisao, o: Orcamento) -> bool:
        return o.gasto_minor + p.amount_minor <= 3_000

    r = backtest(pontos, desfechos, "teto-3k", teto_3k)
    # compra 0 (1k) e 1 (2k); 2 e 3 não cabem DEPOIS — ordem importa
    assert r.n_compras == 2 and r.gasto_autorizado_minor == 3_000
    assert r.entregas == 2 and r.compras_que_falharam == 0
    assert r.entregas_perdidas == 1  # a entrega do ponto 3 ficou na mesa


def test_politica_que_compra_nada_reporta_sem_dividir_por_zero() -> None:
    pontos, desfechos = _cenario()
    r = backtest(pontos, desfechos, "nada",
                 politicas_da_rodada1()["verified-only"])
    assert r.n_compras == 0 and r.taxa_entrega is None
    assert r.custo_por_entrega_minor is None
    assert r.ic_wilson_95 == (0.0, 1.0)  # sem dado = sem informação, dito no intervalo
    assert r.entregas_perdidas == 3


def test_premium_pega_a_falha_cara() -> None:
    pontos, desfechos = _cenario()
    r = backtest(pontos, desfechos, "premium", politicas_da_rodada1()["premium"])
    assert r.n_compras == 2  # os dois ≥ 0,10
    assert r.compras_que_falharam == 1
    assert r.taxa_entrega == 0.5
    lo, hi = r.ic_wilson_95
    assert hi - lo > 0.8  # n=2: o IC é quase o intervalo inteiro — honestidade


def test_wilson_sanidade() -> None:
    lo, hi = wilson(13, 15)
    assert 0.60 < lo < 0.70 and 0.95 < hi <= 1.0  # 13/15 ~ [62%, 97%]
    assert wilson(0, 0) == (0.0, 1.0)
