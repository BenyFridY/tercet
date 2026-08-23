"""Fase 12 — re-emite os passaportes (D-08) das 3 carteiras, para a aba 03 risco.

Só leitura do livro + atribuição on-chain dos sem-par + assinatura local.
Nenhuma compra, nenhum gasto. Saída: scripts/fase10/saida/passaporte-*.json
(o app re-verifica offline a cada request).

Uso: uv run python scripts/fase12/emitir_passaportes.py
"""

import json
from pathlib import Path

from web3 import Web3

from mesa import db
from mesa import passaporte as pp
from mesa.config import CAIP2_BASE_MAINNET, CAIP2_BASE_SEPOLIA, Settings

SAIDA = Path(__file__).resolve().parents[1] / "fase10" / "saida"


def main() -> None:
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)
    SAIDA.mkdir(exist_ok=True)
    w3_sep = Web3(Web3.HTTPProvider(s.rpc_url))
    w3_main = Web3(Web3.HTTPProvider(s.rpc_url_mainnet))

    carteiras = [
        ("caos", s.buyer_address, CAIP2_BASE_SEPOLIA, w3_sep,
         s.buyer_pk.get_secret_value()),
        ("mcp", s.mcp_server_address, CAIP2_BASE_SEPOLIA, w3_sep,
         s.mcp_server_pk.get_secret_value()),
        ("censo", s.census_address, CAIP2_BASE_MAINNET, w3_main,
         s.census_pk.get_secret_value()),
    ]
    for nome, addr, rede, w3, pk in carteiras:
        art = pp.emitir(conn, w3, payer_ref=addr, rede=rede, pk=pk)
        (SAIDA / f"passaporte-{nome}.json").write_text(
            json.dumps(art, indent=2, ensure_ascii=False), encoding="utf-8")
        m = art["payload"]["metricas"]
        print(f"{nome}: {m['autorizacoes']} aut · {m['liquidadas']} liq · "
              f"{m['nonces_reusados']} nonce reusado · "
              f"{m['orfaos_chain_inexplicados']} órfã(s) → passaporte-{nome}.json")
    print("passaportes re-emitidos — a aba 03 risco re-verifica na hora")


if __name__ == "__main__":
    main()
