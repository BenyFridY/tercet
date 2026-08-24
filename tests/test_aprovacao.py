"""Fase 8 (D-14): a aprovação é vinculada — 'sim' para A nunca autoriza B."""

from types import SimpleNamespace
from typing import Any

import pytest

from mesa import aprovacao, checagens
from mesa.config import CAIP2_BASE_SEPOLIA, USDC_BASE_SEPOLIA

PAYTO = "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea"


def _req(amount: int) -> Any:
    return SimpleNamespace(network=CAIP2_BASE_SEPOLIA, scheme="exact",
                           asset=USDC_BASE_SEPOLIA, pay_to=PAYTO,
                           get_amount=lambda: amount)


def _escopo(amount: int) -> str:
    return aprovacao.escopo_da_cotacao(pay_to=PAYTO, amount_minor=amount,
                                       asset=USDC_BASE_SEPOLIA,
                                       network=CAIP2_BASE_SEPOLIA)


def test_escopo_deterministico_e_sensivel_a_qualquer_campo() -> None:
    assert _escopo(500_000) == _escopo(500_000)
    assert _escopo(500_000) != _escopo(500_001)  # mudou um centavo de milionésimo


def test_aprovacao_de_a_nao_vale_para_b() -> None:
    ap_a = aprovacao.aprovar(_escopo(500_000), "alice", decisao=True)
    assert aprovacao.vale_para(ap_a, _escopo(500_000))
    assert not aprovacao.vale_para(ap_a, _escopo(900_000))  # outra cotação: não vale


def test_negacao_tambem_e_evidencia_e_nao_vale() -> None:
    nao = aprovacao.aprovar(_escopo(500_000), "alice", decisao=False)
    assert not aprovacao.vale_para(nao, _escopo(500_000))
    assert nao.evidencia()["tipo"] == "aprovacao-vinculada-d14"


def test_seletor_acima_do_teto_sem_callback_recusa() -> None:
    seletor = checagens.seletor_com_checagens(
        CAIP2_BASE_SEPOLIA, teto_unverified_minor=None, teto_aprovacao_minor=100_000)
    with pytest.raises(ValueError, match="precisa-aprovacao"):
        seletor(2, [_req(500_000)])
    ok = seletor(2, [_req(50_000)])  # abaixo do teto: segue sem perguntar
    assert int(ok.get_amount()) == 50_000


def test_seletor_com_aprovacao_vinculada_passa_e_com_aprovacao_de_outra_recusa() -> None:
    aprova_esta = checagens.seletor_com_checagens(
        CAIP2_BASE_SEPOLIA, teto_unverified_minor=None, teto_aprovacao_minor=100_000,
        pedir_aprovacao=lambda c: aprovacao.aprovar(c["escopo_hex"], "alice", True))
    assert int(aprova_esta(2, [_req(500_000)]).get_amount()) == 500_000

    de_outra = aprovacao.aprovar(_escopo(999_999), "alice", True)  # aprovou OUTRA
    seletor = checagens.seletor_com_checagens(
        CAIP2_BASE_SEPOLIA, teto_unverified_minor=None, teto_aprovacao_minor=100_000,
        pedir_aprovacao=lambda _c: de_outra)
    with pytest.raises(ValueError, match="precisa-aprovacao"):
        seletor(2, [_req(500_000)])
