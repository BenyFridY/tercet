"""Backup do livro — pg_dump de dentro do container, gravado em backups/.

docs/seguranca.md furo 9: carimbo prova integridade, mas não RECUPERA dado — sem
dump, disco morto = livro morto. O dump vai para `backups/` (gitignorado; a pasta
vive no OneDrive, então ganha cópia fora da máquina de graça). Não há segredo no
banco por construção (D-11: URLs só como hash; chaves nunca entram).

Uso:  uv run python scripts/backup_db.py            # gera backups/mesa-<data>.dump
Restaurar (documentado, não automatizado — restauração é decisão humana):
  docker exec -i mesa-pg pg_restore -U mesa -d mesa --clean --if-exists < backups/<arquivo>.dump
"""

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DESTINO = Path(__file__).resolve().parents[1] / "backups"


def main() -> None:
    DESTINO.mkdir(exist_ok=True)
    nome = DESTINO / f"mesa-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.dump"
    # -Fc = formato custom (comprimido, restaurável seletivamente via pg_restore)
    r = subprocess.run(
        ["docker", "exec", "mesa-pg", "pg_dump", "-U", "mesa", "-d", "mesa", "-Fc"],
        capture_output=True, check=False)
    if r.returncode != 0 or not r.stdout:
        sys.exit(f"pg_dump falhou (docker de pé?): {r.stderr.decode(errors='replace')[:300]}")
    nome.write_bytes(r.stdout)
    print(f"backup ok: {nome} ({len(r.stdout):,} bytes)")


if __name__ == "__main__":
    main()
