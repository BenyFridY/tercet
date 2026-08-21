"""Fase 3 / T1 — smoke do coletor na MAINNET. Só LEITURA on-chain; zero escrita no banco.

Prova três coisas antes de qualquer centavo:
1. O RPC da mainnet responde e é mesmo a Base (chain_id 8453).
2. O USDC canônico da Circle é o que dizemos que é (decimals()=6, symbol()='USDC'
   lidos DO CONTRATO — regra 2 da fase3.md, mini-antecipação da Fase 5).
3. O caminho do coletor-pagador funciona: acha um AuthorizationUsed recente de
   TERCEIROS, extrai (authorizer, nonce, tx) e re-busca FILTRANDO por aquele
   authorizer — a mesma tx tem que voltar. É exatamente o filtro que usaremos
   com a NOSSA carteira na T5.

Uso: uv run python scripts/fase3/coletor_smoke.py
"""

import time
from typing import Any

from hexbytes import HexBytes
from rich.console import Console
from web3 import Web3
from web3.types import FilterParams

from mesa.collector import AUTH_USED_SIG, _addr_topic
from mesa.config import CHAIN_ID_BASE_MAINNET, USDC_BASE_MAINNET, Settings

console = Console()
# RPC público 500a em janelas grandes sem filtro de authorizer — janela pequena,
# varrendo de trás pra frente, parando no primeiro evento (o coletor real usa
# filtro de 2 topics, que é leve; a janela grande só machuca AQUI, no smoke).
JANELA = 250          # blocos por consulta (~8min de Base)
MAX_JANELAS = 40      # até ~10k blocos (~5h30) para trás


def _logs_com_retry(w3: Web3, params: FilterParams) -> list[Any]:
    for tentativa in range(3):
        try:
            return list(w3.eth.get_logs(params))
        except Exception:  # noqa: BLE001 — RPC público oscila; 3 tentativas e desiste
            if tentativa == 2:
                raise
            time.sleep(2 * (tentativa + 1))
    return []


def main() -> None:
    s = Settings()
    w3 = Web3(Web3.HTTPProvider(s.rpc_url_mainnet))

    # 1. rede certa
    chain_id = w3.eth.chain_id
    assert chain_id == CHAIN_ID_BASE_MAINNET, f"chain_id {chain_id} != {CHAIN_ID_BASE_MAINNET}"
    latest = w3.eth.block_number
    console.print(f"[1/3] Base mainnet ok — chain_id {chain_id}, bloco {latest}")

    # 2. USDC canônico conferido NO CONTRATO (nunca confiar no símbolo de um índice)
    usdc = Web3.to_checksum_address(USDC_BASE_MAINNET)
    erc20_abi = [
        {"name": "decimals", "inputs": [], "outputs": [{"type": "uint8"}],
         "stateMutability": "view", "type": "function"},
        {"name": "symbol", "inputs": [], "outputs": [{"type": "string"}],
         "stateMutability": "view", "type": "function"},
    ]
    contrato = w3.eth.contract(address=usdc, abi=erc20_abi)
    decimals = contrato.functions.decimals().call()
    symbol = contrato.functions.symbol().call()
    assert decimals == 6, f"decimals {decimals} != 6"
    assert symbol == "USDC", f"symbol {symbol!r} != 'USDC'"
    console.print(f"[2/3] USDC canônico ok — {usdc} · decimals=6 · symbol=USDC (on-chain)")

    # 3. o filtro por authorizer acha uma tx conhecida
    auth_topic = w3.keccak(text=AUTH_USED_SIG)
    eventos: list[Any] = []
    varridos = 0
    to = int(latest)
    for _ in range(MAX_JANELAS):
        frm = to - JANELA
        eventos = _logs_com_retry(w3, {
            "address": usdc, "fromBlock": frm, "toBlock": to, "topics": [auth_topic],
        })
        varridos += JANELA
        if eventos:
            break
        to = frm - 1
    assert eventos, f"nenhum AuthorizationUsed em ~{varridos} blocos — RPC ruim?"
    alvo = eventos[-1]  # o mais recente
    authorizer = "0x" + alvo["topics"][1].hex()[-40:]
    tx_alvo = HexBytes(alvo["transactionHash"])
    bloco_alvo = int(alvo["blockNumber"])

    refiltrado = _logs_com_retry(w3, {
        "address": usdc, "fromBlock": bloco_alvo, "toBlock": bloco_alvo,
        "topics": [auth_topic, _addr_topic(authorizer)],
    })
    achou = any(HexBytes(lg["transactionHash"]) == tx_alvo for lg in refiltrado)
    assert achou, "re-busca filtrada por authorizer NÃO devolveu a tx alvo"
    console.print(
        f"[3/3] filtro por authorizer ok — {len(eventos)} AuthorizationUsed em ~{varridos} "
        f"blocos; tx conhecida {tx_alvo.hex()[:18]}… reencontrada filtrando por "
        f"{authorizer[:10]}…"
    )
    console.print("[bold green]smoke mainnet VERDE — T1 pronta[/bold green]")


if __name__ == "__main__":
    main()
