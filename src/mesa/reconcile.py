"""A reconciliação de três pontas — o coração do produto, como FUNÇÃO PURA.

`reconciliar()` não toca banco nem rede: recebe listas, devolve vereditos.
É ela que vira biblioteca depois. `carregar()` é a ponte com o banco.

Vocabulário (PLANO): delivered -> settled -> uncollected, órfãos nas DUAS direções.
"""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import psycopg


class Veredito(StrEnum):
    OK = "ok"                                       # entregue E liquidado na chain
    UNCOLLECTED = "uncollected"                     # entregue sem cobrar (dinheiro na mesa)
    PAGO_SEM_ENTREGA = "pago-sem-entrega"           # liquidou na chain, cliente não recebeu
    AUTORIZADA_SEM_LIQUIDACAO = "autorizada-sem-liquidacao"  # assinou; chain não liquidou
    REPLAY_EXTRA = "replay-extra"                   # (payer, nonce) duplicado no livro
    FALHOU_SEM_PAGAR = "falhou-sem-pagar"           # request falhou antes de qualquer pagamento
    ORFAO_CHAIN = "orfao-chain"                     # liquidação on-chain sem par no livro


EXPLICACAO = {
    Veredito.OK: "entregue e liquidado — casado por (authorizer, nonce)",
    Veredito.UNCOLLECTED: "vendedor entregou sem cobrar — dinheiro deixado na mesa",
    Veredito.PAGO_SEM_ENTREGA: "a chain liquidou mas a entrega falhou — disputa em potencial",
    Veredito.AUTORIZADA_SEM_LIQUIDACAO: "autorização assinada sem liquidação — dinheiro NÃO saiu",
    Veredito.REPLAY_EXTRA: "mesma (authorizer, nonce) duas vezes — replay pego pela chave",
    Veredito.FALHOU_SEM_PAGAR: "falhou antes de pagar — sem efeito financeiro",
    Veredito.ORFAO_CHAIN: "liquidação sem registro no livro — compra fora da instrumentação",
}


@dataclass(frozen=True)
class Compra:
    request_id: str
    delivered: bool
    status_http: int | None
    authz_id: str | None
    payer: str | None
    nonce: str | None
    settled: bool  # tem settlement_leg


@dataclass(frozen=True)
class Liquidacao:
    settlement_id: str
    external_ref: str
    amount_minor: int
    tem_leg: bool


def reconciliar(
    compras: list[Compra], liquidacoes: list[Liquidacao]
) -> dict[Veredito, list[Any]]:
    """Pura. Cada compra e cada liquidação cai em EXATAMENTE um veredito."""
    out: dict[Veredito, list[Any]] = {v: [] for v in Veredito}
    duplicatas = Counter((c.payer, c.nonce) for c in compras if c.nonce is not None)
    for c in compras:
        if c.authz_id is None:
            out[Veredito.UNCOLLECTED if c.delivered else Veredito.FALHOU_SEM_PAGAR].append(c)
        elif c.settled:
            out[Veredito.OK if c.delivered else Veredito.PAGO_SEM_ENTREGA].append(c)
        elif c.nonce is not None and duplicatas[(c.payer, c.nonce)] > 1:
            out[Veredito.REPLAY_EXTRA].append(c)
        else:
            out[Veredito.AUTORIZADA_SEM_LIQUIDACAO].append(c)
    for s in liquidacoes:
        if not s.tem_leg:
            out[Veredito.ORFAO_CHAIN].append(s)
    return out


def carregar(conn: psycopg.Connection[Any]) -> tuple[list[Compra], list[Liquidacao]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT r.id::text, r.delivered, r.status_http, a.id::text,
                   lower((a.rail_evidence -> 'authorization') ->> 'from'),
                   lower((a.rail_evidence -> 'authorization') ->> 'nonce'),
                   (l.authorization_id IS NOT NULL)
            FROM request r
            LEFT JOIN quote q ON q.request_id = r.id
            LEFT JOIN authz a ON a.quote_id = q.id
            LEFT JOIN settlement_leg l ON l.authorization_id = a.id
            ORDER BY r.ts_utc
        """)
        compras = [Compra(*row) for row in cur.fetchall()]
        cur.execute("""
            SELECT s.id::text, s.external_ref, s.total_amount_minor,
                   (l.settlement_id IS NOT NULL)
            FROM settlement s
            LEFT JOIN settlement_leg l ON l.settlement_id = s.id
            ORDER BY s.block_number
        """)
        liquidacoes = [Liquidacao(*row) for row in cur.fetchall()]
    return compras, liquidacoes
