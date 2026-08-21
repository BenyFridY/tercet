"""Fase 4 — carimba com OpenTimestamps os períodos fechados que ainda não têm prova OTS.

A prova entra como period_stamp kind='ots' (linha nova, nunca UPDATE). O upgrade
futuro (quando os calendários ancorarem no Bitcoin) entra como kind='ots-upgrade'.

Uso: uv run python scripts/fase4/ots_stamp.py
"""

import uuid
from typing import Any

from rich.console import Console

from mesa import carimbo, db

console = Console()


def main() -> None:
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pc.period_date, pc.merkle_root FROM period_close pc"
            " WHERE NOT EXISTS (SELECT 1 FROM period_stamp ps"
            "  WHERE ps.period_date = pc.period_date AND ps.kind = 'ots')"
            " ORDER BY pc.period_date"
        )
        pendentes: list[tuple[Any, bytes]] = [(r[0], bytes(r[1])) for r in cur.fetchall()]
    if not pendentes:
        console.print("nenhum período sem prova OTS")
        return
    for period_date, raiz in pendentes:
        prova, aceitaram = carimbo.ots_stamp(raiz)
        if prova is None:
            console.print(f"[red]{period_date}: todos os calendários falharam[/red]")
            continue
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO period_stamp (id, period_date, kind, proof, ts_utc)"
                " VALUES (%s,%s,%s,%s,%s)",
                (uuid.uuid4(), period_date, "ots", prova, db.now_utc()),
            )
        conn.commit()
        console.print(f"[green]{period_date}: prova OTS gravada ({len(prova)} bytes; "
                      f"{len(aceitaram)}/{len(carimbo.CALENDARIOS)} calendários; "
                      f"ancora no Bitcoin em ~horas)[/green]")


if __name__ == "__main__":
    main()
