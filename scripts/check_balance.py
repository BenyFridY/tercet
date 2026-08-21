"""T1 — critério de pronto: imprime o saldo USDC do comprador via balanceOf.

Se isto roda, RPC, chainId, endereço e contrato foram conferidos de uma vez.
"""

from decimal import Decimal

from rich.console import Console
from web3 import Web3

from mesa.config import CHAIN_ID_BASE_SEPOLIA, USDC_BASE_SEPOLIA, USDC_DECIMALS, Settings

ERC20_MIN_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
]

console = Console()


def main() -> None:
    s = Settings()
    if not s.buyer_address:
        raise SystemExit("BUYER_ADDRESS vazio — rode scripts/setup_wallets.py primeiro.")

    w3 = Web3(Web3.HTTPProvider(s.rpc_url))
    chain_id = w3.eth.chain_id
    if chain_id != CHAIN_ID_BASE_SEPOLIA:
        raise SystemExit(
            f"RPC errado: chainId={chain_id}, esperado {CHAIN_ID_BASE_SEPOLIA} (Base Sepolia)."
        )

    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_BASE_SEPOLIA), abi=ERC20_MIN_ABI)

    # D-07 na prática, desde o dia 1: decimais lidos do CONTRATO, nunca aceitos de cotação.
    onchain_decimals = usdc.functions.decimals().call()
    if onchain_decimals != USDC_DECIMALS:
        raise SystemExit(
            f"decimals() on-chain = {onchain_decimals}, esperado {USDC_DECIMALS} — "
            "endereço de contrato errado?"
        )

    raw = usdc.functions.balanceOf(Web3.to_checksum_address(s.buyer_address)).call()
    human = Decimal(raw) / Decimal(10**onchain_decimals)

    console.print(f"rede      : Base Sepolia (chainId {chain_id}) via {s.rpc_url}")
    console.print(f"contrato  : {USDC_BASE_SEPOLIA} (decimals on-chain: {onchain_decimals})")
    console.print(f"comprador : {s.buyer_address}")
    console.print(f"saldo     : [bold green]{human} USDC[/] (raw {raw})")
    if raw == 0:
        console.print("\n[yellow]Saldo zero — pegue 20 USDC em https://faucet.circle.com "
                      "(USDC -> Base Sepolia) e rode de novo.[/]")


if __name__ == "__main__":
    main()
