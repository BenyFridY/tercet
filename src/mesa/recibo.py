"""O recibo propagado v0 (D-13): o servidor MCP assina o que comprou em nosso nome.

Formato mínimo para a Fase 2 — o formato FORMAL (offer-and-receipt, JWS, rfc8785)
é a Fase 4. Aqui: JSON canônico (chaves ordenadas, separadores compactos) assinado
com EIP-191 (personal_sign) pela chave do servidor. Verificar = recuperar o endereço
e comparar com quem o recibo DIZ que comprou.
"""

import json
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct

VERSAO = "mesa-recibo-v0"


def canonico(recibo: dict[str, Any]) -> bytes:
    return json.dumps(recibo, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def assinar(recibo: dict[str, Any], pk: str) -> bytes:
    signed = Account.sign_message(encode_defunct(canonico(recibo)), pk)
    return bytes(signed.signature)


def signatario(recibo: dict[str, Any], assinatura: bytes) -> str:
    """Endereço recuperado da assinatura. Compare com recibo['comprador_delegado']."""
    return str(Account.recover_message(encode_defunct(canonico(recibo)), signature=assinatura))


def verificar(recibo: dict[str, Any], assinatura: bytes) -> bool:
    try:
        esperado = str(recibo.get("comprador_delegado", ""))
        return signatario(recibo, assinatura).lower() == esperado.lower() and bool(esperado)
    except Exception:
        return False
