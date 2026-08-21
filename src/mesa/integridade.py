"""Fase 4: a corrente de hash do livro. Regras EXATAS: docs/canonicalizacao.md (normativo).

O verificador offline (verificador/) REIMPLEMENTA estas regras sem importar o mesa —
se mudar algo aqui, mudou o protocolo, não um detalhe.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg
import rfc8785

ZERO32 = bytes(32)

# Campos por tabela — mutáveis do v0 EXCLUÍDOS (authz.state; settlement.confirmations/
# finality): a verdade deles é a sequência de eventos (migration 0002).
CAMPOS: dict[str, list[str]] = {
    "span": ["trace_id", "span_id", "parent_span_id", "name", "agent_ref", "attributes",
             "started_utc", "ended_utc", "outcome"],
    "request": ["id", "ts_utc", "rail", "resource_key_hash", "method", "status_http",
                "body_sha256", "body_bytes", "content_type", "etag", "last_modified_utc",
                "delivered", "delivered_before_settle", "trace_id", "span_id",
                "transport", "tool_name", "origin", "origin_ref", "origin_receipt_sig"],
    "quote": ["id", "request_id", "amount_minor", "decimals", "asset_network_caip2",
              "asset_contract", "pay_to", "scheme", "work_unit", "work_qty"],
    "authz": ["id", "quote_id", "rail", "payer_ref", "authorized_max_minor",
              "valid_from_utc", "valid_until_utc", "scope_hash", "principal_ref",
              "principal_evidence", "rail_evidence"],
    "settlement": ["id", "rail", "external_ref", "network_caip2", "block_number",
                   "block_ts_utc", "facilitator_ref", "total_amount_minor",
                   "fee_amount_minor", "fee_asset_contract"],
    "settlement_leg": ["settlement_id", "authorization_id", "settled_amount_minor"],
    "verification": ["id", "subject_type", "subject_ref", "method", "result",
                     "evidence", "verified_at_utc", "expires_at_utc"],
    "authz_event": ["id", "authorization_id", "ts_utc", "kind", "detail"],
    "settlement_event": ["id", "settlement_id", "ts_utc", "kind", "block_number",
                         "confirmations", "detail"],
}
PK: dict[str, list[str]] = {
    "span": ["trace_id", "span_id"],
    "request": ["id"],
    "quote": ["id"],
    "authz": ["id"],
    "settlement": ["id"],
    "settlement_leg": ["settlement_id", "authorization_id"],
    "verification": ["id"],
    "authz_event": ["id"],
    "settlement_event": ["id"],
}


def _canonico(v: Any) -> Any:
    """Codificação de tipos da canonicalizacao.md. Nunca float."""
    if v is None or isinstance(v, bool | int | str):
        return v
    if isinstance(v, uuid.UUID):
        return str(v).lower()
    if isinstance(v, bytes | bytearray | memoryview):
        return "0x" + bytes(v).hex()
    if isinstance(v, datetime):
        return v.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, dict):
        return {k: _canonico(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_canonico(x) for x in v]
    raise TypeError(f"tipo sem regra de canonicalização: {type(v)}")


def objeto_canonico(tabela: str, linha: dict[str, Any]) -> dict[str, Any]:
    """O objeto {"tabela","linha"} com o conjunto FIXO de campos, tipos já codificados."""
    campos = CAMPOS[tabela]
    return {"tabela": tabela, "linha": {c: _canonico(linha.get(c)) for c in campos}}


def linha_canonica(tabela: str, linha: dict[str, Any]) -> bytes:
    """O objeto canônico serializado em RFC 8785."""
    return bytes(rfc8785.dumps(objeto_canonico(tabela, linha)))


def row_hash(tabela: str, linha: dict[str, Any]) -> bytes:
    return hashlib.sha256(linha_canonica(tabela, linha)).digest()


def row_id_de(tabela: str, linha: dict[str, Any]) -> str:
    return "|".join(str(_canonico(linha[c])) for c in PK[tabela])


def registrar_elo(conn: psycopg.Connection[Any], tabela: str,
                  linha: dict[str, Any]) -> None:
    """Insere o elo na MESMA transação da linha (chamar antes do commit).

    Corrida no seq (dois processos escrevendo) colide na PK e tenta de novo — 3×.
    """
    rh = row_hash(tabela, linha)
    rid = row_id_de(tabela, linha)
    ultimo_erro: Exception | None = None
    for _ in range(3):
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT seq, link_hash FROM ledger_hash"
                            " ORDER BY seq DESC LIMIT 1")
                row = cur.fetchone()
                if row is None:
                    raise SystemExit("corrente sem genesis — rodar o backfill da Fase 4")
                seq = int(row[0]) + 1
                prev = bytes(row[1])
                link = hashlib.sha256(prev + rh).digest()
                cur.execute(
                    "INSERT INTO ledger_hash (seq, table_name, row_id, row_hash,"
                    " prev_hash, link_hash, ts_utc) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (seq, tabela, rid, rh, prev, link, datetime.now(UTC)),
                )
            return
        except psycopg.errors.UniqueViolation as e:  # corrida no seq: tenta de novo
            ultimo_erro = e
            continue
    raise RuntimeError(f"não consegui registrar elo de {tabela}/{rid}") from ultimo_erro


def genesis(conn: psycopg.Connection[Any], texto: str) -> None:
    """Elo 0 (idempotente): hash do doc de genesis, prev = 32 zeros."""
    rh = hashlib.sha256(texto.encode("utf-8")).digest()
    link = hashlib.sha256(ZERO32 + rh).digest()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ledger_hash (seq, table_name, row_id, row_hash, prev_hash,"
            " link_hash, ts_utc) VALUES (0,'genesis','genesis',%s,%s,%s,%s)"
            " ON CONFLICT (seq) DO NOTHING",
            (rh, ZERO32, link, datetime.now(UTC)),
        )
    conn.commit()


def merkle_root(folhas: list[bytes]) -> bytes:
    """Folhas em ordem de seq; ímpar duplica o último; 1 folha = raiz."""
    if not folhas:
        raise ValueError("período sem elos não fecha")
    nivel = list(folhas)
    while len(nivel) > 1:
        if len(nivel) % 2:
            nivel.append(nivel[-1])
        nivel = [hashlib.sha256(nivel[i] + nivel[i + 1]).digest()
                 for i in range(0, len(nivel), 2)]
    return nivel[0]
