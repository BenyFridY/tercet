"""Fase 7: o Laboratório — backtest de política de gasto sobre o livro.

Motor PURO (zero SQL, zero rede): testável em memória, alimentado pelo driver.

A regra anti-autoengano nº 1 é TIPO, não disciplina: a política recebe
`PontoDeDecisao`, que NÃO TEM o desfecho — point-in-time por construção.
O `Desfecho` (entregou? liquidou?) entra depois, só para dar nota.

Proxies e premissas são rotulados no resultado (D-12): valor = entrega
estruturalmente válida; premissa de independência (o vendedor não sabia a nossa
política); vínculo medido pós-rodada, premissa de estabilidade no dia.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ROTULOS = [
    "valor = entrega estruturalmente válida (HTTP 200 + corpo); conteúdo NÃO avaliado"
    " — proxy rotulado (D-12: LLM não tem replay determinístico)",
    "premissa de independência: o desfecho observado de cada fonte vale para o"
    " contrafactual (o vendedor não sabia qual política usávamos)",
    "vínculo payTo⇔domínio medido em 21/08 PÓS-rodada; premissa: estável no dia",
    "walk-forward ENTRE rodadas exige rodada 2 — aqui o eixo temporal é a ordem real"
    " das decisões DENTRO da rodada 1",
    "IC: Wilson (aproximado, método nomeado); com n pequeno o intervalo é largo e a"
    " leitura honesta é 'sem evidência'",
]


@dataclass(frozen=True)
class PontoDeDecisao:
    """O que o comprador enxergava NA HORA de assinar. SEM desfecho, de propósito."""

    ordem: int                 # posição real na rodada (walk-forward)
    dominio_hash: str          # identidade da fonte (D-11: hash, nunca URL)
    amount_minor: int          # o valor que seria assinado (USDC, 6 casas)
    vinculo_nivel: int         # escada N1–N4 (4 = unverified)


@dataclass(frozen=True)
class Desfecho:
    """O que aconteceu de verdade — só entra na NOTA, nunca na decisão."""

    entregue: bool
    liquidado_minor: int       # 0 = não cobrou


@dataclass
class Orcamento:
    """Estado walk-forward que a política PODE consultar (era conhecível na hora)."""

    gasto_minor: int = 0


Politica = Callable[[PontoDeDecisao, Orcamento], bool]


def politicas_da_rodada1() -> dict[str, Politica]:
    """As 5 políticas do doc — regras point-in-time nomeadas."""

    def real(p: PontoDeDecisao, o: Orcamento) -> bool:
        return p.amount_minor <= 1_000_000 and o.gasto_minor + p.amount_minor <= 20_000_000

    def micro(p: PontoDeDecisao, o: Orcamento) -> bool:
        return p.amount_minor <= 10_000

    def verified_only(p: PontoDeDecisao, o: Orcamento) -> bool:
        return p.vinculo_nivel <= 2

    def premium(p: PontoDeDecisao, o: Orcamento) -> bool:
        return p.amount_minor >= 100_000

    def orcamento_5c(p: PontoDeDecisao, o: Orcamento) -> bool:
        return o.gasto_minor + p.amount_minor <= 50_000

    return {"real-rodada1": real, "micro": micro, "verified-only": verified_only,
            "premium": premium, "orcamento-5c": orcamento_5c}


def wilson(sucessos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """IC de Wilson para proporção (aproximado; método nomeado no relatório)."""
    if n == 0:
        return (0.0, 1.0)  # sem dado = sem informação — o intervalo diz isso
    p = sucessos / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    meia = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centro - meia), min(1.0, centro + meia))


@dataclass
class Resultado:
    politica: str
    n_ofertas: int = 0
    n_compras: int = 0
    gasto_autorizado_minor: int = 0
    gasto_liquidado_minor: int = 0
    entregas: int = 0
    compras_que_falharam: int = 0
    taxa_entrega: float | None = None
    ic_wilson_95: tuple[float, float] = (0.0, 1.0)
    custo_por_entrega_minor: int | None = None
    entregas_perdidas: int = 0     # entregas que o baseline real obteve e esta perdeu
    detalhe: list[dict[str, Any]] = field(default_factory=list)


def backtest(pontos: list[PontoDeDecisao], desfechos: dict[int, Desfecho],
             nome: str, politica: Politica) -> Resultado:
    """Percorre as decisões NA ORDEM REAL; a política nunca vê o desfecho."""
    r = Resultado(politica=nome, n_ofertas=len(pontos))
    orcamento = Orcamento()
    total_entregas_disponiveis = sum(
        1 for p in pontos if desfechos[p.ordem].entregue)
    for p in sorted(pontos, key=lambda x: x.ordem):
        compra = politica(p, orcamento)
        d = desfechos[p.ordem]
        if compra:
            orcamento.gasto_minor += p.amount_minor
            r.n_compras += 1
            r.gasto_autorizado_minor += p.amount_minor
            r.gasto_liquidado_minor += d.liquidado_minor
            if d.entregue:
                r.entregas += 1
            else:
                r.compras_que_falharam += 1
        r.detalhe.append({"ordem": p.ordem, "comprou": compra,
                          "amount_minor": p.amount_minor,
                          "entregue": d.entregue if compra else None})
    if r.n_compras:
        r.taxa_entrega = r.entregas / r.n_compras
    r.ic_wilson_95 = wilson(r.entregas, r.n_compras)
    if r.entregas:
        r.custo_por_entrega_minor = round(r.gasto_liquidado_minor / r.entregas)
    r.entregas_perdidas = total_entregas_disponiveis - r.entregas
    return r
