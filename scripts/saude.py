"""Saúde da mesa — UM comando confere tudo e imprime VERDE ou VERMELHO.

docs/seguranca.md furo 10 (consolidação): antes eram 5 comandos de cabeça; agora:

  uv run python scripts/saude.py            # tudo
  uv run python scripts/saude.py --rapido   # pula pytest (o mais lento)

O que confere, na ordem:
1. ruff (estilo) · 2. mypy (tipos, strict) · 3. pytest (a suíte inteira)
4. verificador independente no último export de período (a corrente fecha?)
5. portas do Docker: mesa-pg e mesa-jaeger SÓ em 127.0.0.1 (furo 1 nunca volta)
6. varredura de segredo nos arquivos rastreados pelo git (chave/API key = VERMELHO)
"""

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# padrões de segredo: chave EVM atribuída, chave da Anthropic, PEM privado
PADROES_SEGREDO = re.compile(
    r"(PK\s*=\s*['\"]?0x[0-9a-fA-F]{64}|sk-ant-[A-Za-z0-9\-_]{20,}|BEGIN [A-Z ]*PRIVATE KEY)")


def _passo(nome: str, cmd: list[str]) -> bool:
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, check=False)
    ok = r.returncode == 0
    print(f"  [{'ok' if ok else 'FALHOU'}] {nome}")
    if not ok:
        saida = (r.stdout + r.stderr).strip()
        print("    " + "\n    ".join(saida.splitlines()[-12:]))
    return ok


def portas_docker_ok() -> bool:
    r = subprocess.run(["docker", "ps", "--format", "{{.Names}} {{.Ports}}"],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        print("  [FALHOU] docker ps não respondeu (Docker de pé?)")
        return False
    ok = True
    for linha in r.stdout.splitlines():
        if not linha.startswith(("mesa-pg", "mesa-jaeger")):
            continue
        if "0.0.0.0" in linha or "[::]" in linha:
            print(f"  [FALHOU] porta exposta ao Wi-Fi: {linha}")
            ok = False
    if ok:
        print("  [ok] portas do mesa-pg/mesa-jaeger só em 127.0.0.1")
    return ok


def sem_segredo_no_repo() -> bool:
    r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                       text=True, check=False)
    ok = True
    for rel in r.stdout.splitlines():
        p = RAIZ / rel
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = PADROES_SEGREDO.search(texto)
        # o próprio saude.py e o gerador de carteiras contêm os PADRÕES, nunca valores
        if m and rel not in ("scripts/saude.py", "scripts/setup_wallets.py"):
            print(f"  [FALHOU] padrão de segredo em {rel}: {m.group(0)[:24]}…")
            ok = False
    if ok:
        print("  [ok] nenhum segredo em arquivo rastreado")
    return ok


def main() -> None:
    rapido = "--rapido" in sys.argv
    print("saúde da mesa — docs/seguranca.md\n")
    passos = [
        _passo("ruff", ["uv", "run", "ruff", "check", "."]),
        _passo("mypy", ["uv", "run", "mypy", "src", "scripts", "tests"]),
    ]
    if not rapido:
        passos.append(_passo("pytest", ["uv", "run", "pytest", "-q"]))
    exports = sorted((RAIZ / "scripts" / "fase4").glob("dump_periodo_*.json"))
    if exports:
        passos.append(_passo(f"verificador ({exports[-1].name})",
                             ["uv", "run", "python", "verificador/verificar.py",
                              str(exports[-1])]))
    else:
        print("  [aviso] nenhum export de período — rode scripts/fase4/exportar_periodo.py")
    passos.append(portas_docker_ok())
    passos.append(sem_segredo_no_repo())

    if all(passos):
        print("\nVERDE: tudo em ordem.")
    else:
        sys.exit("\nVERMELHO: itens FALHOU acima — arrumar antes de seguir.")


if __name__ == "__main__":
    main()
