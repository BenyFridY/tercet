"""Fase 11: a DeCripto — o leiaute oficial, codificado da fonte, com validador próprio.

Fonte normativa: Manual de Orientação do Leiaute da DeCripto v1.01 (ADE Copes nº
02/2025, IN RFB nº 2.291/2025), capítulo 6 — **PF/PJ SEM prestador de serviço de
criptoativo** (autocustódia; o comprador x402 é exatamente este caso). Baixado de
gov.br e lido página a página em 23/08/2026 (docs/fase11.md).

O arquivo é texto pipe-delimitado (§2.2): UTF-8, campos separados por `|`, CRLF no fim
de cada linha, datas `ddmmaaaa`, decimais com vírgula, sem separador de milhar.

O que o comprador x402 emite:
- **Registro 0450** (transferência de saída, operação IV, TipoTransferenciaSaida 4 =
  "aquisição de bens ou serviços", CARF604) — uma linha por compra liquidada.
- **Registro 0980** (Componibilidade Contratual Atômica, art. 9º § único): a
  alternativa legal de informar só o hash da transação + URL do explorador — o
  pagamento x402 via contrato inteligente é o caso de uso literal.

Regras que valem mais que o código: TESTNET NUNCA entra (filtro por rede mainnet);
símbolo deriva do ENDEREÇO do contrato via allowlist (D-07 — símbolo é falsificável);
dinheiro é Decimal com ROUND_HALF_UP na última milha, nunca float.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import psycopg

from mesa import ptax
from mesa.config import USDC_BASE_MAINNET

# IN RFB 2.291/2025: obrigação mensal da PF acima deste total movimentado fora de
# prestadora nacional. Abaixo dele a DeCripto não é devida — o motor DIZ isso.
LIMIAR_OBRIGACAO_REAIS = Decimal("35000.00")
BASESCAN = "https://basescan.org"

# Símbolo NUNCA vem de fora: deriva do endereço do contrato (D-07)
SIMBOLO_POR_CONTRATO = {USDC_BASE_MAINNET.lower(): "USDC"}

# ------------------------- tabelas internas (manual §2.5), como vão no arquivo
OPERACAO_CODIGO = frozenset({"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"})
TIPO_NI = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})
TIPO_TRANSF_ENTRADA = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9"})
TIPO_TRANSF_SAIDA = frozenset({"1", "2", "3", "4", "5", "6"})
TIPO_AVALIACAO = frozenset({"1", "2", "3", "4"})

SAIDA_AQUISICAO_BENS_SERVICOS = "4"   # CARF604
AVALIACAO_ESTIMATIVA_RAZOAVEL = "4"   # CARF1004 (USDC→USD 1:1 + PTAX é estimativa DECLARADA)
NI_PLATAFORMA_DESCENTRALIZADA = "8"   # o livro conhece payTo+domínio, não NIF (fase11.md)


# ------------------------------------------- o schema do leiaute (cap. 6, à letra)
@dataclass(frozen=True)
class Campo:
    nome: str
    tipo: str                 # "N" | "C"
    tam_max: int              # N: inclui a vírgula; C sem indicação no manual: 255
    decimais: int | None      # N: MÁXIMO de casas após a vírgula; None = inteiro puro
    obrigatorio: bool         # só o "Sim" incondicional do manual
    valores: frozenset[str] | None = None
    nao_zero: bool = False
    data: bool = False        # ddmmaaaa


def _c(nome: str, tam: int, *, obrig: bool, valores: frozenset[str] | None = None) -> Campo:
    return Campo(nome, "C", tam, None, obrig, valores)


def _n(nome: str, tam: int, dec: int | None, *, obrig: bool,
       valores: frozenset[str] | None = None, nao_zero: bool = False,
       data: bool = False) -> Campo:
    return Campo(nome, "N", tam, dec, obrig, valores, nao_zero, data)


REGISTROS: dict[str, list[Campo]] = {
    # 6.6 — a operação do comprador x402 (pagar serviço com cripto da própria carteira)
    "0450": [
        _c("TipoRegistro", 4, obrig=True, valores=frozenset({"0450"})),
        _n("OperacaoData", 8, None, obrig=True, data=True),
        _c("OperacaoCodigo", 4, obrig=True, valores=OPERACAO_CODIGO),
        _n("TipoTransferenciaSaida", 1, None, obrig=True, valores=TIPO_TRANSF_SAIDA),
        _n("OperacaoValor", 15, 2, obrig=True, nao_zero=True),
        _n("OperacaoTaxasValor", 10, 2, obrig=False),
        _c("CriptoativoSimbolo", 10, obrig=True),
        _n("CriptoativoQuantidade", 26, 10, obrig=True, nao_zero=True),
        _n("AvaliacaoAlternativaValor", 1, None, obrig=False, valores=TIPO_AVALIACAO),
        _c("TransfDestinoTipoNI", 2, obrig=True, valores=TIPO_NI),
        _c("TransfDestinoPais", 2, obrig=True),
        _n("TransfDestinoCPFCNPJ", 14, None, obrig=False),
        _c("TransfDestinoNI", 30, obrig=False),
        _c("TransfDestinoNome", 80, obrig=False),
        _c("TransfDestinoPlataforma", 80, obrig=False),
    ],
    # 6.5 — a entrada (quando formos o vendedor recebendo cripto — ainda sem caso mainnet)
    "0350": [
        _c("TipoRegistro", 4, obrig=True, valores=frozenset({"0350"})),
        _n("OperacaoData", 8, None, obrig=True, data=True),
        _c("OperacaoCodigo", 4, obrig=True, valores=OPERACAO_CODIGO),
        _n("TipoTransferenciaEntrada", 1, None, obrig=True, valores=TIPO_TRANSF_ENTRADA),
        _n("OperacaoValor", 15, 2, obrig=True, nao_zero=True),
        _n("OperacaoTaxasValor", 10, 2, obrig=False),
        _c("CriptoativoSimbolo", 10, obrig=True),
        _n("CriptoativoQuantidade", 26, 10, obrig=True, nao_zero=True),
        _n("AvaliacaoAlternativaValor", 1, None, obrig=False, valores=TIPO_AVALIACAO),
        _c("TransfOrigemTipoNI", 2, obrig=True, valores=TIPO_NI),
        _c("TransfOrigemPais", 2, obrig=True),
        _n("TransfOrigemCPFCNPJ", 14, None, obrig=False),
        _c("TransfOrigemNI", 30, obrig=False),
        _c("TransfOrigemNome", 80, obrig=False),
        _c("TransfOrigemPlataforma", 80, obrig=False),
    ],
    # 6.10 — a alternativa do art. 9º § único: só o hash + explorador
    "0980": [
        _c("TipoRegistro", 4, obrig=True, valores=frozenset({"0980"})),
        _n("OperacaoData", 8, None, obrig=True, data=True),
        _c("HashTransacao", 300, obrig=True),
        _c("BlockchainURL", 300, obrig=True),
    ],
}


# --------------------------------------------------------- formatação (§2.3)
def fmt_valor(v: Decimal) -> str:
    """Reais com exatamente 2 casas, vírgula decimal, sem separador de milhar."""
    return f"{v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}".replace(".", ",")


def fmt_quantidade(amount_minor: int, decimals: int) -> str:
    qtd = Decimal(amount_minor) / (Decimal(10) ** decimals)
    return f"{qtd:.{decimals}f}".replace(".", ",")


def valor_reais(amount_minor: int, decimals: int, venda: Decimal) -> Decimal:
    qtd = Decimal(amount_minor) / (Decimal(10) ** decimals)
    return (qtd * venda).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------- montar (puro)
@dataclass(frozen=True)
class OperacaoSaida:
    """Uma compra liquidada do livro, pronta para virar linha do arquivo."""

    ts_utc: datetime
    amount_minor: int
    decimals: int
    asset_contract: str
    plataforma: str  # domínio do vendedor (ou o payTo, quando domínio desconhecido)
    tx: str


def registro_0450(op: OperacaoSaida, venda: Decimal) -> list[str]:
    simbolo = SIMBOLO_POR_CONTRATO.get(op.asset_contract.lower())
    if simbolo is None:
        raise ValueError(f"contrato fora da allowlist (D-07): {op.asset_contract}")
    valor = valor_reais(op.amount_minor, op.decimals, venda)
    if valor == 0:
        raise ValueError(
            f"compra de {op.amount_minor} minor vira R$ 0,00 no leiaute (2 casas) — "
            "não representável; decidir com contador, não arredondar em silêncio")
    return [
        "0450", ptax.data_sp(op.ts_utc).strftime("%d%m%Y"), "IV",
        SAIDA_AQUISICAO_BENS_SERVICOS, fmt_valor(valor),
        "",  # taxas: o facilitator paga o gas — o pagador não incorre (fase11.md)
        simbolo, fmt_quantidade(op.amount_minor, op.decimals),
        AVALIACAO_ESTIMATIVA_RAZOAVEL, NI_PLATAFORMA_DESCENTRALIZADA,
        "BR",  # regra literal do manual: TipoNI 8 → país BR
        "", "", "", op.plataforma[:80],
    ]


def registro_0980(op: OperacaoSaida) -> list[str]:
    return ["0980", ptax.data_sp(op.ts_utc).strftime("%d%m%Y"), op.tx, BASESCAN]


def montar_competencia(
    ops: list[OperacaoSaida], cotacoes: dict[date, tuple[date, Decimal]]
) -> tuple[list[list[str]], list[list[str]], Decimal]:
    """(linhas 0450, linhas 0980, total em reais). `cotacoes`: data SP -> (data usada, venda)."""
    l0450: list[list[str]] = []
    l0980: list[list[str]] = []
    total = Decimal("0.00")
    for op in sorted(ops, key=lambda o: o.ts_utc):
        _, venda = cotacoes[ptax.data_sp(op.ts_utc)]
        linha = registro_0450(op, venda)
        l0450.append(linha)
        l0980.append(registro_0980(op))
        total += Decimal(linha[4].replace(",", "."))
    return l0450, l0980, total


def obrigacao(total_reais: Decimal) -> tuple[bool, str]:
    if total_reais > LIMIAR_OBRIGACAO_REAIS:
        return True, (f"OBRIGADA: R$ {total_reais} no mês fora de prestadora nacional "
                      f"> limiar de R$ {LIMIAR_OBRIGACAO_REAIS} (IN RFB 2.291/2025)")
    return False, (f"ABAIXO DO LIMIAR: R$ {total_reais} no mês < R$ "
                   f"{LIMIAR_OBRIGACAO_REAIS} — entrega NÃO devida; arquivo gerado "
                   "como demonstração do motor (rotulada, D-12)")


# --------------------------------------------------------- render + validar (§2.2/§2.3)
def render(linhas: list[list[str]]) -> str:
    return "".join("|".join(campos) + "\r\n" for campos in linhas)


_RE_NUM = re.compile(r"^\d+(,\d+)?$")


def _validar_campo(n_linha: int, spec: Campo, valor: str, falhas: list[str]) -> None:
    onde = f"linha {n_linha}, {spec.nome}"
    if valor == "":
        if spec.obrigatorio:
            falhas.append(f"{onde}: obrigatório vazio")
        return
    if spec.tipo == "N":
        if not _RE_NUM.match(valor):
            falhas.append(f"{onde}: não é numérico do leiaute: {valor!r}")
            return
        if len(valor) > spec.tam_max:
            falhas.append(f"{onde}: {len(valor)} chars > máx {spec.tam_max}")
        casas = len(valor.split(",")[1]) if "," in valor else 0
        if spec.decimais is None and casas:
            falhas.append(f"{onde}: não admite casas decimais: {valor!r}")
        elif spec.decimais is not None and casas > spec.decimais:
            falhas.append(f"{onde}: {casas} casas > máx {spec.decimais}")
        if spec.data:
            try:
                datetime.strptime(valor, "%d%m%Y").replace(tzinfo=UTC)
            except ValueError:
                falhas.append(f"{onde}: data inválida (ddmmaaaa): {valor!r}")
        if spec.nao_zero and Decimal(valor.replace(",", ".")) == 0:
            falhas.append(f"{onde}: deve ser diferente de 0")
    else:
        if len(valor) > spec.tam_max:
            falhas.append(f"{onde}: {len(valor)} chars > máx {spec.tam_max}")
        if any(ord(ch) < 32 for ch in valor):
            falhas.append(f"{onde}: caractere de controle proibido")
    if spec.valores is not None and valor not in spec.valores:
        falhas.append(f"{onde}: {valor!r} fora da tabela {sorted(spec.valores)}")


def validar(texto: str) -> list[str]:
    """Puro: o arquivo contra o leiaute. Lista de falhas nomeadas; vazia = VERDE."""
    falhas: list[str] = []
    if not texto.endswith("\r\n"):
        falhas.append("arquivo não termina em CRLF (§2.2)")
    for i, linha in enumerate(texto.split("\r\n")):
        if not linha:
            continue
        n = i + 1
        campos = linha.split("|")
        schema = REGISTROS.get(campos[0])
        if schema is None:
            falhas.append(f"linha {n}: registro desconhecido {campos[0]!r}")
            continue
        if len(campos) != len(schema):
            falhas.append(f"linha {n}: {len(campos)} campos, leiaute do "
                          f"{campos[0]} exige {len(schema)}")
            continue
        for spec, valor in zip(schema, campos, strict=True):
            _validar_campo(n, spec, valor, falhas)
    return falhas


# --------------------------------------------------------- a ponte com o livro
def carregar_saidas_mainnet(
    conn: psycopg.Connection[Any], *, ano: int, mes: int,
    plataforma_por_tx: dict[str, str],
) -> list[OperacaoSaida]:
    """Compras LIQUIDADAS na Base mainnet cuja data de SP cai na competência.

    Testnet não aparece nem por engano: o filtro é a rede, na query.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.block_ts_utc, l.settled_amount_minor, q.decimals,
                   q.asset_contract, s.external_ref
            FROM settlement_leg l
            JOIN settlement s ON s.id = l.settlement_id
            JOIN authz a ON a.id = l.authorization_id
            JOIN quote q ON q.id = a.quote_id
            WHERE s.rail = 'x402' AND s.network_caip2 = 'eip155:8453'
            ORDER BY s.block_ts_utc
            """,
        )
        ops = [
            OperacaoSaida(
                ts_utc=row[0], amount_minor=int(row[1]), decimals=int(row[2]),
                asset_contract=str(row[3]),
                plataforma=plataforma_por_tx.get(str(row[4]).lower(), str(row[4])),
                tx=str(row[4]),
            )
            for row in cur.fetchall()
        ]
    return [op for op in ops
            if (d := ptax.data_sp(op.ts_utc)).year == ano and d.month == mes]


def cotacoes_para(conn: psycopg.Connection[Any], ops: list[OperacaoSaida]
                  ) -> dict[date, tuple[date, Decimal]]:
    datas = sorted({ptax.data_sp(op.ts_utc) for op in ops})
    return {d: ptax.venda_para(conn, d) for d in datas}
