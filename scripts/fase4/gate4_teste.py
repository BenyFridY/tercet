"""Fase 4 / T4 — o teste do GATE 4: o verificador detecta 1 bit alterado.

Roda o verificador como um TERCEIRO rodaria (subprocess, sem imports do mesa):
1. no dump limpo → tem que dar VERDE;
2. num dump com EXATAMENTE 1 bit virado numa linha do meio → tem que dar VERMELHO
   apontando a seq certa.

Uso: uv run python scripts/fase4/gate4_teste.py [dump.json]
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()
DIR = Path(__file__).parent
VERIFICADOR = DIR.parents[1] / "verificador" / "verificar.py"


def _rodar(dump: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(VERIFICADOR), str(dump)],
                       capture_output=True, text=True, timeout=300, check=False)
    return r.returncode, r.stdout + r.stderr


def main() -> None:
    dump_path = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(
        DIR.glob("dump_periodo_*.json"))[-1]

    # 1. dump limpo → VERDE
    codigo, saida = _rodar(dump_path)
    assert codigo == 0 and "VERDE" in saida, f"dump limpo reprovou:\n{saida}"
    console.print(f"[1/2] dump limpo: VERDE ({dump_path.name})")

    # 2. vira 1 bit numa linha do meio → VERMELHO na seq certa
    dump: dict[str, Any] = json.loads(dump_path.read_text(encoding="utf-8"))
    candidatos = [e for e in dump["elos"] if e["table_name"] != "genesis"]
    alvo = candidatos[len(candidatos) // 2]
    chave = f"{alvo['table_name']}|{alvo['row_id']}"
    linha = dump["linhas"][chave]["linha"]
    campo = next(k for k, v in linha.items() if isinstance(v, str) and v)
    original = linha[campo]
    linha[campo] = chr(ord(original[0]) ^ 1) + original[1:]  # exatamente 1 bit
    console.print(f"[2/2] virando 1 bit: seq {alvo['seq']} ({chave}), campo "
                  f"'{campo}': {original[:20]!r} -> {linha[campo][:20]!r}")

    adulterado = dump_path.with_name("dump_ADULTERADO_1bit.json")
    adulterado.write_text(json.dumps(dump), encoding="utf-8")
    codigo, saida = _rodar(adulterado)
    adulterado.unlink()
    assert codigo != 0, "o verificador NÃO pegou a adulteração!"
    assert f"seq {alvo['seq']}" in saida and "ADULTERADA" in saida, \
        f"pegou, mas na linha errada:\n{saida}"
    console.print(f"    verificador: {saida.strip().splitlines()[-1]}")
    console.print("[bold green]GATE 4 VERDE: terceiro valida o período e detecta "
                  "1 bit alterado na linha exata[/bold green]")


if __name__ == "__main__":
    main()
