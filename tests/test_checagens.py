"""GATE 5(a): os três ataques recusados em teste reproduzível, SEM REDE.

O registro usado é o pinado no repo (lido do contrato uma vez, offline aqui).
Cada ataque tem o motivo NOMEADO no veredito — evidência, não booleano.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from mesa import checagens
from mesa.config import CAIP2_BASE_MAINNET, USDC_BASE_MAINNET

REDE = CAIP2_BASE_MAINNET
USDC = USDC_BASE_MAINNET
PAYTO_LEGITIMO = "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea"
PAYTO_ATACANTE = "0x000000000000000000000000000000000000dEaD"
VINCULO_N2 = {"nivel": 2, "valido": True, "payto": PAYTO_LEGITIMO,
              "dominio": "vendedor-legitimo.example"}


def test_ataque_1_payto_trocado() -> None:
    """Cotação com payTo do ATACANTE, num domínio cujo vínculo aponta outro payTo."""
    v = checagens.checar_cotacao(
        rede=REDE, asset=USDC, pay_to=PAYTO_ATACANTE, amount_minor=10_000,
        vinculo=VINCULO_N2)
    assert not v.aprovada
    assert v.motivo == "payto-trocado"
    assert v.evidencia["payto_vinculado_ao_dominio"] == PAYTO_LEGITIMO


def test_ataque_2_ativo_sosia() -> None:
    """Token que se apresenta como USDC mas o CONTRATO é outro (símbolo é grátis)."""
    sosia = "0x1111111111111111111111111111111111111111"
    v = checagens.checar_cotacao(
        rede=REDE, asset=sosia, pay_to=PAYTO_LEGITIMO, amount_minor=10_000)
    assert not v.aprovada
    assert v.motivo == "ativo-sosia"
    assert "símbolo NÃO foi consultado" in v.evidencia["nota"]


def test_ataque_3_decimais_mentidos() -> None:
    """Cotação afirma 2 casas (US$ 100,00 vira 'US$ 100,00') — o contrato diz 6."""
    v = checagens.checar_cotacao(
        rede=REDE, asset=USDC, pay_to=PAYTO_LEGITIMO, amount_minor=10_000,
        decimais_afirmados=2)
    assert not v.aprovada
    assert v.motivo == "decimais-mentidos"
    assert v.evidencia["pinado_no_contrato"] == 6


def test_cotacao_legitima_passa() -> None:
    v = checagens.checar_cotacao(
        rede=REDE, asset=USDC.upper(), pay_to=PAYTO_LEGITIMO, amount_minor=10_000,
        vinculo=VINCULO_N2)
    assert v.aprovada and v.motivo == "ok"


def test_unverified_e_primeira_classe_com_teto() -> None:
    """Sem vínculo: passa DENTRO do teto da política; recusa ACIMA dele."""
    ok = checagens.checar_cotacao(rede=REDE, asset=USDC, pay_to=PAYTO_LEGITIMO,
                                  amount_minor=1_000, teto_unverified_minor=1_000_000)
    assert ok.aprovada and ok.motivo == "unverified" and ok.evidencia["nivel"] == 4
    caro = checagens.checar_cotacao(rede=REDE, asset=USDC, pay_to=PAYTO_LEGITIMO,
                                    amount_minor=2_000_000,
                                    teto_unverified_minor=1_000_000)
    assert not caro.aprovada
    assert caro.motivo == "payto-nao-verificado-acima-do-teto"


def test_rede_desconhecida_recusa() -> None:
    v = checagens.checar_cotacao(rede="eip155:1", asset=USDC,
                                 pay_to=PAYTO_LEGITIMO, amount_minor=1)
    assert not v.aprovada and v.motivo == "rede-desconhecida"


def _req(asset: str, pay_to: str, amount: int, rede: str = REDE,
         scheme: str = "exact") -> Any:
    return SimpleNamespace(network=rede, scheme=scheme, asset=asset, pay_to=pay_to,
                           get_amount=lambda: amount)


def test_seletor_fail_closed_antes_de_assinar() -> None:
    """O seletor do SDK recusa TODOS os aceites maliciosos — a compra não acontece."""
    seletor = checagens.seletor_com_checagens(REDE, teto_unverified_minor=1_000_000)
    with pytest.raises(ValueError, match="ativo-sosia"):
        seletor(2, [_req("0x2222222222222222222222222222222222222222",
                         PAYTO_LEGITIMO, 10_000)])
    escolhido = seletor(2, [
        _req("0x3333333333333333333333333333333333333333", PAYTO_LEGITIMO, 10),
        _req(USDC, PAYTO_LEGITIMO, 10_000),  # o único legítimo
    ])
    assert escolhido.asset == USDC


def test_seletor_payto_trocado_com_vinculo() -> None:
    seletor = checagens.seletor_com_checagens(
        REDE, vinculos={PAYTO_ATACANTE.lower(): {**VINCULO_N2}})
    with pytest.raises(ValueError, match="payto-trocado"):
        seletor(2, [_req(USDC, PAYTO_ATACANTE, 10_000)])
