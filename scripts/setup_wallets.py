"""T1: gera as duas EOAs do FDS 1 (comprador e payTo do vendedor) e escreve o env de segredos.

Idempotente: se o arquivo já tem chaves, NÃO sobrescreve (aborta com aviso).
Imprime só endereços — nunca chaves privadas.

Onde o arquivo de segredos vive (mesma ordem que o config.py lê):
1. `MESA_ENV_FILE` no ambiente, se definido;
2. um env legado fora de pasta sincronizada, se já existir (chave em pasta de
   sync = chave na nuvem — evite);
3. senão, `.env` no diretório atual (o caso de quem clonou o repo agora).
"""

import os
from pathlib import Path

from eth_account import Account
from rich.console import Console

console = Console()

_LEGADO = Path(r"C:\dev\mesa.env")


def _env_path() -> Path:
    via_ambiente = os.environ.get("MESA_ENV_FILE")
    if via_ambiente:
        return Path(via_ambiente)
    return _LEGADO if _LEGADO.exists() else Path(".env")


ENV_PATH = _env_path()


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
