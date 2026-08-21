"""D-02: atribuição é árvore, não agent_id — a soma em qualquer altura, como função pura.

Gasto por agente / passo / tarefa é a MESMA árvore somada em alturas diferentes; se as
somas não batem, ou a árvore está quebrada (span órfão, raiz duplicada) ou uma compra
pendurou em span que não existe — e compra que desaparece é exatamente o que o produto
promete que não acontece (GATE 2).
"""

from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True)
class No:
    """Um span carregado do livro (o suficiente para a soma)."""

    span_id: str
    parent_span_id: str | None
    name: str


@dataclass(frozen=True)
class Problema:
    tipo: str  # compra-sem-span | span-orfao | raiz-multipla | ciclo
    detalhe: str


def verificar(nos: list[No], gasto_proprio: dict[str, int]) -> list[Problema]:
    """Integridade antes da soma. Lista vazia = árvore íntegra."""
    ids = {n.span_id for n in nos}
    problemas: list[Problema] = []
    for span_id in gasto_proprio:
        if span_id not in ids:
            problemas.append(
                Problema("compra-sem-span", f"compra pendurada em span inexistente: {span_id}")
            )
    raizes = [n for n in nos if n.parent_span_id is None]
    for n in nos:
        if n.parent_span_id is not None and n.parent_span_id not in ids:
            problemas.append(
                Problema("span-orfao", f"{n.span_id} ({n.name}) aponta pai ausente")
            )
    if len(raizes) > 1:
        problemas.append(
            Problema("raiz-multipla", f"{len(raizes)} raízes num trace só: "
                     + ", ".join(r.name for r in raizes))
        )
    return problemas


def rollup(nos: list[No], gasto_proprio: dict[str, int]) -> dict[str, int]:
    """span_id -> gasto próprio + gasto de TODOS os descendentes (unidade mínima)."""
    filhos: dict[str, list[No]] = {}
    for n in nos:
        if n.parent_span_id is not None:
            filhos.setdefault(n.parent_span_id, []).append(n)

    memo: dict[str, int] = {}

    def custo(n: No) -> int:
        if n.span_id not in memo:
            memo[n.span_id] = gasto_proprio.get(n.span_id, 0) + sum(
                custo(f) for f in filhos.get(n.span_id, [])
            )
        return memo[n.span_id]

    for n in nos:
        custo(n)
    return memo


def total_das_raizes(nos: list[No], acumulado: dict[str, int]) -> int:
    return sum(acumulado[n.span_id] for n in nos if n.parent_span_id is None)


def carregar_arvore(
    conn: psycopg.Connection[Any], trace_id: str
) -> tuple[list[No], dict[str, int]]:
    """Ponte SQL: spans do trace + gasto próprio por span (soma das cotações das compras)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT span_id, parent_span_id, name FROM span WHERE trace_id = %s",
            (trace_id,),
        )
        nos = [No(span_id=r[0], parent_span_id=r[1], name=r[2]) for r in cur.fetchall()]
        cur.execute(
            "SELECT r.span_id, COALESCE(SUM(q.amount_minor), 0)"
            " FROM request r JOIN quote q ON q.request_id = r.id"
            " WHERE r.trace_id = %s GROUP BY r.span_id",
            (trace_id,),
        )
        gasto = {r[0]: int(r[1]) for r in cur.fetchall()}
    return nos, gasto
