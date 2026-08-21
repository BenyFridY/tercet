"""Conformance da NOSSA implementação (mesa.mcp) contra o mesmo spec — dogfood.

A suíte que cobra os outros cobra a gente primeiro. Cenários N1–N5 no nível de shape
(o fluxo completo N6 é provado ponta a ponta nos runs reais: scripts/fase2/*.py).
"""

import json
from typing import Any

from mesa.mcp.seller import MESA_UPSTREAM_META_KEY, _payment_required


class _ReqFake:
    """PaymentRequirements mínimo com a interface que _payment_required usa."""

    def __init__(self, d: dict[str, Any]) -> None:
        self._d = d

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self._d


ACCEPTS = [_ReqFake({"scheme": "exact", "network": "eip155:84532", "amount": "10000"})]


def test_n1_payment_required_e_in_band_is_error() -> None:
    r = _payment_required(list(ACCEPTS), "Payment Required")
    assert r.is_error is True  # N1: tool result, nunca erro JSON-RPC


def test_n2_structured_content_e_texto_json() -> None:
    r = _payment_required(list(ACCEPTS), "Payment Required")
    assert isinstance(r.structured_content, dict)
    assert r.structured_content["x402Version"] == 2
    texto = r.content[0].text  # type: ignore[union-attr]
    assert json.loads(texto)["accepts"], "content[0].text tem que ser o JSON do PaymentRequired"


def test_n4_n5_meta_keys_usadas_sao_as_do_spec() -> None:
    from x402.mcp.constants import MCP_PAYMENT_META_KEY, MCP_PAYMENT_RESPONSE_META_KEY

    assert MCP_PAYMENT_META_KEY == "x402/payment"
    assert MCP_PAYMENT_RESPONSE_META_KEY == "x402/payment-response"
    # a extensão nossa (recibo propagado) usa namespace próprio, sem colidir com o spec
    assert MESA_UPSTREAM_META_KEY == "mesa/upstream-receipts"
