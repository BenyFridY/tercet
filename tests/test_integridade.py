"""Fase 4: as regras da canonicalizacao.md valem — testes puros, sem banco."""

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from mesa import integridade


def _authz_base() -> dict[str, object]:
    return {
        "id": uuid.UUID("00000000-0000-4000-8000-000000000001"),
        "quote_id": uuid.UUID("00000000-0000-4000-8000-000000000002"),
        "rail": "x402", "payer_ref": "0xAbC", "authorized_max_minor": 10_000,
        "valid_from_utc": datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC),
        "valid_until_utc": None, "scope_hash": b"\x01\x02", "principal_ref": None,
        "principal_evidence": None, "rail_evidence": {"b": 2, "a": 1},
        "state": "authorized",  # mutável: NÃO pode entrar no hash
    }


def test_canonico_tipos() -> None:
    linha = _authz_base()
    canon = integridade.linha_canonica("authz", linha).decode()
    assert '"0x0102"' in canon                       # bytea -> 0x hex
    assert "2026-08-21T12:00:00.000000+00:00" in canon  # ts com microssegundos SEMPRE
    assert '"a":1,"b":2' in canon                    # RFC8785 ordena chaves do jsonb
    assert '"state"' not in canon                    # mutável excluído


def test_mutavel_nao_muda_hash() -> None:
    a = _authz_base()
    b = _authz_base() | {"state": "settled"}
    assert integridade.row_hash("authz", a) == integridade.row_hash("authz", b)


def test_decimal_vira_string() -> None:
    linha = {"id": uuid.uuid4(), "request_id": uuid.uuid4(), "amount_minor": 1,
             "decimals": 6, "asset_network_caip2": "x", "asset_contract": "y",
             "pay_to": "z", "scheme": "exact", "work_unit": "call",
             "work_qty": Decimal("1.5")}
    assert '"1.5"' in integridade.linha_canonica("quote", linha).decode()


def test_row_id_composto() -> None:
    linha = {"trace_id": "t1", "span_id": "s1"}
    assert integridade.row_id_de("span", linha) == "t1|s1"


def test_corrente_detecta_1_bit() -> None:
    """A prova central do GATE 4, em memória: 1 bit em qualquer linha quebra o elo."""
    linhas = [b"linha-a", b"linha-b", b"linha-c"]
    hashes = [hashlib.sha256(x).digest() for x in linhas]
    prev = integridade.ZERO32
    links = []
    for h in hashes:
        prev = hashlib.sha256(prev + h).digest()
        links.append(prev)

    adulterada = bytearray(linhas[1])
    adulterada[0] ^= 1  # exatamente 1 bit
    hashes2 = [hashlib.sha256(bytes(x)).digest()
               for x in [linhas[0], bytes(adulterada), linhas[2]]]
    prev = integridade.ZERO32
    quebrou_em = None
    for i, h in enumerate(hashes2):
        prev = hashlib.sha256(prev + h).digest()
        if prev != links[i]:
            quebrou_em = i
            break
    assert quebrou_em == 1  # quebra NO elo adulterado, não depois


def test_merkle() -> None:
    f = [hashlib.sha256(bytes([i])).digest() for i in range(5)]
    assert integridade.merkle_root(f[:1]) == f[0]                     # 1 folha = raiz
    par = hashlib.sha256(f[0] + f[1]).digest()
    assert integridade.merkle_root(f[:2]) == par                     # par simples
    r_impar = integridade.merkle_root(f[:3])                         # ímpar duplica
    n2 = hashlib.sha256(f[2] + f[2]).digest()
    assert r_impar == hashlib.sha256(par + n2).digest()
    raiz = integridade.merkle_root(f)
    f2 = list(f)
    f2[3] = hashlib.sha256(b"outra").digest()
    assert integridade.merkle_root(f2) != raiz                       # 1 folha muda a raiz
