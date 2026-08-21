"""Fase 4 / T3 — fecha o período: raiz de Merkle + carimbo de tempo DUPLO.

Pega TODOS os elos ainda não fechados (canonicalizacao.md, seção Merkle), computa a
raiz, grava `period_close` (nunca reabre) e carimba a MESMA raiz duas vezes:

- **RFC3161** (freeTSA): resposta na hora, DER em `period_stamp` kind='rfc3161'.
  É este que segura o GATE 4.
- **OpenTimestamps**: submete aos calendários (ancora no Bitcoin em ~horas); a prova
  incompleta entra como kind='ots' e o upgrade futuro entra como LINHA NOVA
  kind='ots-upgrade' (append-only — nunca UPDATE).

Uso: uv run python scripts/fase4/fechar_periodo.py
"""

import uuid
from datetime import UTC, datetime

from rich.console import Console

from mesa import carimbo, db, integridade

console = Console()


def main() -> None:
    conn = db.connect()
    hoje = datetime.now(UTC).date()

    with conn.cursor() as cur:
        cur.execute("SELECT period_date, last_seq FROM period_close"
                    " ORDER BY last_seq DESC LIMIT 1")
        anterior = cur.fetchone()
        if anterior and anterior[0] == hoje:
            raise SystemExit(f"período {hoje} já fechado — no máximo 1 fechamento/dia")
        first_seq = int(anterior[1]) + 1 if anterior else 0

        cur.execute("SELECT seq, link_hash FROM ledger_hash WHERE seq >= %s"
                    " ORDER BY seq", (first_seq,))
        elos = cur.fetchall()
        if not elos:
            raise SystemExit("nenhum elo novo desde o último fechamento — nada a fechar")
        last_seq = int(elos[-1][0])
        raiz = integridade.merkle_root([bytes(e[1]) for e in elos])

    console.print(f"período {hoje}: elos {first_seq}..{last_seq} "
                  f"({len(elos)} folhas) · raiz {raiz.hex()[:16]}…")

    # 1º carimbo: RFC3161 (freeTSA) — instantâneo, segura o gate
    tst_der = carimbo.rfc3161_stamp(raiz)
    console.print(f"carimbo RFC3161 ok ({len(tst_der)} bytes DER)")

    # 2º carimbo: OpenTimestamps (prova completa vem em ~horas; falha não trava o gate)
    ots_proof, aceitaram = carimbo.ots_stamp(raiz)
    if ots_proof:
        console.print(f"carimbo OTS submetido ({len(ots_proof)} bytes; "
                      f"{len(aceitaram)}/{len(carimbo.CALENDARIOS)} calendários)")
    else:
        console.print("[yellow]OTS falhou em todos os calendários — "
                      "seguindo só com RFC3161; re-tentar com ots_stamp.py[/yellow]")

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO period_close (period_date, first_seq, last_seq, merkle_root,"
            " closed_utc) VALUES (%s,%s,%s,%s,%s)",
            (hoje, first_seq, last_seq, raiz, db.now_utc()),
        )
        cur.execute(
            "INSERT INTO period_stamp (id, period_date, kind, proof, ts_utc)"
            " VALUES (%s,%s,%s,%s,%s)",
            (uuid.uuid4(), hoje, "rfc3161", tst_der, db.now_utc()),
        )
        if ots_proof:
            cur.execute(
                "INSERT INTO period_stamp (id, period_date, kind, proof, ts_utc)"
                " VALUES (%s,%s,%s,%s,%s)",
                (uuid.uuid4(), hoje, "ots", ots_proof, db.now_utc()),
            )
    conn.commit()
    console.print(f"[bold green]período {hoje} FECHADO: seq {first_seq}..{last_seq}, "
                  f"raiz carimbada {'2×' if ots_proof else '1× (RFC3161)'}[/bold green]")


if __name__ == "__main__":
    main()
