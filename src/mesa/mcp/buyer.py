"""Fase 2: o comprador MCP instrumentado — o gancho na fronteira de ferramenta (D-01).

Duas pontes de compatibilidade (achados p/ conformance, T5):
1. O x402MCPClient (SDK) fala o shape WIRE do mcp 1.x (isError/_meta/structuredContent
   como atributos, content como lista de dicts). O SDK mcp 2.0 devolve modelos pydantic
   snake_case — sem o adapter, payment-required passa por resultado comum e o cliente
   NUNCA paga.
2. ClientSession.call_tool do 2.0 recebe (name, arguments, meta=...), nao um dict unico.
"""

import hashlib
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import psycopg
from eth_account import Account
from mcp import ClientSession
from x402 import x402Client
from x402.mcp.client_async import x402MCPClient
from x402.mcp.types import (
    AfterPaymentContext,
    PaymentRequiredContext,
    PaymentRequiredHookResult,
)
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmClientScheme

from mesa import checagens, db, recibo
from mesa.config import CAIP2_BASE_SEPOLIA, USDC_DECIMALS, Settings


class SessionAdapter:
    """Adapta ClientSession (mcp 2.0) ao shape que o x402MCPClient espera (mcp 1.x)."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def call_tool(self, params: dict[str, Any]) -> Any:
        result = await self._session.call_tool(
            params["name"], params.get("arguments") or {}, meta=params.get("_meta")
        )
        d = result.model_dump(by_alias=True)
        return SimpleNamespace(
            content=d.get("content") or [],
            isError=bool(d.get("isError")),
            structuredContent=d.get("structuredContent"),
            **{"_meta": d.get("_meta") or {}},
        )


@dataclass
class CapturedMcp:
    """O que os hooks do cliente MCP capturam de UM tool call pago (uso sequencial)."""

    payment_required: Any = None  # PaymentRequired — a cotacao no transporte MCP
    payload: Any = None  # PaymentPayload assinado — a autorizacao
    settle_claim: dict[str, Any] | None = None  # ALEGACAO do _meta, nao verdade on-chain
    result_meta: dict[str, Any] | None = None  # o _meta INTEIRO (recibos delegados vem nele)

    def reset(self) -> None:
        self.payment_required = None
        self.payload = None
        self.settle_claim = None
        self.result_meta = None


def make_mcp_client(
    settings: Settings, session: ClientSession, captured: CapturedMcp
) -> x402MCPClient:
    signer = EthAccountSigner(Account.from_key(settings.buyer_pk.get_secret_value()))
    # seguranca.md furo 8: nenhum cliente sem checagens — nem no transporte MCP
    payment_client = x402Client(
        payment_requirements_selector=checagens.seletor_padrao_testnet())
    payment_client.register(CAIP2_BASE_SEPOLIA, ExactEvmClientScheme(signer))

    xmcp = x402MCPClient(SessionAdapter(session), payment_client, auto_payment=True)

    def on_payment_required(ctx: PaymentRequiredContext) -> PaymentRequiredHookResult:
        captured.payment_required = ctx.payment_required
        # abort=False + payment=None = so captura; o fluxo segue para o auto_payment
        return PaymentRequiredHookResult()

    def on_after_payment(ctx: AfterPaymentContext) -> None:
        captured.payload = ctx.payment_payload
        captured.settle_claim = (
            ctx.settle_response.model_dump() if ctx.settle_response is not None else None
        )
        captured.result_meta = dict(ctx.result.meta or {})

    xmcp.on_payment_required(on_payment_required)
    xmcp.on_after_payment(on_after_payment)
    return xmcp


def record_mcp_purchase(
    conn: psycopg.Connection[Any],
    *,
    captured: CapturedMcp,
    canonical: str,
    tool_name: str,
    trace_id: str,
    span_id: str,
    result_text: str | None,
    is_error: bool,
) -> str:
    """Grava request SEMPRE; quote+authz so se houve pagamento. Devolve a classe gravada.

    Espelho MCP do buyer.record_purchase: transport='mcp', method='tools/call',
    status_http NULL (D-01 — nao existe HTTP status na fronteira de ferramenta).
    """
    content = result_text.encode() if result_text else None
    delivered = (not is_error) and bool(content)
    rid = db.insert_request(
        conn,
        rail="x402",
        resource_key_hash=hashlib.sha256(canonical.encode()).digest(),  # D-11
        method="tools/call",
        status_http=None,
        body_sha256=hashlib.sha256(content).digest() if content else None,
        body_bytes=len(content) if content is not None else None,
        content_type="application/json",
        delivered=delivered,
        trace_id=trace_id,
        span_id=span_id,
        transport="mcp",
        origin="direct",
        tool_name=tool_name,
    )
    if captured.payment_required is None or captured.payload is None:
        return "sem-pagamento"

    req = captured.payment_required.accepts[0]
    qid = db.insert_quote(
        conn,
        request_id=rid,
        amount_minor=int(req.get_amount()),
        decimals=USDC_DECIMALS,
        asset_network_caip2=str(req.network),
        asset_contract=req.asset,
        pay_to=req.pay_to,
        scheme=req.scheme,
    )
    inner: dict[str, Any] = dict(captured.payload.payload)
    auth: dict[str, Any] = dict(inner.get("authorization") or {})
    db.insert_authz(
        conn,
        quote_id=qid,
        rail="x402",
        payer_ref=str(auth.get("from", "")),
        authorized_max_minor=int(auth.get("value", 0)),
        valid_from_utc=db.ts_from_unix(auth.get("validAfter")),
        valid_until_utc=db.ts_from_unix(auth.get("validBefore")),
        rail_evidence={
            "authorization": auth,
            "signature": inner.get("signature"),
            "settle_claim": captured.settle_claim,  # alegacao; o coletor confirma on-chain
            "transport": "mcp",
        },
        state="authorized",
    )
    return "tripla"


def record_delegated_purchases(
    conn: psycopg.Connection[Any],
    *,
    captured: CapturedMcp,
    trace_id: str,
    span_id: str,
) -> int:
    """T4: grava as compras que o SERVIDOR fez em nosso nome (recibos propagados no _meta).

    A assinatura é verificada ANTES de entrar no livro: recibo cujo signatário não é o
    comprador_delegado declarado é recusado com erro — recibo forjado não vira evidência.
    Devolve quantas compras delegadas entraram.
    """
    envelopes = (captured.result_meta or {}).get("mesa/upstream-receipts") or []
    gravadas = 0
    for env in envelopes:
        rec: dict[str, Any] = dict(env.get("recibo") or {})
        sig = bytes.fromhex(str(env.get("assinatura_hex", "0x"))[2:])
        if not recibo.verificar(rec, sig):
            raise ValueError(
                f"recibo propagado com assinatura inválida (delegado declarado: "
                f"{rec.get('comprador_delegado')}) — recusado, não entra no livro"
            )
        rid = db.insert_request(
            conn,
            rail="x402",
            resource_key_hash=bytes.fromhex(str(rec["recurso_hash"])),
            method=str(rec.get("metodo", "GET")),
            status_http=None,
            body_sha256=bytes.fromhex(str(rec["body_sha256_hex"]))
            if rec.get("body_sha256_hex") else None,
            body_bytes=None,
            content_type=None,
            delivered=True,  # o insumo chegou: a resposta da ferramenta veio dele
            trace_id=trace_id,
            span_id=span_id,
            transport="mcp",
            origin="delegated",
            tool_name=str(rec.get("ferramenta") or "") or None,
            origin_ref=str(rec.get("comprador_delegado") or "") or None,
            origin_receipt_sig=sig,
        )
        qid = db.insert_quote(
            conn,
            request_id=rid,
            amount_minor=int(rec["amount_minor"]),
            decimals=int(rec.get("decimals", USDC_DECIMALS)),
            asset_network_caip2=str(rec["network"]),
            asset_contract=str(rec["asset"]),
            pay_to=str(rec["pay_to"]),
            scheme=str(rec["scheme"]),
        )
        auth: dict[str, Any] = dict(rec.get("authorization") or {})
        db.insert_authz(
            conn,
            quote_id=qid,
            rail="x402",
            payer_ref=str(auth.get("from", "")),
            authorized_max_minor=int(auth.get("value", 0)),
            valid_from_utc=db.ts_from_unix(auth.get("validAfter")),
            valid_until_utc=db.ts_from_unix(auth.get("validBefore")),
            rail_evidence={
                "authorization": auth,  # a chave (authorizer, nonce) p/ o coletor casar
                "recibo_propagado": rec,
                "assinatura_hex": env.get("assinatura_hex"),
                "transport": "mcp",
                "origin": "delegated",
            },
            state="authorized",
        )
        gravadas += 1
    return gravadas


def result_text_of(result: Any) -> str | None:
    """Extrai o texto do primeiro content block (shape wire, pos-adapter)."""
    for item in result.content or []:
        if isinstance(item, dict) and item.get("type") == "text":
            return str(item.get("text", ""))
    return None


def settle_claim_summary(captured: CapturedMcp) -> str:
    if not captured.settle_claim:
        return "sem settle_claim"
    return json.dumps(captured.settle_claim, default=str)[:200]
