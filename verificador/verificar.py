"""Verificador OFFLINE do livro da mesa — independente de propósito.

Este script NÃO importa o código do mesa: reimplementa as regras públicas de
docs/canonicalizacao.md, para que um terceiro confie no que LÊ aqui, não em nós.
Roda num dump exportado (mesa-dump-periodo-v1), sem banco e sem rede.

O que ele prova:
1. Cada linha do dump re-hasheia para o row_hash declarado (RFC 8785 + sha256).
2. A corrente fecha: link[n] = sha256(link[n-1] || row_hash[n]), sem buracos.
3. A raiz de Merkle das folhas bate com a raiz declarada do período.
4. O carimbo RFC3161 cobre EXATAMENTE essa raiz (messageImprint), e o horário
   assinado pelo TSA é impresso. (Checagem criptográfica completa da assinatura
   do TSA: openssl ts -verify — o comando é impresso no fim.)

O row_hash do genesis (seq 0) é âncora: adulterá-lo obriga a recomputar a corrente
inteira, e então a raiz deixa de bater com os carimbos de tempo — que são externos.

Dependências: rfc8785 (obrigatória), rfc3161ng (opcional, para decodificar o carimbo).
Uso: python verificar.py dump_periodo_YYYY-MM-DD.json
"""

import base64
import hashlib
import json
import sys
from pathlib import Path

import rfc8785

ZERO32 = bytes(32)


def falha(msg: str) -> None:
    print(f"VERMELHO: {msg}")
    sys.exit(1)


def merkle(folhas: list[bytes]) -> bytes:
    nivel = list(folhas)
    while len(nivel) > 1:
        if len(nivel) % 2:
            nivel.append(nivel[-1])
        nivel = [hashlib.sha256(nivel[i] + nivel[i + 1]).digest()
                 for i in range(0, len(nivel), 2)]
    return nivel[0]


def main() -> None:
    dump = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if dump.get("formato") != "mesa-dump-periodo-v1":
        falha("formato de dump desconhecido")
    elos, linhas, period = dump["elos"], dump["linhas"], dump["period"]

    # 1 + 2: re-hash de cada linha e fechamento da corrente
    seq_esperado = period["first_seq"]
    prev = ZERO32 if period["first_seq"] == 0 else bytes.fromhex(elos[0]["prev_hash"])
    for e in elos:
        if e["seq"] != seq_esperado:
            falha(f"buraco na sequência: esperava seq {seq_esperado}, veio {e['seq']}")
        rh = bytes.fromhex(e["row_hash"])
        if e["table_name"] != "genesis":
            obj = linhas.get(f"{e['table_name']}|{e['row_id']}")
            if obj is None:
                falha(f"seq {e['seq']}: linha ausente do dump")
            recomputado = hashlib.sha256(rfc8785.dumps(obj)).digest()
            if recomputado != rh:
                falha(f"seq {e['seq']} ({e['table_name']}/{e['row_id']}): "
                      f"row_hash não bate — linha ADULTERADA")
        if bytes.fromhex(e["prev_hash"]) != prev:
            falha(f"seq {e['seq']}: prev_hash não bate — corrente QUEBRADA")
        link = hashlib.sha256(prev + rh).digest()
        if bytes.fromhex(e["link_hash"]) != link:
            falha(f"seq {e['seq']}: link_hash não bate — corrente QUEBRADA")
        prev = link
        seq_esperado += 1
    print(f"[1/3] {len(elos)} linhas re-hasheadas e corrente fechada "
          f"(seq {period['first_seq']}..{period['last_seq']})")

    # 3: a raiz de Merkle
    raiz = merkle([bytes.fromhex(e["link_hash"]) for e in elos])
    if raiz != bytes.fromhex(period["merkle_root"]):
        falha("raiz de Merkle não bate com a declarada")
    print(f"[2/3] raiz de Merkle confere: {raiz.hex()[:32]}…")

    # 4: o carimbo RFC3161 cobre esta raiz
    rfc = [s for s in dump["stamps"] if s["kind"] == "rfc3161"]
    if not rfc:
        falha("sem carimbo RFC3161 no dump")
    der = base64.b64decode(rfc[0]["proof_b64"])
    try:
        from pyasn1.codec.der import decoder
        from rfc3161ng import TimeStampToken, get_timestamp
        tst, _ = decoder.decode(der, asn1Spec=TimeStampToken())
        imprint = bytes(tst.tst_info.message_imprint["hashedMessage"])
        # RFC3161: o token carrega o HASH do dado carimbado — carimbamos a raiz
        # (32 bytes), então messageImprint = sha256(raiz)
        if imprint != hashlib.sha256(raiz).digest():
            falha("o carimbo RFC3161 NÃO cobre esta raiz (messageImprint difere)")
        print(f"[3/3] carimbo RFC3161 cobre a raiz; horário assinado pelo TSA: "
              f"{get_timestamp(tst)}")
    except ImportError:
        print("[3/3] rfc3161ng ausente — carimbo presente mas não decodificado aqui")
    print("VERDE: período íntegro. (Checagem completa da assinatura do TSA: "
          "openssl ts -verify -digest <sha256 da raiz, hex> -in carimbo.der "
          "-token_in -CAfile cacert-freetsa.pem)")


if __name__ == "__main__":
    main()
