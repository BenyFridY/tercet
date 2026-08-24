"""As operações do app (D-36): a interface ACIONA motores auditados, nunca escreve.

Um job por vez, sempre de uma lista FECHADA de operações (nada de comando vindo da
tela), rodando como subprocesso do MESMO Python do venv, com o log capturado para a
tela. Compra disparada daqui é SEMPRE testnet; mainnet exige "vai" fora do app.
"""

import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RAIZ = Path(__file__).resolve().parents[3]
LOG_MAX_LINHAS = 800


@dataclass
class Operacao:
    nome: str
    titulo: str
    descricao: str
    dinheiro: str  # o rótulo honesto do custo, SEMPRE visível na tela
    argv: list[str]


def _py(*args: str) -> list[str]:
    return [sys.executable, *args]


# a lista FECHADA — só isto pode rodar pela tela
OPERACOES: dict[str, Operacao] = {
    "demo": Operacao(
        "demo", "Demo ponta a ponta (testnet)",
        "sobe o vendedor de brinquedo, faz 3 compras x402 reais na Base Sepolia, "
        "roda o coletor e casa tudo por (authorizer, nonce) — a compra nova aparece "
        "no blotter ao terminar",
        "TESTNET — ~0,03 USDC de mentira; gas é do facilitator; dinheiro real: zero",
        _py(str(_RAIZ / "scripts" / "fase12" / "demo_ponta_a_ponta.py")),
    ),
    "coletor-testnet": Operacao(
        "coletor-testnet", "Coletor · testnet",
        "varre a Base Sepolia (Transfer + AuthorizationUsed) e observa no livro; "
        "idempotente — rodar duas vezes produz as mesmas linhas",
        "zero — só leitura da chain",
        _py("-m", "mesa.collector"),
    ),
    "coletor-mainnet": Operacao(
        "coletor-mainnet", "Coletor · mainnet (censo)",
        "varre a Base mainnet pelas autorizações da carteira do censo",
        "zero — só leitura da chain",
        _py("-m", "mesa.collector", "--pagador"),
    ),
    "passaportes": Operacao(
        "passaportes", "Re-emitir passaportes (D-08)",
        "re-emite os passaportes das 3 carteiras a partir do livro, com atribuição "
        "on-chain das liquidações sem par — a aba 03 risco re-verifica na hora",
        "zero — leitura + assinatura local",
        _py(str(_RAIZ / "scripts" / "fase12" / "emitir_passaportes.py")),
    ),
    "decripto": Operacao(
        "decripto", "Gerar DeCripto da competência",
        "recibo → PTAX da data de SP → arquivo 0450 + alternativa 0980, validados "
        "contra o leiaute oficial (simulação rotulada; nada é transmitido)",
        "zero — PTAX é público",
        _py(str(_RAIZ / "scripts" / "fase11" / "decripto_build.py"),
            datetime.now(UTC).strftime("%Y-%m")),
    ),
    "contabil": Operacao(
        "contabil", "Gerar export contábil da competência (F13)",
        "o diário de partidas dobradas: universal + QuickBooks + Xero, com o "
        "detalhe compra-a-compra (6 casas + tx hash) que soma no exato; "
        "débito==crédito e conferência SQL independente provados no build",
        "zero — só leitura do livro; escreve arquivos em contabil/",
        _py(str(_RAIZ / "scripts" / "fase13" / "contabil_build.py")),
    ),
    "carf": Operacao(
        "carf", "Gerar visão CARF do ano (F13)",
        "o que um RCASP reportaria destas transações (guia oficial OECD jul/2025); "
        "nasce OECD11 (test data) + Warning de demonstração; validador do guia "
        "morde adulteração — nada é transmitido a ninguém",
        "zero — só leitura do livro; escreve arquivos em fiscal/carf/",
        _py(str(_RAIZ / "scripts" / "fase13" / "carf_build.py")),
    ),
}


@dataclass
class Job:
    operacao: str
    titulo: str
    iniciado_utc: str
    terminado_utc: str | None = None
    rc: int | None = None
    log: list[str] = field(default_factory=list)

    @property
    def rodando(self) -> bool:
        return self.rc is None

    def resumo(self) -> dict[str, Any]:
        return {"operacao": self.operacao, "titulo": self.titulo,
                "iniciado_utc": self.iniciado_utc, "terminado_utc": self.terminado_utc,
                "rc": self.rc, "rodando": self.rodando, "log": self.log}


_lock = threading.Lock()
_atual: Job | None = None


def _rodar(job: Job, argv: list[str]) -> None:
    global _atual
    try:
        proc = subprocess.Popen(
            argv, cwd=str(_RAIZ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            # Windows: sem isto o print() do filho nasce cp1252 e um "ê" derruba
            # o motor (achado do GATE 14)
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        assert proc.stdout is not None
        for linha in proc.stdout:
            job.log.append(linha.rstrip("\n"))
            if len(job.log) > LOG_MAX_LINHAS:  # tela não é arquivo de log
                del job.log[: len(job.log) - LOG_MAX_LINHAS]
        job.rc = proc.wait()
    except Exception as e:  # o erro vai para a tela, não para o void
        job.log.append(f"ERRO ao rodar o job: {e}")
        job.rc = -1
    finally:
        job.terminado_utc = datetime.now(UTC).isoformat(timespec="seconds")


def iniciar(nome: str) -> tuple[bool, str]:
    """(iniciou?, motivo). Um job por vez; nome fora da lista fechada é recusado."""
    global _atual
    op = OPERACOES.get(nome)
    if op is None:
        return False, f"operação desconhecida: {nome!r}"
    with _lock:
        if _atual is not None and _atual.rodando:
            return False, f"já existe um job rodando: {_atual.titulo}"
        job = Job(operacao=op.nome, titulo=op.titulo,
                  iniciado_utc=datetime.now(UTC).isoformat(timespec="seconds"))
        _atual = job
    threading.Thread(target=_rodar, args=(job, op.argv), daemon=True).start()
    return True, "iniciado"


def status() -> dict[str, Any] | None:
    return _atual.resumo() if _atual is not None else None
