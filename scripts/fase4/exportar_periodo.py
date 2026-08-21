"""Fase 4 / T4 — exporta um período fechado como dump JSON auto-contido.

O dump é o que um TERCEIRO recebe: os elos, as linhas em forma canônica (o objeto
exato que entra no RFC 8785), a raiz de Merkle e os carimbos. O verificador offline
(verificador/verificar.py) valida o dump SEM banco, SEM rede e SEM importar o mesa.

Nota de desenho: o row_hash do genesis é ÂNCORA (o texto de genesis não viaja no
dump). Adulterar o genesis exigiria recomputar a corrente inteira — e aí a raiz não
bate mais com os carimbos de tempo, que são o ponto de confiança externo.

Uso: uv run python scripts/fase4/exportar_periodo.py [YYYY-MM-DD]
"""

import base64
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from rich.console import Console

from mesa import db, integridade

console = Console()
DIR = Path(__file__).parent


def main() -> None:
    conn = db.connect()
    with conn.cursor() as cur:
        if len(sys.argv) > 1:
            alvo = date.fromisoformat(sys.argv[1])
            cur.execute("SELECT period_date, first_seq, last_seq, merkle_root,"
                        " closed_utc FROM period_close WHERE period_date=%s", (alvo,))
        else:
            cur.execute("SELECT period_date, first_seq, last_seq, merkle_root,"
                        " closed_utc FROM period_close ORDER BY period_date DESC LIMIT 1")
        p = cur.fetchone()
        if p is None:
            raise SystemExit("nenhum período fechado — rodar fechar_periodo.py")
        period_date, first_seq, last_seq, raiz, closed_utc = p

        cur.execute("SELECT kind, proof, ts_utc FROM period_stamp WHERE period_date=%s"
                    " ORDER BY ts_utc", (period_date,))
        stamps = [{"kind": r[0], "proof_b64": base64.b64encode(bytes(r[1])).decode(),
                   "ts_utc": r[2].isoformat()} for r in cur.fetchall()]

        cur.execute("SELECT seq, table_name, row_id, row_hash, prev_hash, link_hash,"
                    " ts_utc FROM ledger_hash WHERE seq BETWEEN %s AND %s ORDER BY seq",
                    (first_seq, last_seq))
        elos = [{"seq": int(r[0]), "table_name": r[1], "row_id": r[2],
                 "row_hash": bytes(r[3]).hex(), "prev_hash": bytes(r[4]).hex(),
                 "link_hash": bytes(r[5]).hex(), "ts_utc": r[6].isoformat()}
                for r in cur.fetchall()]

        # as linhas, na forma canônica exata (o verificador só re-serializa e hasheia)
        linhas: dict[str, Any] = {}
        for e in elos:
            t = e["table_name"]
            if t == "genesis":
                continue
            pk_cols = integridade.PK[t]
            partes = e["row_id"].split("|")
            cond = " AND ".join(f"{c}::text = %s" for c in pk_cols)
            cur.execute(f"SELECT * FROM {t} WHERE {cond}", partes)  # noqa: S608
            assert cur.description is not None
            colunas = [d.name for d in cur.description]
            row = cur.fetchone()
            assert row is not None, f"linha sumiu: {t}/{e['row_id']}"
            linha = dict(zip(colunas, row, strict=True))
            linhas[f"{t}|{e['row_id']}"] = integridade.objeto_canonico(t, linha)

    dump = {
        "formato": "mesa-dump-periodo-v1",
        "period": {"period_date": period_date.isoformat(), "first_seq": int(first_seq),
                   "last_seq": int(last_seq), "merkle_root": bytes(raiz).hex(),
                   "closed_utc": closed_utc.isoformat()},
        "stamps": stamps,
        "elos": elos,
        "linhas": linhas,
    }
    saida = DIR / f"dump_periodo_{period_date.isoformat()}.json"
    saida.write_text(json.dumps(dump, indent=1, ensure_ascii=False), encoding="utf-8")
    console.print(f"dump: {saida} · {len(elos)} elos · {len(linhas)} linhas · "
                  f"{len(stamps)} carimbos")


if __name__ == "__main__":
    main()
