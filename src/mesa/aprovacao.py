"""Fase 8: aprovação vinculada (D-14) — o humano aprova UMA cotação, não um cheque em branco.

O problema que isso resolve: "aprovar" genérico vira autorização eterna — o agente
pergunta uma vez e compra qualquer coisa depois. Aqui a aprovação carrega o HASH da
cotação exata (payTo + valor + ativo + rede + recurso): mudou um byte, a aprovação
não vale. É o padrão `input_required`/elicitation do MCP (D-30) aplicado à compra —
pedir aprovação não bloqueia o resto (D-05): a compra sem aprovação é recusada
(fail-closed) e a rodada segue.

A aprovação concedida entra NO LIVRO em `authz.principal_ref`/`principal_evidence`
(colunas que existiam desde a migration 0001 esperando por isso).
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class AprovacaoVinculada:
    """Evidência da decisão humana — vinculada por hash à cotação exata."""

    escopo_hex: str      # sha256 do escopo canônico da cotação (abaixo)
    aprovador: str       # quem decidiu (ex.: "beny")
    decisao: bool        # True = aprovou; False também é evidência (fica no log)
    ts_utc: str          # quando, ISO-8601

    def evidencia(self) -> dict[str, str | bool]:
        d = asdict(self)
        d["tipo"] = "aprovacao-vinculada-d14"
        return d


def escopo_da_cotacao(*, pay_to: str, amount_minor: int, asset: str,
                      network: str, recurso_hash_hex: str | None = None) -> str:
    """O hash que amarra a aprovação a UMA cotação. Determinístico e canônico."""
    canonico = json.dumps({
        "pay_to": pay_to.lower(), "amount_minor": int(amount_minor),
        "asset": asset.lower(), "network": network,
        "recurso": recurso_hash_hex or "",
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode()).hexdigest()


def aprovar(escopo_hex: str, aprovador: str, decisao: bool) -> AprovacaoVinculada:
    return AprovacaoVinculada(escopo_hex=escopo_hex, aprovador=aprovador,
                              decisao=decisao,
                              ts_utc=datetime.now(UTC).isoformat())


def vale_para(aprovacao: AprovacaoVinculada, escopo_hex: str) -> bool:
    """A pergunta que importa: ESTA aprovação vale para ESTA cotação?"""
    return aprovacao.decisao and aprovacao.escopo_hex == escopo_hex
