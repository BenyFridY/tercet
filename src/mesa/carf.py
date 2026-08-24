"""Fase 13 / item 3: CARF — a visão OECD das nossas transações (DEMO/teste).

Enquadramento honesto: o CARF é reportado por RCASPs (provedores) às administrações
tributárias; nós NÃO somos RCASP e não reportamos nada. Este módulo gera a visão de
conformidade — "o que um RCASP reportaria de você" — com dados de transação REAIS
do livro e identidades SINTÉTICAS rotuladas. O documento nasce OECD11 (New TEST
Data — o guia reserva OECD10–13 para teste; é o tpAmb=2 do CARF) e com Warning de
DEMONSTRAÇÃO em texto corrido.

Fonte primária: OECD, "CARF XML Schema (July 2025) — User Guide for Tax
Administrations" (48 págs; Annex B nomeia CARFXML_v1.5.xsd). O XSD oficial não é
público (distribuído às administrações; procurado em 23/08/2026) — a validação
aqui é o validador próprio codado do guia, o MESMO padrão da Fase 11 (o validador
do leiaute pipe também é nosso). Quando o XSD aparecer: lxml.XMLSchema, como a
NFS-e. As URIs de namespace seguem a convenção OECD e estão marcadas A CONFIRMAR.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import psycopg
from lxml import etree

from mesa import contabil

# prefixos do Annex B do guia; URIs por convenção OECD (CRS usa urn:oecd:ties:*) —
# CONFIRMAR contra o XSD oficial quando ele for público
NS_CARF = "urn:oecd:ties:carf:v1"
NS_STF = "urn:oecd:ties:carfstf:v1"
NS_ISO = "urn:oecd:ties:carfiso:v1"
NSMAP = {"carf": NS_CARF, "stf": NS_STF, "iso": NS_ISO}
VERSAO_SCHEMA = "1.5"  # CARFXML_v1.5.xsd (Annex B, guia jul/2025)

# tabelas do guia (jul/2025), à letra
TRANSFER_OUT_TYPES = frozenset(
    {"CARF601", "CARF602", "CARF603", "CARF604", "CARF605", "CARF606"})
COMPRA_BENS_SERVICOS = "CARF603"  # "Purchase of goods or services" (jul/2025)
ALT_VALUATION = frozenset({"CARF1001", "CARF1002", "CARF1003", "CARF1004"})
ESTIMATIVA_RAZOAVEL = "CARF1004"  # USDC→USD 1:1 é estimativa DECLARADA (D-12)
MESSAGE_TYPE_INDIC = frozenset({"CARF701", "CARF702", "CARF703"})
DOC_TYPE_INDIC = frozenset(
    {"OECD0", "OECD1", "OECD2", "OECD3", "OECD10", "OECD11", "OECD12", "OECD13"})
TESTE_NOVO = "OECD11"  # New Test Data — o documento demo NASCE marcado assim

AVISO = ("DEMONSTRACAO / TEST DATA (OECD11). Transacoes REAIS do livro da mesa; "
         "identidades SINTETICAS. A mesa NAO e RCASP e este documento NAO e um "
         "reporte: e a visao de conformidade do que um RCASP reportaria.")


@dataclass(frozen=True)
class AgregadoAno:
    """O agregado anual que o CARF pede: transferências de saída por cripto-ativo."""

    ano: int
    cripto_ativo: str  # nome (DTI quando houver; texto livre é permitido pelo guia)
    n_transacoes: int
    usd_exato: Decimal  # 6 casas (vira NumberofUnits; USDC 1:1)
    moeda: str = "USD"

    @property
    def amount_2c(self) -> Decimal:
        return self.usd_exato.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def agregar_ano(conn: psycopg.Connection[Any], mapa: dict[str, str],
                ano: int) -> AgregadoAno:
    """Todas as compras x402 liquidadas na mainnet no ano (data de SP)."""
    compras = contabil.carregar_compras(conn, mapa, ano, mes=None)
    return AgregadoAno(
        ano=ano,
        cripto_ativo="USDC",
        n_transacoes=len(compras),
        usd_exato=sum((c.usd_exato for c in compras), Decimal(0)),
    )


def _ref(ag: AgregadoAno) -> str:
    """Identificador determinístico (testável): país+ano+país + hash do agregado."""
    h = hashlib.sha256(
        f"{ag.ano}|{ag.cripto_ativo}|{ag.n_transacoes}|{ag.usd_exato}".encode()
    ).hexdigest()[:16]
    return f"BR{ag.ano}BR-mesa-demo-{h}"


def montar_xml(ag: AgregadoAno, agora: datetime | None = None) -> bytes:
    """A mensagem CARF (guia jul/2025): MessageSpec + CarfBody, tudo rotulado."""
    agora = agora or datetime.now(UTC)
    q = f"{{{NS_CARF}}}"

    raiz = etree.Element(q + "CARF_OECD", nsmap=NSMAP, version=VERSAO_SCHEMA)

    spec = etree.SubElement(raiz, q + "MessageSpec")
    etree.SubElement(spec, q + "SendingEntityIN").text = "mesa-demo"
    etree.SubElement(spec, q + "TransmittingCountry").text = "BR"
    etree.SubElement(spec, q + "ReceivingCountry").text = "BR"
    etree.SubElement(spec, q + "MessageType").text = "CARF"
    etree.SubElement(spec, q + "Warning").text = AVISO
    # regra do guia: MessageRefID começa com país-remetente + ano + país-destino
    etree.SubElement(spec, q + "MessageRefID").text = _ref(ag)
    etree.SubElement(spec, q + "MessageTypeIndic").text = "CARF701"
    etree.SubElement(spec, q + "ReportingPeriod").text = f"{ag.ano:04d}-12-31"
    etree.SubElement(spec, q + "Timestamp").text = (
        agora.replace(tzinfo=None).isoformat(timespec="seconds"))

    corpo = etree.SubElement(raiz, q + "CarfBody")

    rcasp = etree.SubElement(corpo, q + "RCASP")
    doc1 = etree.SubElement(rcasp, q + "DocSpec")
    etree.SubElement(doc1, q + "DocTypeIndic").text = TESTE_NOVO
    etree.SubElement(doc1, q + "DocRefID").text = _ref(ag) + "-rcasp"
    etree.SubElement(rcasp, q + "ResCountryCode").text = "BR"
    etree.SubElement(rcasp, q + "IN").text = "00000000000000"  # SINTÉTICO
    etree.SubElement(rcasp, q + "Name").text = (
        "FACILITADOR SINTETICO (DEMONSTRACAO - NAO E UM REPORTE REAL)")

    usuario = etree.SubElement(corpo, q + "ReportableUser")
    doc2 = etree.SubElement(usuario, q + "DocSpec")
    etree.SubElement(doc2, q + "DocTypeIndic").text = TESTE_NOVO
    etree.SubElement(doc2, q + "DocRefID").text = _ref(ag) + "-user"
    uid = etree.SubElement(usuario, q + "UserID")
    ind = etree.SubElement(uid, q + "Individual")
    etree.SubElement(ind, q + "ResCountryCode").text = "BR"
    etree.SubElement(ind, q + "TIN").text = "00000000000"  # SINTÉTICO
    nome = etree.SubElement(ind, q + "Name")
    etree.SubElement(nome, q + "FirstName").text = "USUARIO"
    etree.SubElement(nome, q + "LastName").text = "SINTETICO (DEMONSTRACAO)"

    rel = etree.SubElement(usuario, q + "RelevantTransactions")
    etree.SubElement(rel, q + "CryptoAsset").text = ag.cripto_ativo
    saida = etree.SubElement(rel, q + "CryptoTransferOut")
    etree.SubElement(saida, q + "TransferType").text = COMPRA_BENS_SERVICOS
    etree.SubElement(saida, q + "NumberofTransactions").text = str(ag.n_transacoes)
    amt = etree.SubElement(saida, q + "Amount")
    amt.set("currCode", ag.moeda)
    amt.text = str(ag.amount_2c)
    etree.SubElement(saida, q + "NumberofUnits").text = f"{ag.usd_exato:.6f}"
    etree.SubElement(saida, q + "AltValuation").text = ESTIMATIVA_RAZOAVEL

    corpo_xml: bytes = etree.tostring(raiz, xml_declaration=True,
                                      encoding="UTF-8", pretty_print=True)
    return corpo_xml


# ------------------------------------------------------------------ o validador

_RE_AMOUNT = re.compile(r"^\d+\.\d{2}$")
_RE_UNITS = re.compile(r"^\d+(\.\d{1,6})?$")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_PAIS = re.compile(r"^[A-Z]{2}$")
_RE_MOEDA = re.compile(r"^[A-Z]{3}$")


def _um(raiz: etree._Element, caminho: str) -> str | None:
    achados = raiz.findall(caminho, NSMAP)
    return achados[0].text if len(achados) == 1 else None


def validar(xml_bytes: bytes) -> list[str]:
    """Puro. As regras do GUIA, nomeadas (lista vazia = válido).

    Não substitui o XSD oficial (não público) — valida o que o guia jul/2025
    especifica: enums, formatos de valor (2 casas + currCode), unidades (≤6
    casas), datas e o padrão do MessageRefID.
    """
    problemas: list[str] = []
    try:
        raiz = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        return [f"xml-malformado: {e}"]

    if etree.QName(raiz).localname != "CARF_OECD":
        problemas.append("raiz-nao-e-CARF_OECD")
    if raiz.get("version") != VERSAO_SCHEMA:
        problemas.append("versao-do-schema-diferente-de-1.5")

    if _um(raiz, ".//carf:MessageType") != "CARF":
        problemas.append("MessageType-diferente-de-CARF")
    mti = _um(raiz, ".//carf:MessageTypeIndic")
    if mti not in MESSAGE_TYPE_INDIC:
        problemas.append(f"MessageTypeIndic-fora-da-tabela:{mti}")
    periodo = _um(raiz, ".//carf:ReportingPeriod")
    if not (periodo and _RE_DATA.match(periodo)):
        problemas.append("ReportingPeriod-fora-do-formato-aaaa-mm-dd")

    tx_pais = _um(raiz, ".//carf:TransmittingCountry")
    rx_pais = _um(raiz, ".//carf:ReceivingCountry")
    for rotulo, pais in (("TransmittingCountry", tx_pais),
                         ("ReceivingCountry", rx_pais)):
        if not (pais and _RE_PAIS.match(pais)):
            problemas.append(f"{rotulo}-fora-do-ISO-3166-alpha2")
    ref = _um(raiz, ".//carf:MessageRefID")
    if not ref:
        problemas.append("MessageRefID-ausente")
    elif tx_pais and rx_pais and periodo and not ref.startswith(
            f"{tx_pais}{periodo[:4]}{rx_pais}"):
        problemas.append("MessageRefID-nao-comeca-com-pais+ano+pais")

    for el in raiz.findall(".//carf:DocTypeIndic", NSMAP):
        if el.text not in DOC_TYPE_INDIC:
            problemas.append(f"DocTypeIndic-fora-da-tabela:{el.text}")
    for el in raiz.findall(".//carf:TransferType", NSMAP):
        if el.text not in TRANSFER_OUT_TYPES:
            problemas.append(f"TransferType-fora-da-tabela:{el.text}")
    for el in raiz.findall(".//carf:AltValuation", NSMAP):
        if el.text not in ALT_VALUATION:
            problemas.append(f"AltValuation-fora-da-tabela:{el.text}")

    for el in raiz.findall(".//carf:Amount", NSMAP):
        if not (el.text and _RE_AMOUNT.match(el.text)):
            problemas.append(f"Amount-sem-2-casas-decimais:{el.text}")
        moeda = el.get("currCode")
        if not (moeda and _RE_MOEDA.match(moeda)):
            problemas.append("Amount-sem-currCode-ISO-4217")
    for el in raiz.findall(".//carf:NumberofUnits", NSMAP):
        if not (el.text and _RE_UNITS.match(el.text)):
            problemas.append(f"NumberofUnits-mais-de-6-casas:{el.text}")
    for el in raiz.findall(".//carf:NumberofTransactions", NSMAP):
        if not (el.text and el.text.isdigit() and int(el.text) > 0):
            problemas.append(f"NumberofTransactions-nao-positivo:{el.text}")

    return problemas
