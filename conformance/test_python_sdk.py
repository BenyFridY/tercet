"""Conformance do SDK Python `x402==2.20.0` contra o spec vivo (baselines.py).

Convenção da suíte: não-conformidade CONFIRMADA vira teste `xfail(strict=True)` —
a suíte fica verde hoje E quebra no dia em que o SDK consertar (aviso automático de
que a não-conformidade sumiu). Testes sem marca são conformidades que PASSAM: a
suíte mede, não caça.

NC-1  create_payment_wrapper importa `mcp.server.fastmcp` (removido no mcp SDK 2.0)
      -> o caminho OFICIAL de servidor não consegue implementar o spec no MCP atual.
NC-2  o cliente espera o wire 1.x (dicts/isError/_meta como atributos) -> contra os
      objetos pydantic do mcp 2.0, payment-required NÃO é detectado e o cliente trata
      ferramenta paga como grátis (quebra o N6: nunca cria o PaymentPayload).
NC-3  MCP_PAYMENT_REQUIRED_CODE = 402: o spec vivo não define erro JSON-RPC nenhum e
      o único texto que definiu código (SEP-2007, dormente) pedia -32402.
"""

import json

import pytest
from mcp_types import CallToolResult, TextContent
from x402.mcp.types import MCP_PAYMENT_REQUIRED_CODE
from x402.mcp.utils import convert_mcp_result, extract_payment_required_from_result

from conformance.baselines import PAYMENT_REQUIRED_EXEMPLO


def _payment_required_mcp20() -> CallToolResult:
    """O payment-required EXATAMENTE como um servidor mcp 2.0 conforme o emite (N1+N2)."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(PAYMENT_REQUIRED_EXEMPLO))],
        structured_content=PAYMENT_REQUIRED_EXEMPLO,
        is_error=True,
    )


class _WireAntigo:
    """O mesmo payment-required no shape wire 1.x (dicts) que o SDK espera."""

    def __init__(self) -> None:
        self.content = [{"type": "text", "text": json.dumps(PAYMENT_REQUIRED_EXEMPLO)}]
        self.isError = True
        self.structuredContent = PAYMENT_REQUIRED_EXEMPLO
        self._meta: dict[str, object] = {}


@pytest.mark.xfail(
    strict=True,
    reason="NC-1: create_payment_wrapper importa mcp.server.fastmcp, removido no mcp 2.0",
)
def test_nc1_wrapper_de_servidor_funciona_no_mcp_20() -> None:
    from x402.mcp import create_payment_wrapper

    paid = create_payment_wrapper(object(), accepts=[object()])  # decorator factory

    def ferramenta(pergunta: str) -> str:
        return "ok"

    paid(ferramenta)  # <- aqui acontece o `from mcp.server.fastmcp import Context`


@pytest.mark.xfail(
    strict=True,
    reason="NC-2: cliente não detecta payment-required no wire do mcp 2.0 (N6 quebra)",
)
def test_nc2_cliente_detecta_payment_required_no_wire_mcp20() -> None:
    resultado = convert_mcp_result(_payment_required_mcp20())
    pr = extract_payment_required_from_result(resultado)
    assert pr is not None, "payment-required conforme (N1+N2) tratado como resultado comum"


def test_conforme_cliente_detecta_payment_required_no_wire_1x() -> None:
    """Contraprova: no wire 1.x o mesmo payload É detectado — o bug é só de compat 2.0."""
    resultado = convert_mcp_result(_WireAntigo())
    pr = extract_payment_required_from_result(resultado)
    assert pr is not None


def test_conforme_meta_keys_sao_as_do_spec() -> None:
    """N4/N5: as chaves _meta do SDK batem com o texto vivo."""
    from x402.mcp.constants import MCP_PAYMENT_META_KEY, MCP_PAYMENT_RESPONSE_META_KEY

    assert MCP_PAYMENT_META_KEY == "x402/payment"
    assert MCP_PAYMENT_RESPONSE_META_KEY == "x402/payment-response"


@pytest.mark.xfail(
    strict=True,
    reason="NC-3: 402 não corresponde a nenhum texto normativo (vivo: sem erro JSON-RPC; "
    "SEP-2007 dormente: -32402)",
)
def test_nc3_codigo_de_erro_jsonrpc_tem_base_normativa() -> None:
    assert MCP_PAYMENT_REQUIRED_CODE == -32402
