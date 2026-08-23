"""Fase 11 — o leiaute é lei: o validador reprova UM campo fora do manual.

Tudo puro (sem banco, sem rede). O que se prova: o arquivo bom passa; cada classe de
violação do leiaute (contagem de campos, data, tabela, decimais, tamanho, zero,
obrigatório, CRLF) é pega COM o nome do campo; a regra de SP e o arredondamento de
dinheiro são os do doc (fase11.md).
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from mesa import decripto as dc
from mesa import ptax
from mesa.config import USDC_BASE_MAINNET

TS = datetime(2026, 8, 21, 18, 40, 10, tzinfo=UTC)  # 15:40 de SP na sexta 21/08
VENDA = Decimal("5.1625")  # a PTAX real de 21/08/2026, persistida em fx_ptax


def _op(minor: int = 20_000, tx: str = "0x" + "ab" * 32) -> dc.OperacaoSaida:
    return dc.OperacaoSaida(ts_utc=TS, amount_minor=minor, decimals=6,
                            asset_contract=USDC_BASE_MAINNET,
                            plataforma="api.exemplo.io", tx=tx)


def _arquivo() -> str:
    l0450, l0980, _total = dc.montar_competencia(
        [_op(), _op(1_000, "0x" + "cd" * 32)],
        {date(2026, 8, 21): (date(2026, 8, 21), VENDA)})
    return dc.render(l0450 + l0980)


# ----------------------------------------------------------------- caminho feliz

def test_arquivo_bom_e_verde() -> None:
    assert dc.validar(_arquivo()) == []


def test_0450_bate_com_o_exemplo_oficial_do_manual() -> None:
    linha = dc.registro_0450(_op(), VENDA)
    # a forma do exemplo oficial: 0450|data|IV|4|valor|taxas|simbolo|qtd|aval|NI|pais|...
    assert linha[0] == "0450" and linha[2] == "IV" and linha[3] == "4"
    assert linha[1] == "21082026"           # data de SP, ddmmaaaa
    assert linha[4] == "0,10"               # 0,02 USDC × 5,1625 = R$ 0,10325 → 0,10
    assert linha[5] == ""                   # gas é do facilitator — sem taxa inventada
    assert linha[6] == "USDC" and linha[7] == "0,020000"
    assert linha[9] == "8" and linha[10] == "BR"  # TipoNI 8 → país BR (regra literal)
    assert linha[14] == "api.exemplo.io"


def test_regra_de_sp_muda_o_dia() -> None:
    madrugada_utc = datetime(2026, 8, 22, 1, 30, tzinfo=UTC)  # 22h30 de SP do dia 21
    assert ptax.data_sp(madrugada_utc) == date(2026, 8, 21)


def test_arredondamento_half_up() -> None:
    assert dc.valor_reais(1_000, 6, Decimal("5.00")) == Decimal("0.01")   # 0,005 → 0,01
    assert dc.valor_reais(1_000, 6, Decimal("4.00")) == Decimal("0.00")   # 0,004 → 0,00
    with pytest.raises(ValueError, match="R\\$ 0,00"):
        dc.registro_0450(_op(minor=100), VENDA)  # pequena demais p/ 2 casas: erro, não silêncio


def test_simbolo_vem_do_contrato_nunca_de_fora() -> None:
    falso = dc.OperacaoSaida(ts_utc=TS, amount_minor=1000, decimals=6,
                             asset_contract="0x" + "99" * 20,
                             plataforma="x", tx="0xdead")
    with pytest.raises(ValueError, match="allowlist"):
        dc.registro_0450(falso, VENDA)


def test_obrigacao_diz_a_verdade() -> None:
    devida, msg = dc.obrigacao(Decimal("35000.01"))
    assert devida and "OBRIGADA" in msg
    nao_devida, msg = dc.obrigacao(Decimal("0.14"))
    assert not nao_devida and "ABAIXO DO LIMIAR" in msg and "demonstração" in msg


# ------------------------------------------------- cada violação pega pelo nome

def _quebrar(campo_idx: int, valor: str) -> list[str]:
    linha = dc.registro_0450(_op(), VENDA)
    linha[campo_idx] = valor
    return dc.validar(dc.render([linha]))


def test_data_invalida() -> None:
    assert any("OperacaoData" in f and "inválida" in f for f in _quebrar(1, "32132026"))


def test_codigo_fora_da_tabela() -> None:
    assert any("OperacaoCodigo" in f and "fora da tabela" in f for f in _quebrar(2, "X"))
    assert any("TipoTransferenciaSaida" in f for f in _quebrar(3, "9"))


def test_valor_zero_reprovado() -> None:
    assert any("OperacaoValor" in f and "diferente de 0" in f for f in _quebrar(4, "0,00"))


def test_decimais_alem_do_maximo() -> None:
    assert any("OperacaoValor" in f and "casas" in f for f in _quebrar(4, "1,234"))


def test_numerico_com_lixo() -> None:
    assert any("OperacaoValor" in f and "não é numérico" in f for f in _quebrar(4, "1.234,56"))


def test_alfanumerico_estourando_tamanho() -> None:
    assert any("TransfDestinoPlataforma" in f and "máx 80" in f
               for f in _quebrar(14, "x" * 81))


def test_obrigatorio_vazio() -> None:
    assert any("CriptoativoSimbolo" in f and "obrigatório vazio" in f
               for f in _quebrar(6, ""))


def test_contagem_de_campos() -> None:
    linha = dc.registro_0450(_op(), VENDA)[:-1]  # arranca um campo
    assert any("exige 15" in f for f in dc.validar(dc.render([linha])))


def test_registro_desconhecido_e_crlf() -> None:
    assert any("desconhecido" in f for f in dc.validar("0666|x\r\n"))
    assert any("CRLF" in f for f in dc.validar("0980|21082026|0xab|https://basescan.org"))


def test_0980_por_hash() -> None:
    linha = dc.registro_0980(_op())
    assert linha == ["0980", "21082026", "0x" + "ab" * 32, "https://basescan.org"]
    assert dc.validar(dc.render([linha])) == []


def test_total_da_competencia_soma_as_linhas() -> None:
    l0450, l0980, total = dc.montar_competencia(
        [_op(), _op(1_000)], {date(2026, 8, 21): (date(2026, 8, 21), VENDA)})
    assert len(l0450) == len(l0980) == 2
    soma = sum(Decimal(li[4].replace(",", ".")) for li in l0450)
    assert total == soma
