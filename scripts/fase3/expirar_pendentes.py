"""Fase 3 (vigilância) — encerra autorizações do censo que EXPIRARAM sem liquidar.

Uma autorização EIP-3009 com `validBefore` no passado não pode mais ser usada
on-chain — "pendente" vira "expirada": o vendedor não cobrou e NÃO PODE mais cobrar.
Registro do jeito da Fase 4: evento `authz_event(kind='failed')` append-only (com o
motivo no detail) + a coluna de compatibilidade acompanha.

Idempotente: só toca em authz state='authorized' com valid_until_utc < now().

Uso: uv run python scripts/fase3/expirar_pendentes.py
"""

from rich.console import Console

from mesa import db
from mesa.config import Settings

console = Console()


def main() -> None:
    s = Settings()
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT a.id, q.amount_minor, a.valid_until_utc FROM authz a"
            " JOIN quote q ON q.id = a.quote_id"
            " WHERE a.state = 'authorized' AND a.valid_until_utc < now()"
            " AND lower(a.payer_ref) = lower(%s)",
            (s.census_address,),
        )
        expiradas = cur.fetchall()
    if not expiradas:
        console.print("nenhuma autorização do censo expirada em aberto")
        return
    for aid, valor, valid_until in expiradas:
        db.insert_authz_event(
            conn, authorization_id=aid, kind="failed",
            detail={"motivo": "autorização expirou sem liquidação on-chain "
                              "(validBefore no passado — não pode mais ser usada)",
                    "valid_until_utc": valid_until.isoformat()})
        with conn.cursor() as cur:  # coluna de compatibilidade (verdade = o evento)
            cur.execute("UPDATE authz SET state='failed' WHERE id=%s", (aid,))
        conn.commit()
        console.print(f"expirada: authz {str(aid)[:8]}… (US$ {int(valor) / 1e6:.4f}) "
                      f"— evento 'failed' gravado, vigilância encerrada")


if __name__ == "__main__":
    main()
