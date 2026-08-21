"""T2 — critério de pronto: paga UMA vez o /brinquedo e prova o recibo on-chain.

Prova exigida pelo PLANO: no MESMO receipt da transação, (a) `Transfer` do USDC
para o payTo do vendedor e (b) `AuthorizationUsed` — o evento que carrega a chave
de join `(authorizer, nonce)` do livro.
"""

import asyncio
import base64
import json
import re
from typing import Any

from eth_account import Account
from eth_typing import HexStr
from rich.console import Console
from web3 import Web3
from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.http.constants import PAYMENT_RESPONSE_HEADER
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmClientScheme

from mesa import checagens
from mesa.config import CAIP2_BASE_SEPOLIA, USDC_BASE_SEPOLIA, Settings

console = Console()
SELLER_URL = "http://127.0.0.1:8402"


def _find_tx_hash(obj: Any) -> str | None:
    """Acha um hash de transação (0x + 64 hex) em qualquer canto do JSON do recibo."""
    text = json.dumps(obj)
    m = re.search(r"0x[0-9a-fA-F]{64}", text)
    return m.group(0) if m else None


async def main() -> None:
    s = Settings()
    if not s.buyer_pk:
        raise SystemExit("BUYER_PK vazio — rode scripts/setup_wallets.py primeiro.")

    signer = EthAccountSigner(Account.from_key(s.buyer_pk.get_secret_value()))
    # seguranca.md furo 8: nenhum cliente sem checagens — nem neste one-shot da Fase 1
    xc = x402Client(payment_requirements_selector=checagens.seletor_padrao_testnet())
    xc.register(CAIP2_BASE_SEPOLIA, ExactEvmClientScheme(signer))

    console.print(f"[bold]1/3[/] chamando {SELLER_URL}/brinquedo (o 402 e o retry são do SDK)…")
    async with x402HttpxClient(xc, base_url=SELLER_URL, timeout=120.0) as http:
        r = await http.get("/brinquedo")

    console.print(f"    status: [bold]{r.status_code}[/] · corpo: {r.text}")
    header = r.headers.get(PAYMENT_RESPONSE_HEADER)
    if r.status_code != 200 or header is None:
        raise SystemExit("Sem 200 + PAYMENT-RESPONSE — o pagamento não aconteceu.")

    receipt_json = json.loads(base64.b64decode(header))
    tx_hash = _find_tx_hash(receipt_json)
    console.print(f"[bold]2/3[/] recibo do settlement (header PAYMENT-RESPONSE): {receipt_json}")
    if tx_hash is None:
        raise SystemExit("PAYMENT-RESPONSE sem hash de transação.")

    console.print(f"[bold]3/3[/] conferindo o receipt on-chain de {tx_hash}…")
    w3 = Web3(Web3.HTTPProvider(s.rpc_url))
    onchain = w3.eth.wait_for_transaction_receipt(HexStr(tx_hash), timeout=120)

    transfer_topic = w3.keccak(text="Transfer(address,address,uint256)")
    auth_topic = w3.keccak(text="AuthorizationUsed(address,bytes32)")
    usdc = USDC_BASE_SEPOLIA.lower()

    transfer_to_payto = False
    authorizer = nonce = None
    for log in onchain["logs"]:
        if log["address"].lower() != usdc:
            continue
        if log["topics"][0] == transfer_topic:
            to_addr = "0x" + log["topics"][2].hex()[-40:]
            if to_addr.lower() == s.seller_payto.lower():
                transfer_to_payto = True
        elif log["topics"][0] == auth_topic:
            authorizer = "0x" + log["topics"][1].hex()[-40:]
            nonce = "0x" + log["topics"][2].hex()

    console.print(f"    Transfer -> payTo do vendedor : {'SIM' if transfer_to_payto else 'NAO'}")
    console.print(f"    AuthorizationUsed no receipt  : {'SIM' if authorizer else 'NAO'}")
    if authorizer:
        console.print(f"    chave de join do livro: (authorizer={authorizer}, nonce={nonce})")
    console.print(f"\n    explorador: https://sepolia.basescan.org/tx/{tx_hash}")

    if transfer_to_payto and authorizer:
        console.print("\n[bold green]T2 FECHADA[/] — EIP-3009 confirmado na testnet. "
                      "O resto do FDS é engenharia nossa.")
    else:
        raise SystemExit("Receipt não tem as duas provas — investigar antes de seguir.")


if __name__ == "__main__":
    asyncio.run(main())
