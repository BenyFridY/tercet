"""Fase 4: os dois carimbos de tempo da raiz de Merkle.

- RFC3161 (freeTSA): instantâneo; o token DER carrega o certificado do TSA
  (include_tsa_certificate=True), então a verificação offline é auto-contida.
- OpenTimestamps: pela LIB, não pelo CLI — o otsclient importa bitcoin.rpc, que
  tenta carregar OpenSSL via ctypes e morre no Windows; para CARIMBAR a lib basta.
  Fluxo idêntico ao do otsclient: sha256 + nonce de privacidade + calendários.
  A prova nasce incompleta (ancora no Bitcoin em ~horas) e se completa por upgrade
  — que entra como period_stamp kind='ots-upgrade', linha nova, nunca UPDATE.
"""

import io
import os

import rfc3161ng
from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.serialize import StreamSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile

TSA_URL = "https://freetsa.org/tsr"
CALENDARIOS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://a.pool.eternitywall.com",
    "https://ots.btc.catallaxy.com",
]
OTS_MINIMO = 1  # v0: 1 calendário basta (o RFC3161 é o carimbo que segura o gate)


def rfc3161_stamp(dado: bytes) -> bytes:
    """Carimbo RFC3161 do freeTSA sobre `dado`; devolve o TimeStampToken em DER."""
    timestamper = rfc3161ng.RemoteTimestamper(TSA_URL, hashname="sha256")
    tst = timestamper(data=dado, include_tsa_certificate=True)
    return bytes(tst) if not isinstance(tst, bytes) else tst


def ots_stamp(conteudo: bytes) -> tuple[bytes | None, list[str]]:
    """Carimba `conteudo` nos calendários OTS.

    Devolve (prova .ots ou None se todos falharem, lista de calendários que aceitaram).
    """
    arquivo = DetachedTimestampFile.from_fd(OpSHA256(), io.BytesIO(conteudo))
    com_nonce = arquivo.timestamp.ops.add(OpAppend(os.urandom(16)))
    raiz = com_nonce.ops.add(OpSHA256())

    aceitaram: list[str] = []
    for url in CALENDARIOS:
        try:
            resultado = RemoteCalendar(url).submit(raiz.msg)
            raiz.merge(resultado)
            aceitaram.append(url)
        except Exception:  # noqa: BLE001 — calendário público oscila; tenta o próximo
            continue
    if len(aceitaram) < OTS_MINIMO:
        return None, aceitaram
    saida = io.BytesIO()
    arquivo.serialize(StreamSerializationContext(saida))
    return saida.getvalue(), aceitaram
