"""Prepara um banco ZERADO de ponta a ponta (o passo 1 do exemplo do README).

O que faz, idempotente: (1) confere que o Postgres responde; (2) aplica as
migrations que faltarem; (3) cria o GENESIS da corrente de hash — sem ele o
livro se recusa a escrever ("corrente sem genesis"), e um terceiro seguindo só
o README travaria aqui (achado do GATE 12 simulado, 24/08/2026).

O texto do genesis é O MESMO do backfill da Fase 4 (a âncora é o hash do doc de
canonicalização, não dado de ninguém) — os dois caminhos produzem o elo 0 idêntico.
"""

import hashlib
from pathlib import Path

from rich.console import Console

from mesa import db, integridade

console = Console()
DOC_CANON = Path(__file__).resolve().parents[1] / "docs" / "canonicalizacao.md"


def main() -> None:
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute("SHOW server_version")
        row = cur.fetchone()
        version = row[0] if row else "?"
    console.print(f"[green]Postgres de pé[/] — server_version {version}")

    aplicadas = db.apply_migrations(conn)
    console.print(f"migrations aplicadas agora: {aplicadas or 'nenhuma (já em dia)'}")

    canon_hash = hashlib.sha256(DOC_CANON.read_bytes()).hexdigest()
    genesis_texto = (
        "mesa — genesis da corrente de hash (Fase 4)\n"
        "data: 2026-08-21\n"
        "regra de backfill: docs/canonicalizacao.md, seção 'Ordem do backfill'\n"
        f"sha256(docs/canonicalizacao.md) = {canon_hash}\n"
    )
    integridade.genesis(conn, genesis_texto)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM ledger_hash")
        row = cur.fetchone()
        elos = int(row[0]) if row else 0
    console.print(f"[green]corrente pronta[/] — {elos} elo(s); o livro aceita escrita")
    conn.close()


if __name__ == "__main__":
    main()
