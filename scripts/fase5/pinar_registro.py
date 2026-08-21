"""Fase 5 / T1 — pina o registro de ativos canônicos LENDO OS CONTRATOS (D-07).

Roda ONLINE uma única vez (e a cada mudança deliberada): lê `decimals()` e `symbol()`
dos contratos canônicos nas duas redes e grava `src/mesa/registro_ativos.json`,
VERSIONADO no repo. As checagens (mesa/checagens.py) só LEEM o arquivo — a decisão
de compra roda 100% offline, point-in-time.

Se o que está na chain divergir do esperado, o script FALHA — nunca pina lixo.

Uso: uv run python scripts/fase5/pinar_registro.py
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from web3 import Web3

from mesa.config import (
    CAIP2_BASE_MAINNET,
    CAIP2_BASE_SEPOLIA,
    USDC_BASE_MAINNET,
    USDC_BASE_SEPOLIA,
    Settings,
)

console = Console()
SAIDA = Path(__file__).resolve().parents[2] / "src" / "mesa" / "registro_ativos.json"
ERC20_ABI = [
    {"name": "decimals", "inputs": [], "outputs": [{"type": "uint8"}],
     "stateMutability": "view", "type": "function"},
    {"name": "symbol", "inputs": [], "outputs": [{"type": "string"}],
     "stateMutability": "view", "type": "function"},
]
ESPERADOS = [  # (caip2, rpc_attr, endereço, symbol esperado, nome humano)
    (CAIP2_BASE_SEPOLIA, "rpc_url", USDC_BASE_SEPOLIA, "USDC",
     "USDC de teste (Circle, Base Sepolia)"),
    (CAIP2_BASE_MAINNET, "rpc_url_mainnet", USDC_BASE_MAINNET, "USDC",
     "USDC canônico (Circle, Base mainnet)"),
]


def _call_com_retry(fn: Any) -> Any:
    for tentativa in range(4):
        try:
            return fn.call()
        except Exception:  # noqa: BLE001 — RPC público oscila (503); backoff e repete
            if tentativa == 3:
                raise
            time.sleep(3 * (tentativa + 1))
    return None


def main() -> None:
    s = Settings()
    ativos: dict[str, dict[str, dict[str, object]]] = {}
    for caip2, rpc_attr, endereco, symbol_esperado, nome in ESPERADOS:
        w3 = Web3(Web3.HTTPProvider(getattr(s, rpc_attr)))
        contrato = w3.eth.contract(
            address=Web3.to_checksum_address(endereco), abi=ERC20_ABI)
        decimals = int(_call_com_retry(contrato.functions.decimals()))
        symbol = str(_call_com_retry(contrato.functions.symbol()))
        assert symbol == symbol_esperado, f"{caip2}: symbol {symbol!r} != esperado"
        assert decimals == 6, f"{caip2}: decimals {decimals} != 6"
        ativos.setdefault(caip2, {})[endereco.lower()] = {
            "symbol": symbol, "decimals": decimals, "nome": nome,
        }
        console.print(f"{caip2}: {endereco[:10]}… → {symbol}/{decimals} ✓ (on-chain)")

    SAIDA.write_text(json.dumps({
        "pinado_utc": datetime.now(UTC).isoformat(),
        "metodo": "decimals()/symbol() lidos DOS CONTRATOS via eth_call "
                  "(scripts/fase5/pinar_registro.py); D-07: endereço é identidade, "
                  "símbolo nunca decide nada",
        "ativos": ativos,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[bold green]registro pinado: {SAIDA}[/bold green]")


if __name__ == "__main__":
    main()
