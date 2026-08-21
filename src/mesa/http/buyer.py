"""O comprador instrumentado — lifecycle hooks do SDK gravando a tripla no livro (D-30).

Usado pelo loop normal (scripts/buyer.py) e pelo caos (scripts/chaos_run.py).
"""

import hashlib
from dataclasses import dataclass
from typing import Any

import psycopg
from eth_account import Account
from x402 import x402Client
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.schemas.hooks import PaymentCreatedContext, PaymentResponseContext

from mesa import db
from mesa.config import CAIP2_BASE_SEPOLIA, USDC_DECIMALS, Settings


@dataclass
class Captured:
    """O que os hooks capturam de UM pagamento (uso sequencial)."""

    req: Any = None            # PaymentRequirements selecionado (a cotação)
    payload: Any = None        # PaymentPayload assinado (a autorização)
    settle_claim: dict[str, Any] | None = None  # ALEGAÇÃO do header, não verdade on-chain

    def reset(self) -> None:
        self.req = None
        self.payload = None
        self.settle_claim = None


def make_client(settings: Settings, captured: Captured, *, pk: str | None = None) -> x402Client:
    """pk=None -> carteira do comprador; o servidor MCP passa a PRÓPRIA (compra delegada, T4)."""
    signer = EthAccountSigner(Account.from_key(pk or settings.buyer_pk))
    xc = x402Client()
    xc.register(CAIP2_BASE_SEPOLIA, ExactEvmClientScheme(signer))

    def after_creation(ctx: PaymentCreatedContext) -> None:
        captured.req = ctx.selected_requirements
        captured.payload = ctx.payment_payload

    def on_response(ctx: PaymentResponseContext) -> None:
        captured.settle_claim = (
            ctx.settle_response.model_dump() if ctx.settle_response is not None else None
        )

    xc.on_after_payment_creation(after_creation)
    xc.on_payment_response(on_response)
    return xc


def resource_hash(canonical: str) -> bytes:
    """D-11: só o hash do canônico entra no banco."""
    return hashlib.sha256(canonical.encode()).digest()


def record_purchase(
    conn: psycopg.Connection[Any],
    *,
    captured: Captured,
    canonical: str,
    trace_id: str,
    span_id: str,
    status_http: int | None,
    content: bytes | None,
    content_type: str | None,
    method: str = "GET",
) -> str:
    """Grava request SEMPRE; quote+authz só se os hooks dispararam. Devolve a classe gravada."""
    delivered = status_http == 200 and bool(content)
    rid = db.insert_request(
        conn, rail="x402", resource_key_hash=resource_hash(canonical), method=method,
        status_http=status_http,
        body_sha256=hashlib.sha256(content).digest() if content else None,
        body_bytes=len(content) if content is not None else None,
        content_type=content_type, delivered=delivered,
        trace_id=trace_id, span_id=span_id, transport="http", origin="direct",
    )
    if captured.req is None or captured.payload is None:
        return "sem-pagamento"

    req = captured.req
    qid = db.insert_quote(
        conn, request_id=rid, amount_minor=int(req.get_amount()), decimals=USDC_DECIMALS,
        asset_network_caip2=str(req.network), asset_contract=req.asset,
        pay_to=req.pay_to, scheme=req.scheme,
    )
    inner: dict[str, Any] = dict(captured.payload.payload)
    auth: dict[str, Any] = dict(inner.get("authorization") or {})
    db.insert_authz(
        conn, quote_id=qid, rail="x402", payer_ref=str(auth.get("from", "")),
        authorized_max_minor=int(auth.get("value", 0)),
        valid_from_utc=db.ts_from_unix(auth.get("validAfter")),
        valid_until_utc=db.ts_from_unix(auth.get("validBefore")),
        rail_evidence={
            "authorization": auth,
            "signature": inner.get("signature"),
            "settle_claim": captured.settle_claim,  # alegação; o coletor confirma (T4)
        },
        state="authorized",
    )
    return "tripla"
