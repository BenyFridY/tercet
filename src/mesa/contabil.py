"""Fase 13 / item 2: export contábil universal — partidas dobradas do livro.

O diário importável tem UM lançamento por competência (micro-pagamentos de $0,001
viram $0,00 nas 2 casas dos sistemas contábeis — agregação é honestidade, não
preguiça) e o detalhe compra-a-compra (6 casas + tx hash) sai num CSV irmão: a
ponte de auditoria que liga o lançamento à evidência on-chain.

Recorte do v0 (doc: fase13-export.md): regime de caixa (só LIQUIDADO), só mainnet,
sem ganho/perda de disposição (USDC ao valor de face), competência pela data de
São Paulo — a MESMA régua da Fase 11. Dinheiro é Decimal, ROUND_HALF_UP na última
milha, nunca float.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import psycopg

from mesa import ptax, telas
from mesa.config import CAIP2_BASE_MAINNET

CONTA_DESPESA = "Despesas:Compras de agentes (x402)"
CONTA_ATIVO = "Ativos digitais:USDC"
MICRO = Decimal(1_000_000)
MINIMO_IMPORTAVEL = Decimal("0.005")  # abaixo disso, 2 casas arredondam para 0,00


@dataclass(frozen=True)
class CompraContabil:
    """Uma compra liquidada, como o detalhe de auditoria enxerga."""

    data_sp: date
    dominio: str
    agente: str
    usd_exato: Decimal  # 6 casas — o valor de verdade
    tx: str


@dataclass(frozen=True)
class Lancamento:
    """Um lançamento de diário (as duas pernas, débito == crédito)."""

    numero: str
    data: date  # último dia com movimento na competência
    narrativa: str
    conta_debito: str
    conta_credito: str
    valor_2c: Decimal  # o que os sistemas importam (2 casas, ROUND_HALF_UP)
    valor_exato: Decimal  # 6 casas — vai na narrativa e no detalhe
    n_compras: int


def carregar_compras(conn: psycopg.Connection[Any], mapa: dict[str, str],
                     ano: int, mes: int | None = None) -> list[CompraContabil]:
    """Compras x402 LIQUIDADAS na mainnet, na competência (data de SP).

    `mes=None` = o ano inteiro (o agregado anual do CARF usa assim)."""
    out: list[CompraContabil] = []
    for ln in telas.carregar_linhas(conn, mapa):
        if ln.rail != "x402" or ln.network != CAIP2_BASE_MAINNET:
            continue
        if ln.settled_minor <= 0:
            continue
        d = ptax.data_sp(ln.ts_utc)
        if d.year != ano or (mes is not None and d.month != mes):
            continue
        out.append(CompraContabil(
            data_sp=d,
            dominio=ln.dominio or f"hash:{ln.recurso_hash[:12]}",
            agente=ln.agente or "-",
            usd_exato=Decimal(ln.settled_minor) / MICRO,
            tx=ln.tx or "-",
        ))
    out.sort(key=lambda c: (c.data_sp, c.dominio, c.tx))
    return out


def montar_lancamento(compras: list[CompraContabil], ano: int, mes: int,
                      conta_despesa: str = CONTA_DESPESA,
                      conta_credito: str = CONTA_ATIVO) -> Lancamento:
    """O lançamento da competência. Levanta ValueError com o motivo NOMEADO."""
    if not compras:
        raise ValueError("sem-compras-liquidadas-na-competencia")
    exato = sum((c.usd_exato for c in compras), Decimal(0))
    valor = exato.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if valor <= 0:
        raise ValueError(
            "abaixo-da-materialidade-de-importacao: total exato "
            f"USD {exato} arredonda para 0,00 em 2 casas — use o detalhe")
    return Lancamento(
        numero=f"x402-{ano:04d}{mes:02d}",
        data=max(c.data_sp for c in compras),
        narrativa=(f"Compras de agentes via x402 — {len(compras)} compras na "
                   f"competência {ano:04d}-{mes:02d}; total exato USD {exato} "
                   "(detalhe compra-a-compra com tx hash no detalhe-compras.csv)"),
        conta_debito=conta_despesa,
        conta_credito=conta_credito,
        valor_2c=valor,
        valor_exato=exato,
        n_compras=len(compras),
    )


# ------------------------------------------------------------------ renderizadores

def _csv(linhas: list[list[str]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerows(linhas)
    return buf.getvalue()


def render_universal(lanc: Lancamento) -> str:
    """O canônico nosso: uma linha por perna, débito e crédito explícitos."""
    return _csv([
        ["numero", "data", "conta", "debito", "credito",
         "valor_exato_6c", "narrativa"],
        [lanc.numero, lanc.data.isoformat(), lanc.conta_debito,
         str(lanc.valor_2c), "", str(lanc.valor_exato), lanc.narrativa],
        [lanc.numero, lanc.data.isoformat(), lanc.conta_credito,
         "", str(lanc.valor_2c), str(lanc.valor_exato), lanc.narrativa],
    ])


def render_qbo(lanc: Lancamento) -> str:
    """QuickBooks Online (artigo oficial Intuit): Journal No./Date/Account Name/
    Description/Debits/Credits; sub-conta = 'Pai:Filha'; débitos == créditos."""
    return _csv([
        ["Journal No.", "Journal Date", "Account Name", "Description",
         "Debits", "Credits"],
        [lanc.numero, lanc.data.strftime("%m/%d/%Y"), lanc.conta_debito,
         lanc.narrativa, str(lanc.valor_2c), ""],
        [lanc.numero, lanc.data.strftime("%m/%d/%Y"), lanc.conta_credito,
         lanc.narrativa, "", str(lanc.valor_2c)],
    ])


def render_xero(lanc: Lancamento, tax_rate: str = "Tax Exempt") -> str:
    """Xero (Conversion Toolbox; leiaute de fontes secundárias convergentes —
    CONFERIR com o template baixado do produto): Amount com sinal (+D/−C)."""
    return _csv([
        ["Narration", "Date", "Description", "AccountCode", "TaxRate", "Amount"],
        [lanc.narrativa, lanc.data.strftime("%d/%m/%Y"), lanc.conta_debito,
         lanc.conta_debito, tax_rate, str(lanc.valor_2c)],
        [lanc.narrativa, lanc.data.strftime("%d/%m/%Y"), lanc.conta_credito,
         lanc.conta_credito, tax_rate, str(-lanc.valor_2c)],
    ])


def render_detalhe(compras: list[CompraContabil]) -> str:
    """A ponte de auditoria: uma linha por compra, 6 casas, tx hash."""
    linhas = [["data_sp", "dominio", "agente", "usd_exato_6c", "tx"]]
    linhas += [[c.data_sp.isoformat(), c.dominio, c.agente,
                f"{c.usd_exato:.6f}", c.tx] for c in compras]
    return _csv(linhas)


# ------------------------------------------------------------------ o validador

def validar(lanc: Lancamento, compras: list[CompraContabil],
            ano: int, mes: int) -> list[str]:
    """Puro. Devolve os problemas NOMEADOS (lista vazia = válido)."""
    problemas: list[str] = []
    if lanc.valor_2c <= 0:
        problemas.append("valor-nao-positivo")
    if lanc.valor_2c != lanc.valor_2c.quantize(Decimal("0.01")):
        problemas.append("valor-com-mais-de-2-casas")
    if not lanc.conta_debito or not lanc.conta_credito:
        problemas.append("conta-vazia")
    if lanc.conta_debito == lanc.conta_credito:
        problemas.append("debito-e-credito-na-mesma-conta")
    if (lanc.data.year, lanc.data.month) != (ano, mes):
        problemas.append("data-fora-da-competencia")
    soma_detalhe = sum((c.usd_exato for c in compras), Decimal(0))
    if soma_detalhe != lanc.valor_exato:
        problemas.append("detalhe-nao-soma-no-exato")
    esperado = lanc.valor_exato.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if lanc.valor_2c != esperado:
        problemas.append("arredondamento-nao-confere-com-o-exato")
    if lanc.n_compras != len(compras):
        problemas.append("contagem-de-compras-nao-confere")
    for c in compras:
        if (c.data_sp.year, c.data_sp.month) != (ano, mes):
            problemas.append(f"compra-fora-da-competencia:{c.tx[:18]}")
        if c.usd_exato <= 0:
            problemas.append(f"compra-com-valor-nao-positivo:{c.tx[:18]}")
    return problemas
