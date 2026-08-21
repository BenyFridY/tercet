"""A extensão OFICIAL `offer-and-receipt` do x402 (D-27: ingerir e emitir os padrões
que já nasceram — nunca formato próprio).

Fonte normativa: coinbase/x402 specs/extensions/extension-offer-and-receipt.md
(baixada em 21/08/2026). Implementa o formato `eip712`:

- Domínio: {name: "x402 offer"|"x402 receipt", version: "1", chainId: 1} — o chainId
  fixo em 1 é INTENCIONAL no spec (EIP-712 aqui é formato de assinatura off-chain;
  a rede do pagamento vai no campo `network` do payload).
- Schemas canônicos (§4.3/§5.3) NÃO viajam no wire — assinante e verificador usam
  os daqui. Campo opcional ausente: validUntil=0 (offer), transaction="" (receipt).
- Autorização do assinante (§4.5.1, caminho simples): signer recuperado == payTo.

Extensão aprovada com ZERO implementações públicas — esta é a primeira do mesa.
"""

from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data

_DOMAIN_TYPE = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
]
TYPES_OFFER = {
    "EIP712Domain": _DOMAIN_TYPE,
    "Offer": [
        {"name": "version", "type": "uint256"},
        {"name": "resourceUrl", "type": "string"},
        {"name": "scheme", "type": "string"},
        {"name": "network", "type": "string"},
        {"name": "asset", "type": "string"},
        {"name": "payTo", "type": "string"},
        {"name": "amount", "type": "string"},
        {"name": "validUntil", "type": "uint256"},
    ],
}
TYPES_RECEIPT = {
    "EIP712Domain": _DOMAIN_TYPE,
    "Receipt": [
        {"name": "version", "type": "uint256"},
        {"name": "network", "type": "string"},
        {"name": "resourceUrl", "type": "string"},
        {"name": "payer", "type": "string"},
        {"name": "issuedAt", "type": "uint256"},
        {"name": "transaction", "type": "string"},
    ],
}
DOMINIO_OFFER = {"name": "x402 offer", "version": "1", "chainId": 1}
DOMINIO_RECEIPT = {"name": "x402 receipt", "version": "1", "chainId": 1}


def _full_message(primary: str, types: dict[str, Any], dominio: dict[str, Any],
                  payload: dict[str, Any]) -> dict[str, Any]:
    return {"types": types, "primaryType": primary, "domain": dominio,
            "message": payload}


def emitir_oferta(pk: str, *, resource_url: str, scheme: str, network: str,
                  asset: str, pay_to: str, amount: str, valid_until: int = 0,
                  accept_index: int | None = None) -> dict[str, Any]:
    """Oferta assinada (§4). `valid_until=0` = sem expiração (regra do spec)."""
    payload = {"version": 1, "resourceUrl": resource_url, "scheme": scheme,
               "network": network, "asset": asset, "payTo": pay_to,
               "amount": amount, "validUntil": valid_until}
    assinada = Account.sign_typed_data(
        pk, full_message=_full_message("Offer", TYPES_OFFER, DOMINIO_OFFER, payload))
    artefato: dict[str, Any] = {"format": "eip712", "payload": payload,
                                "signature": assinada.signature.to_0x_hex()}
    if accept_index is not None:  # conveniência NÃO assinada (§4.1.1)
        artefato["acceptIndex"] = accept_index
    return artefato


def emitir_recibo(pk: str, *, network: str, resource_url: str, payer: str,
                  issued_at: int, transaction: str = "") -> dict[str, Any]:
    """Recibo assinado (§5) — só em sucesso; `transaction=""` = privacidade-mínima."""
    payload = {"version": 1, "network": network, "resourceUrl": resource_url,
               "payer": payer, "issuedAt": issued_at, "transaction": transaction}
    assinada = Account.sign_typed_data(
        pk, full_message=_full_message("Receipt", TYPES_RECEIPT, DOMINIO_RECEIPT,
                                       payload))
    return {"format": "eip712", "payload": payload,
            "signature": assinada.signature.to_0x_hex()}


def signatario(artefato: dict[str, Any]) -> str:
    """Recupera o assinante (§4.5/§5.5): o payload viaja como está — NUNCA reconstruir."""
    if artefato.get("format") != "eip712":
        raise ValueError(f"formato não implementado: {artefato.get('format')}")
    payload = dict(artefato["payload"])
    if "payTo" in payload:  # Offer
        fm = _full_message("Offer", TYPES_OFFER, DOMINIO_OFFER, payload)
    else:
        fm = _full_message("Receipt", TYPES_RECEIPT, DOMINIO_RECEIPT, payload)
    recuperado: str = Account.recover_message(
        encode_typed_data(full_message=fm), signature=artefato["signature"])
    return recuperado


def verificar_oferta(artefato: dict[str, Any]) -> bool:
    """Autorização pelo caminho simples do §4.5.1: signer == payTo."""
    return signatario(artefato).lower() == str(artefato["payload"]["payTo"]).lower()
