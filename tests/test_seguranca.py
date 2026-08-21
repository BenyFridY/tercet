"""docs/seguranca.md em teste reproduzível — cada furo arrumado tem um teste aqui.

Tudo OFFLINE (a guarda de URL é testada com IPs literais — sem DNS no pytest).
"""

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mesa import checagens, rede_segura
from mesa.config import (
    CAIP2_BASE_MAINNET,
    CAIP2_BASE_SEPOLIA,
    USDC_BASE_MAINNET,
    USDC_BASE_SEPOLIA,
    USDC_DECIMALS,
    Settings,
)

PAYTO = "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea"


def _req(asset: str, amount: int, rede: str = CAIP2_BASE_MAINNET,
         validade_s: int | None = None) -> Any:
    r = SimpleNamespace(network=rede, scheme="exact", asset=asset, pay_to=PAYTO,
                        get_amount=lambda: amount)
    if validade_s is not None:
        r.max_timeout_seconds = validade_s
    return r


# ---- furo 4: valor tem piso e teto absoluto -------------------------------------


def test_seletor_recusa_valor_zero_negativo_e_absurdo() -> None:
    seletor = checagens.seletor_com_checagens(CAIP2_BASE_MAINNET,
                                              teto_unverified_minor=None)
    for valor in (0, -5, 2**70):
        with pytest.raises(ValueError, match="valor-invalido"):
            seletor(2, [_req(USDC_BASE_MAINNET, valor)])


# ---- furo 3: validade da autorização não é o vendedor quem manda ----------------


def test_seletor_recusa_validade_excessiva() -> None:
    """maxTimeoutSeconds do vendedor vira validBefore da NOSSA assinatura (SDK)."""
    seletor = checagens.seletor_com_checagens(CAIP2_BASE_MAINNET,
                                              teto_unverified_minor=None)
    with pytest.raises(ValueError, match="validade-excessiva"):
        seletor(2, [_req(USDC_BASE_MAINNET, 10_000, validade_s=10**9)])
    ok = seletor(2, [_req(USDC_BASE_MAINNET, 10_000, validade_s=600)])
    assert int(ok.get_amount()) == 10_000


# ---- furo 8: o seletor padrão de testnet é fail-closed --------------------------


def test_seletor_padrao_testnet_tem_checagens() -> None:
    seletor = checagens.seletor_padrao_testnet()
    # mainnet não passa num cliente de teste; acima de US$ 1 não passa nem na testnet
    with pytest.raises(ValueError):
        seletor(2, [_req(USDC_BASE_MAINNET, 10_000, rede=CAIP2_BASE_MAINNET)])
    with pytest.raises(ValueError, match="payto-nao-verificado-acima-do-teto"):
        seletor(2, [_req(USDC_BASE_SEPOLIA, 5_000_000, rede=CAIP2_BASE_SEPOLIA)])
    ok = seletor(2, [_req(USDC_BASE_SEPOLIA, 10_000, rede=CAIP2_BASE_SEPOLIA)])
    assert str(ok.network) == CAIP2_BASE_SEPOLIA


# ---- furo 6: guarda de URL (anti-SSRF) — IPs literais, sem DNS ------------------


def test_url_segura_recusa_privadas_e_http() -> None:
    recusas = {
        "http://api.example.com/x": "esquema-nao-https",
        "https://localhost/x": "host-local",
        "https://127.0.0.1:8402/x": "ip-nao-publico",
        "https://10.0.0.7/x": "ip-nao-publico",
        "https://169.254.169.254/latest/meta-data": "ip-nao-publico",
        "https://[::1]/x": "ip-nao-publico",
    }
    for url, motivo in recusas.items():
        ok, m = rede_segura.url_segura(url)
        assert not ok and m.startswith(motivo), (url, m)


def test_url_segura_aceita_ip_publico() -> None:
    ok, m = rede_segura.url_segura("https://93.184.216.34/recurso")
    assert ok and m == "ok"


# ---- furo 7: header base64 com teto ---------------------------------------------


def test_header_gigante_nao_e_decodificado() -> None:
    assert not rede_segura.decodificavel(None)
    assert not rede_segura.decodificavel("")
    assert not rede_segura.decodificavel("A" * 100_000)
    assert rede_segura.decodificavel("eyJvayI6IHRydWV9")


# ---- furo 5: leitura de resposta com teto ---------------------------------------


def test_leitura_com_teto_trunca_sem_morrer() -> None:
    transport = httpx.MockTransport(
        lambda _req: httpx.Response(200, content=b"x" * 1_000))
    with httpx.Client(transport=transport) as cli, \
            cli.stream("GET", "https://vendedor.example/paga") as r:
        corpo, truncado = rede_segura.ler_corpo_limitado(r, max_bytes=100)
    assert truncado and len(corpo) == 100

    with httpx.Client(transport=transport) as cli, \
            cli.stream("GET", "https://vendedor.example/paga") as r:
        corpo, truncado = rede_segura.ler_corpo_limitado(r, max_bytes=10_000)
    assert not truncado and corpo == b"x" * 1_000


# ---- furo 2: Settings nunca imprime segredo -------------------------------------


def test_settings_nao_vaza_chave_em_print() -> None:
    chave = "0x" + "ab" * 32
    s = Settings(  # type: ignore[call-arg]  # _env_file é kwarg de runtime do pydantic-settings
        _env_file=None, buyer_pk=SecretStr(chave),
        anthropic_api_key=SecretStr("sk-ant-teste-123"))
    assert chave not in str(s) and chave not in repr(s)
    assert "sk-ant-teste-123" not in str(s) and "sk-ant-teste-123" not in repr(s)
    assert s.buyer_pk.get_secret_value() == chave  # o uso explícito continua possível


# ---- pin do registro ⇔ constantes (envenenamento do pin seria pego aqui) --------


def test_registro_pinado_bate_com_as_constantes() -> None:
    reg = checagens.carregar_registro()
    for rede, contrato in ((CAIP2_BASE_MAINNET, USDC_BASE_MAINNET),
                           (CAIP2_BASE_SEPOLIA, USDC_BASE_SEPOLIA)):
        entrada = reg["ativos"][rede][contrato.lower()]
        assert entrada["decimals"] == USDC_DECIMALS
        assert entrada["symbol"] == "USDC"
