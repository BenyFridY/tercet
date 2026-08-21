"""T1: confere que o Postgres está de pé (SELECT 1 + versão)."""

import psycopg
from rich.console import Console

from mesa.config import Settings

console = Console()


def main() -> None:
    s = Settings()
    with psycopg.connect(s.database_url, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)
        cur.execute("SHOW server_version")
        row = cur.fetchone()
        version = row[0] if row else "?"
    console.print(f"[green]Postgres de pé[/] — server_version {version} ({s.database_url})")


if __name__ == "__main__":
    main()
