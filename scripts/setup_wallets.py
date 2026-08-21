"""T1: gera as duas EOAs do FDS 1 (comprador e payTo do vendedor) e escreve o env de segredos.

Idempotente: se o arquivo já tem chaves, NÃO sobrescreve (aborta com aviso).
Imprime só endereços — nunca chaves privadas.

Desde 20/08 o repo vive na raiz x402 (pasta sincronizada pelo OneDrive) — segredos
ficam FORA do sync, em C:\\dev\\mesa.env (o config.py lê de lá com precedência).
"""

from pathlib import Path

from eth_account import Account
from rich.console import Console

console = Console()
ENV_PATH = Path(r"C:\dev\mesa.env")


def main() -> None:
    if ENV_PATH.exists() and "BUYER_PK=" in ENV_PATH.read_text(encoding="utf-8"):
        console.print(f"[yellow].env já tem carteiras — nada a fazer.[/] ({ENV_PATH})")
        console.print("Se quiser gerar novas, apague as linhas *_PK do .env antes.")
        return

    buyer = Account.create()
    seller = Account.create()

    lines = [
        "# Gerado por scripts/setup_wallets.py — NUNCA commitar este arquivo.",
        f"BUYER_PK={buyer.key.hex()}",
        f"BUYER_ADDRESS={buyer.address}",
        f"SELLER_PK={seller.key.hex()}",
        f"SELLER_PAYTO={seller.address}",
        "",
    ]
    existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    ENV_PATH.write_text(existing + "\n".join(lines), encoding="utf-8")

    console.print("[green]Carteiras geradas e gravadas no .env[/]")
    console.print(f"  comprador (cole no faucet): [bold cyan]{buyer.address}[/]")
    console.print(f"  payTo do vendedor:          [bold]{seller.address}[/]")
    console.print("\nFaucet: https://faucet.circle.com -> USDC -> Base Sepolia (20 USDC / 2h)")


if __name__ == "__main__":
    main()
