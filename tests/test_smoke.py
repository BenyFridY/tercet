"""Esqueleto verde: constantes do ambiente batem com o PLANO (sem rede, sem banco)."""

from mesa.config import (
    CAIP2_BASE_SEPOLIA,
    CHAIN_ID_BASE_SEPOLIA,
    TOY_PRICE_USDC_MINOR,
    USDC_BASE_SEPOLIA,
    USDC_DECIMALS,
    Settings,
)


def test_constantes_da_rede() -> None:
    assert f"eip155:{CHAIN_ID_BASE_SEPOLIA}" == CAIP2_BASE_SEPOLIA
    assert CHAIN_ID_BASE_SEPOLIA == 84532  # testnet — NUNCA 8453 (mainnet)
    assert USDC_BASE_SEPOLIA.startswith("0x") and len(USDC_BASE_SEPOLIA) == 42
    assert USDC_DECIMALS == 6


def test_preco_do_brinquedo_e_inteiro_em_unidade_minima() -> None:
    assert isinstance(TOY_PRICE_USDC_MINOR, int)
    assert TOY_PRICE_USDC_MINOR == 10_000  # 0,01 USDC


def test_settings_carrega_sem_env() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.rpc_url.startswith("https://")
    assert s.facilitator_url.startswith("https://")
