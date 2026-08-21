"""Fase 6: a conta do trilho invoice — Decimal, preço pinado, faixa por data."""

from datetime import date

from mesa.trilho_invoice import custo_llm_micro_usd

MODELO = "claude-sonnet-5"


def test_preco_intro_ate_31_08() -> None:
    # 1M tokens de entrada a US$2/MTok = US$ 2,00 = 2_000_000 micro-USD
    assert custo_llm_micro_usd(MODELO, 1_000_000, 0, date(2026, 8, 21)) == 2_000_000
    # 1M de saída a US$10/MTok
    assert custo_llm_micro_usd(MODELO, 0, 1_000_000, date(2026, 8, 31)) == 10_000_000


def test_preco_padrao_depois() -> None:
    assert custo_llm_micro_usd(MODELO, 1_000_000, 0, date(2026, 9, 1)) == 3_000_000
    assert custo_llm_micro_usd(MODELO, 0, 1_000_000, date(2026, 9, 1)) == 15_000_000


def test_chamada_pequena_arredonda_certo() -> None:
    # 217 in + 63 out em 21/08: 217*2 + 63*10 = 1064 micro-USD (US$ 0,001064)
    assert custo_llm_micro_usd(MODELO, 217, 63, date(2026, 8, 21)) == 1064


def test_modelo_sem_preco_falha() -> None:
    try:
        custo_llm_micro_usd("modelo-fantasma", 1, 1, date(2026, 8, 21))
        raise AssertionError("devia ter falhado")
    except ValueError as e:
        assert "sem preço pinado" in str(e)
