"""Fase 2 / T2: o vendedor MCP — uma ferramenta paga (0,01 USDC, `exact`, Base Sepolia).

O wrapper oficial (x402.mcp.create_payment_wrapper) esta QUEBRADO contra o SDK mcp 2.0:
importa `mcp.server.fastmcp` (removido no 2.0) e extrai o _meta via API pydantic do 1.x
(`meta.model_extra`; no 2.0 o meta e um mapa aberto). Achado registrado para a suite de
conformance (T5). Aqui o fluxo de pagamento usa as primitivas do x402
(verify_payment/settle_payment) direto num handler do mcp 2.0, espelhando a semantica
do wrapper: sem pagamento -> payment-required em CallToolResult isError=true; verify ->
executa -> settle -> resposta com _meta["x402/payment-response"]. Execute-then-settle:
handler que falha NAO liquida (mesma regra do lado HTTP, Tarefa 0 da Fase 1).
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import uvicorn
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp_types import CallToolResult, TextContent
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.clients import x402HttpxClient
from x402.mcp.constants import MCP_PAYMENT_META_KEY, MCP_PAYMENT_RESPONSE_META_KEY
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import PaymentPayload
from x402.schemas.config import ResourceConfig

from mesa import recibo
from mesa.config import CAIP2_BASE_SEPOLIA, USDC_DECIMALS, Settings
from mesa.http.buyer import Captured, make_client

MCP_HOST = "127.0.0.1"
MCP_PORT = 8403  # 8402 e do vendedor HTTP (fase 1) — na T4 os dois rodam JUNTOS
UPSTREAM_BASE = "http://127.0.0.1:8402"  # o fornecedor: o vendedor HTTP da fase 1
UPSTREAM_CANONICAL = f"GET {UPSTREAM_BASE}/brinquedo"
MESA_UPSTREAM_META_KEY = "mesa/upstream-receipts"


def _payment_required(accepts: list[Any], error: str) -> CallToolResult:
    """Espelha o shape do wrapper oficial: PaymentRequired v2 dentro do tool result."""
    body: dict[str, Any] = {
        "x402Version": 2,
        "accepts": [r.model_dump(by_alias=True, exclude_none=True) for r in accepts],
        "error": error,
        "resource": {
            "url": "mcp://tool/consultar",
            "description": "Consulta paga da mesa",
            "mimeType": "application/json",
        },
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(body))],
        structured_content=body,
        is_error=True,
    )


def create_server(settings: Settings) -> MCPServer:
    if not settings.seller_payto:
        raise SystemExit("SELLER_PAYTO vazio — rode scripts/setup_wallets.py primeiro.")

    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
    resource_server = x402ResourceServer(facilitator)
    resource_server.register(CAIP2_BASE_SEPOLIA, ExactEvmServerScheme())  # type: ignore[no-untyped-call]
    resource_server.initialize()  # sincrono: busca supported kinds do facilitator (rede)

    accepts = resource_server.build_payment_requirements(
        ResourceConfig(
            scheme="exact",
            pay_to=settings.seller_payto,
            price="$0.01",
            network=CAIP2_BASE_SEPOLIA,
        )
    )

    server = MCPServer(name="mesa-vendedor-mcp", version="0.0.1")

    @server.tool(
        name="consultar",
        description="Consulta paga: devolve um fato da mesa por 0,01 USDC via x402.",
    )
    async def consultar(pergunta: str, ctx: Context) -> CallToolResult:
        meta = ctx.request_context.meta or {}
        payment_data: Any = meta.get(MCP_PAYMENT_META_KEY)
        if payment_data is None:
            return _payment_required(accepts, "Payment Required")

        try:
            if isinstance(payment_data, str):
                payment_data = json.loads(payment_data)
            payload = PaymentPayload.model_validate(payment_data)
        except Exception as e:  # payload malformado e recusa, nunca 500
            return _payment_required(accepts, f"Invalid payment payload: {e}")

        requirements = resource_server.find_matching_requirements(accepts, payload)
        if requirements is None:
            return _payment_required(accepts, "No matching payment requirements found")

        verify = await resource_server.verify_payment(payload, requirements)
        if not verify.is_valid:
            return _payment_required(
                accepts, f"Payment verification failed: {verify.invalid_reason}"
            )

        # Executa ANTES de liquidar (execute-then-settle): falha aqui = nao cobra.
        # T4: para atender, o servidor COMPRA upstream com a PROPRIA carteira (delegada).
        # Se a compra upstream falha, devolvemos erro SEM liquidar o pagamento do cliente
        # — o prejuizo do que ja pagamos upstream e risco NOSSO (delivered_before_settle).
        recibos_upstream: list[dict[str, Any]] = []
        if settings.mcp_server_pk:
            captured_up = Captured()
            xc_up = make_client(settings, captured_up,
                                pk=settings.mcp_server_pk.get_secret_value())
            try:
                async with x402HttpxClient(xc_up, base_url=UPSTREAM_BASE, timeout=120.0) as http:
                    r_up = await http.get("/brinquedo")
                    corpo_up = r_up.content
                    status_up = r_up.status_code
            except Exception as e:
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(
                        {"error": f"compra upstream falhou: {e}"}))],
                    is_error=True,
                )
            if status_up != 200 or captured_up.req is None or captured_up.payload is None:
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(
                        {"error": f"upstream HTTP {status_up} sem pagamento completo"}))],
                    is_error=True,
                )
            inner_up: dict[str, Any] = dict(captured_up.payload.payload)
            auth_up: dict[str, Any] = dict(inner_up.get("authorization") or {})
            rec: dict[str, Any] = {
                "v": recibo.VERSAO,
                "ferramenta": "consultar",
                "comprador_delegado": settings.mcp_server_address,
                "metodo": "GET",
                # D-11 vale ate no recibo: hash do canonico, nunca a URL em claro
                "recurso_hash": hashlib.sha256(UPSTREAM_CANONICAL.encode()).hexdigest(),
                "amount_minor": int(captured_up.req.get_amount()),
                "decimals": USDC_DECIMALS,
                "asset": captured_up.req.asset,
                "network": str(captured_up.req.network),
                "pay_to": captured_up.req.pay_to,
                "scheme": captured_up.req.scheme,
                "authorization": {
                    k: auth_up.get(k)
                    for k in ("from", "nonce", "validAfter", "validBefore", "value")
                },
                "settle_claim_tx": (captured_up.settle_claim or {}).get("transaction"),
                "body_sha256_hex": hashlib.sha256(corpo_up).hexdigest(),
                "ts_utc": datetime.now(UTC).isoformat(),
            }
            sig = recibo.assinar(rec, settings.mcp_server_pk.get_secret_value())
            recibos_upstream.append({"recibo": rec, "assinatura_hex": "0x" + sig.hex()})

        resultado = {
            "pergunta": pergunta,
            "resposta": "um fato pago da mesa (com insumo comprado upstream)"
            if recibos_upstream else "um fato pago da mesa",
            "fonte": "mesa-vendedor-mcp",
        }

        settle = await resource_server.settle_payment(payload, requirements)
        if not settle.success:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": f"Payment settlement failed: {settle.error_reason}"}
                        ),
                    )
                ],
                is_error=True,
            )

        meta_resposta: dict[str, Any] = {
            MCP_PAYMENT_RESPONSE_META_KEY: settle.model_dump(by_alias=True, exclude_none=True)
        }
        if recibos_upstream:
            meta_resposta[MESA_UPSTREAM_META_KEY] = recibos_upstream
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(resultado))],
            is_error=False,
            _meta=meta_resposta,
        )

    return server


def main() -> None:
    server = create_server(Settings())
    uvicorn.run(server.streamable_http_app(), host=MCP_HOST, port=MCP_PORT, log_level="info")


if __name__ == "__main__":
    main()
