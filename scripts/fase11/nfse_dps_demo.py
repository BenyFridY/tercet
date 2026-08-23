"""Fase 11 — a ponte recibo→NFS-e: uma DPS gerada e validada contra o XSD oficial.

SINTÉTICA E ROTULADA (D-12): a única venda do livro é em TESTNET (sem valor fiscal),
então esta DPS é a demonstração da ponte, não um documento fiscal — `tpAmb = 2`
(homologação) diz isso dentro do próprio XML, e a descrição do serviço repete.

O caminho: bindings oficiais da `nfelib` (DPS v1.00 do Emissor Nacional) → editar os
campos do nosso caso → serializar → **validar contra o XSD oficial embarcado** (lxml)
→ provar que o validador morde (campo inválido → VERMELHO).

Emissão real só existe com CNPJ + Emissor Nacional (Simples: obrigatório 01/11/2026).
Uso: uv run python scripts/fase11/nfse_dps_demo.py
"""

from decimal import Decimal
from pathlib import Path

import nfelib
from lxml import etree
from nfelib.nfse.bindings.v1_0.dps_v1_00 import Dps
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

NFSE = Path(nfelib.__file__).parent / "nfse"
XSD = NFSE / "schemas" / "v1_0" / "DPS_v1.00.xsd"
AMOSTRA = NFSE / "samples" / "v1_0" / "dps-simples.xml"
RAIZ = Path(__file__).resolve().parents[2]

DESCRICAO = ("[SINTETICA - DEMONSTRACAO, NAO E DOCUMENTO FISCAL] Venda de acesso a "
             "endpoint de dados via protocolo x402 (recibo on-chain no livro mesa; "
             "venda real ocorreu em testnet, sem valor fiscal)")


def validar_xsd(xml_texto: str) -> list[str]:
    schema = etree.XMLSchema(etree.parse(str(XSD)))
    doc = etree.fromstring(xml_texto.encode("utf-8"))
    if schema.validate(doc):
        return []
    return [str(e) for e in schema.error_log]


def main() -> None:
    dps = XmlParser().parse(str(AMOSTRA), Dps)
    inf = dps.infDPS
    assert inf is not None and inf.serv is not None and inf.valores is not None

    # o nosso caso, por cima da amostra oficial (CNPJ de exemplo da própria lib)
    inf.dhEmi = "2026-08-21T15:40:10-03:00"    # a venda de teste da Fase 4, hora de SP
    inf.dCompet = "2026-08-21"
    assert inf.serv.cServ is not None
    inf.serv.cServ.xDescServ = DESCRICAO
    assert inf.valores.vServPrest is not None
    inf.valores.vServPrest.vServ = Decimal("0.05")  # 0,01 USDC × PTAX ~5,16 → R$ 0,05

    xml = XmlSerializer(config=SerializerConfig(indent="  ")).render(
        dps, ns_map={None: "http://www.sped.fazenda.gov.br/nfse"})

    falhas = validar_xsd(xml)
    assert falhas == [], f"DPS fora do XSD oficial: {falhas[:3]}"

    # o validador morde: ambiente fora do domínio (só 1=produção, 2=homologação)
    ruim = xml.replace("<tpAmb>2</tpAmb>", "<tpAmb>7</tpAmb>")
    assert validar_xsd(ruim), "XSD não pegou tpAmb inválido — validação não morde"

    saida = RAIZ / "fiscal" / "nfse"
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "dps-demo-sintetica.xml").write_text(xml, encoding="utf-8")
    print(f"DPS sintética validada contra {XSD.name} → {saida / 'dps-demo-sintetica.xml'}")
    print("VERDE: ponte recibo→DPS demonstrada (rotulada sintética; tpAmb=2)")


if __name__ == "__main__":
    main()
