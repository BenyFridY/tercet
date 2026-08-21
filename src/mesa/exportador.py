"""Fase 6: o custo da COMPRA no painel de observabilidade — atributos `purchase.*`.

Um span de compra ganha, na hora da compra, os atributos que nenhum painel tem hoje:
quanto custou, em quê, por qual trilho, e a REFERÊNCIA da liquidação (tx hash).
Qualquer backend OTel (Jaeger, Datadog, LangSmith via OTLP) mostra sem configuração.

Alinhamento com o vocabulário em padronização no OTel (#443, D-28):

| nosso (`purchase.*`)        | #443 (`gen_ai.usage.cost.*`) — quando/se fechar |
|-----------------------------|--------------------------------------------------|
| purchase.amount             | gen_ai.usage.cost.amount                         |
| purchase.currency           | gen_ai.usage.cost.currency                       |
| purchase.rail               | (sem equivalente — proposta nossa no comentário) |
| purchase.settlement_ref     | (sem equivalente — é o nosso diferencial)        |

Por backend (D-30): OTLP genérico cobre Jaeger e Datadog; LangSmith aceita custo em
run de tool (`total_cost`); Langfuse exige modo próprio — mapeados, não implementados.

Nota honesta: `settlement_ref` aqui é o tx hash ALEGADO pelo vendedor na resposta
(chega na hora); a confirmação on-chain vive no LIVRO (coletor). O painel mostra a
alegação; o livro é a verdade.
"""

import json
import re
from typing import Any

from opentelemetry import trace

_TX_RE = re.compile(r"0x[0-9a-fA-F]{64}")


def ref_da_alegacao(settle_claim: dict[str, Any] | None) -> str | None:
    """Acha o tx hash na resposta de settlement do vendedor (a ALEGAÇÃO dele).

    Campos nomeados primeiro (regex genérico pegava o NONCE, que também tem 64 hex).
    """
    if not settle_claim:
        return None

    def _busca_campo(obj: Any) -> str | None:
        if isinstance(obj, dict):
            for chave in ("transaction", "transactionHash", "txHash", "tx_hash"):
                valor = obj.get(chave)
                if isinstance(valor, str) and _TX_RE.fullmatch(valor):
                    return valor
            for v in obj.values():
                achado = _busca_campo(v)
                if achado:
                    return achado
        elif isinstance(obj, list):
            for v in obj:
                achado = _busca_campo(v)
                if achado:
                    return achado
        return None

    nomeado = _busca_campo(settle_claim)
    if nomeado:
        return nomeado
    m = _TX_RE.search(json.dumps(settle_claim))
    return m.group(0) if m else None


def anotar_span_compra(
    *,
    amount_minor: int,
    decimals: int,
    currency: str,
    rail: str,
    network: str | None,
    settlement_ref: str | None,
    resource_hash_hex: str,
    span: Any = None,
) -> None:
    """Pendura os atributos `purchase.*` no span ATUAL (ou no passado em `span`).

    `amount` vai como string decimal (nunca float — invariante do livro).
    `resource_hash_hex` e não a URL (D-11 vale até no painel).
    """
    alvo = span if span is not None else trace.get_current_span()
    inteiro, resto = divmod(amount_minor, 10**decimals)
    alvo.set_attribute("purchase.amount", f"{inteiro}.{resto:0{decimals}d}")
    alvo.set_attribute("purchase.amount_minor", amount_minor)
    alvo.set_attribute("purchase.currency", currency)
    alvo.set_attribute("purchase.rail", rail)
    if network:
        alvo.set_attribute("purchase.network", network)
    if settlement_ref:
        alvo.set_attribute("purchase.settlement_ref", settlement_ref)
    alvo.set_attribute("purchase.resource_hash", resource_hash_hex)
