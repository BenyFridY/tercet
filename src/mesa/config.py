"""Constantes da rede e settings do v0.

Rede das Fases 1–2: Base Sepolia (eip155:84532). A Fase 3 adiciona a Base MAINNET
(eip155:8453) para o censo comprador — rede dupla, a testnet continua funcionando.
Fontes dos endereços: DECISOES.md D-18 / PLANO.md (tabela de ambiente); USDC mainnet
é o contrato canônico da Circle na Base (conferido on-chain no smoke da Fase 3).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

# USDC de teste na Base Sepolia (faucet.circle.com, 20 USDC/2h por endereço)
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
CAIP2_BASE_SEPOLIA = "eip155:84532"
CHAIN_ID_BASE_SEPOLIA = 84532
USDC_DECIMALS = 6

# Fase 3 — Base mainnet (dinheiro real; só o censo usa, com tetos duros abaixo)
USDC_BASE_MAINNET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CAIP2_BASE_MAINNET = "eip155:8453"
CHAIN_ID_BASE_MAINNET = 8453

DEFAULT_RPC_URL = "https://sepolia.base.org"
DEFAULT_RPC_URL_MAINNET = "https://mainnet.base.org"
DEFAULT_FACILITATOR_URL = "https://x402.org/facilitator"

# Tetos do censo (regra 4 da fase3.md) — o script PARA sozinho nestes valores
CENSO_TETO_POR_COMPRA_MINOR = 1_000_000   # US$ 1,00 em USDC (6 casas)
CENSO_TETO_RODADA_MINOR = 20_000_000      # US$ 20,00 na rodada 1

# Preço do endpoint de brinquedo: 0,01 USDC -> 200 chamadas = 2 USDC
TOY_PRICE_USDC_MINOR = 10_000  # inteiro em unidade mínima, nunca float (invariante do livro)


class Settings(BaseSettings):
    """Lidas de .env (nunca commitado). Chaves privadas só vivem aqui."""

    # Segredos moram FORA da pasta sincronizada pelo OneDrive (repo vive em Documents\x402\mesa):
    # chave privada em pasta de sync = chave na nuvem. C:\dev\mesa.env tem precedência.
    model_config = SettingsConfigDict(
        env_file=(".env", r"C:\dev\mesa.env"), env_file_encoding="utf-8", extra="ignore"
    )

    rpc_url: str = DEFAULT_RPC_URL
    rpc_url_mainnet: str = DEFAULT_RPC_URL_MAINNET
    facilitator_url: str = DEFAULT_FACILITATOR_URL
    database_url: str = "postgresql://mesa:mesa@localhost:5433/mesa"

    buyer_pk: str = ""
    buyer_address: str = ""
    seller_pk: str = ""
    seller_payto: str = ""
    # T4: a carteira do SERVIDOR MCP — com ela o servidor compra upstream (compra delegada)
    mcp_server_pk: str = ""
    mcp_server_address: str = ""
    anthropic_api_key: str = ""  # T6: o agente (nunca impresso, nunca commitado)
    # Fase 3: carteira EXCLUSIVA do censo (mainnet) — nunca reusada, só o orçamento dentro
    census_pk: str = ""
    census_address: str = ""
