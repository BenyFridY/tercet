"""Fase 4 / T2 — backfill: o livro das Fases 1–3 entra na corrente de hash.

Idempotente: genesis com ON CONFLICT; linha que já tem elo (UNIQUE table_name,row_id)
é pulada. A ordem é a da canonicalizacao.md (timestamp natural; empate/sem timestamp →
row_id lexicográfico) — decisão IRREVERSÍVEL, gravada no próprio genesis.

No fim, AUTOVERIFICA: recomputa a corrente inteira do zero e confere cada elo.

Uso: uv run python scripts/fase4/backfill_corrente.py
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from mesa import db, integridade

console = Console()
DOC_CANON = Path(__file__).resolve().parents[2] / "docs" / "canonicalizacao.md"

# timestamp natural por tabela (None = só row_id lexicográfico)
TS_NATURAL: dict[str, str | None] = {
    "span": "started_utc",
    "request": "ts_utc",
    "quote": None,
    "authz": None,
    "settlement": "block_ts_utc",
    "settlement_leg": None,
    "verification": "verified_at_utc",
    "authz_event": "ts_utc",
    "settlement_event": "ts_utc",
}
ORDEM_TABELAS = ["span", "request", "quote", "authz", "settlement",
                 "settlement_leg", "verification", "authz_event", "settlement_event"]


def main() -> None:
    conn = db.connect()
    aplicadas = db.apply_migrations(conn)
    if aplicadas:
        console.print(f"migrations aplicadas: {aplicadas}")

    canon_hash = hashlib.sha256(DOC_CANON.read_bytes()).hexdigest()
    genesis_texto = (
        "mesa — genesis da corrente de hash (Fase 4)\n"
        "data: 2026-08-21\n"
        "regra de backfill: docs/canonicalizacao.md, seção 'Ordem do backfill'\n"
        f"sha256(docs/canonicalizacao.md) = {canon_hash}\n"
    )
    integridade.genesis(conn, genesis_texto)

    with conn.cursor() as cur:
        cur.execute("SELECT table_name, row_id FROM ledger_hash")
        ja_tem = {(r[0], r[1]) for r in cur.fetchall()}

    total = pulados = 0
    for tabela in ORDEM_TABELAS:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {tabela}")  # noqa: S608 — nome vem da lista fixa
            assert cur.description is not None
            colunas = [d.name for d in cur.description]
            linhas = [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]

        ts_campo = TS_NATURAL[tabela]

        def chave(linha: dict[str, Any], _c: str | None = ts_campo,
                  _t: str = tabela) -> tuple[datetime, str]:
            ts = linha.get(_c) if _c else None
            return (ts if isinstance(ts, datetime) else datetime.min.replace(tzinfo=UTC),
                    integridade.row_id_de(_t, linha))

        for linha in sorted(linhas, key=chave):
            rid = integridade.row_id_de(tabela, linha)
            if (tabela, rid) in ja_tem:
                pulados += 1
                continue
            integridade.registrar_elo(conn, tabela, linha)
            total += 1
        conn.commit()
        console.print(f"{tabela}: {len(linhas)} linhas na tabela")

    console.print(f"elos novos: {total} · já tinham elo: {pulados}")

    # autoverificação: recomputa a corrente INTEIRA e confere elo a elo
    with conn.cursor() as cur:
        cur.execute("SELECT seq, row_hash, prev_hash, link_hash FROM ledger_hash"
                    " ORDER BY seq")
        elos = cur.fetchall()
    assert elos and int(elos[0][0]) == 0, "sem genesis"
    prev = integridade.ZERO32
    for seq, rh, ph, lh in elos:
        assert bytes(ph) == prev, f"elo {seq}: prev_hash não bate"
        esperado = hashlib.sha256(prev + bytes(rh)).digest()
        assert bytes(lh) == esperado, f"elo {seq}: link_hash não bate"
        prev = bytes(lh)
    seqs = [int(e[0]) for e in elos]
    assert seqs == list(range(len(seqs))), "buraco na sequência"
    console.print(f"[bold green]corrente ÍNTEGRA: {len(elos)} elos verificados "
                  f"(genesis + {len(elos) - 1} linhas)[/bold green]")


if __name__ == "__main__":
    main()
