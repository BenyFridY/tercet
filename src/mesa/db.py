"""Acesso ao livro. INSERT-ONLY por construção nas tabelas do livro.

Nenhuma função aqui faz UPDATE ou DELETE em tabela do livro (invariante 3 / D-06).
A única exceção registrada do v0 é authz.state — e ela vive em função separada e nomeada.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from mesa import integridade
from mesa.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def connect() -> psycopg.Connection[Any]:
    try:
        return psycopg.connect(Settings().database_url, connect_timeout=5)
    except psycopg.OperationalError as e:
        raise SystemExit(
            "banco inacessível em 5s — o Docker caiu de novo? Runbook: "
            "abrir o Docker Desktop, depois `docker start mesa-pg`. "
            f"(detalhe: {e})"
        ) from e


def apply_migrations(conn: psycopg.Connection[Any]) -> list[str]:
    """Aplica migrations pendentes em ordem. SQL puro numerado, sem Alembic (D-18)."""
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS meta_migration ("
            "filename text PRIMARY KEY, applied_utc timestamptz NOT NULL DEFAULT now())"
        )
        cur.execute("SELECT filename FROM meta_migration")
        done = {row[0] for row in cur.fetchall()}
        applied: list[str] = []
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            cur.execute(path.read_text(encoding="utf-8"))  # SQL puro numerado
            cur.execute("INSERT INTO meta_migration (filename) VALUES (%s)", (path.name,))
            applied.append(path.name)
    conn.commit()
    return applied


def now_utc() -> datetime:
    return datetime.now(UTC)


def ts_from_unix(unix: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(unix), tz=UTC)
    except (TypeError, ValueError):
        return None


def insert_span(
    conn: psycopg.Connection[Any],
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    name: str,
    agent_ref: str | None,
    attributes: dict[str, Any] | None,
    started_utc: datetime,
    ended_utc: datetime | None = None,
    outcome: str | None = None,
) -> None:
    """Um span COMPLETO por linha (inserido no fim do span, nunca atualizado — D-06)."""
    linha: dict[str, Any] = {
        "trace_id": trace_id, "span_id": span_id, "parent_span_id": parent_span_id,
        "name": name, "agent_ref": agent_ref, "attributes": attributes,
        "started_utc": started_utc, "ended_utc": ended_utc, "outcome": outcome,
    }
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO span (trace_id, span_id, parent_span_id, name, agent_ref,"
            " attributes, started_utc, ended_utc, outcome)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (trace_id, span_id, parent_span_id, name, agent_ref,
             json.dumps(attributes) if attributes else None, started_utc,
             ended_utc, outcome),
        )
    integridade.registrar_elo(conn, "span", linha)  # Fase 4: mesma transação
    conn.commit()


def insert_request(
    conn: psycopg.Connection[Any],
    *,
    rail: str,
    resource_key_hash: bytes,
    method: str,
    status_http: int | None,
    body_sha256: bytes | None,
    body_bytes: int | None,
    content_type: str | None,
    delivered: bool,
    trace_id: str,
    span_id: str,
    transport: str,
    origin: str,
    tool_name: str | None = None,
    origin_ref: str | None = None,
    origin_receipt_sig: bytes | None = None,
) -> uuid.UUID:
    rid = uuid.uuid4()
    ts = now_utc()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO request (id, ts_utc, rail, resource_key_hash, method, status_http,"
            " body_sha256, body_bytes, content_type, delivered, trace_id, span_id,"
            " transport, tool_name, origin, origin_ref, origin_receipt_sig)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (rid, ts, rail, resource_key_hash, method, status_http, body_sha256,
             body_bytes, content_type, delivered, trace_id, span_id, transport,
             tool_name, origin, origin_ref, origin_receipt_sig),
        )
    integridade.registrar_elo(conn, "request", {
        "id": rid, "ts_utc": ts, "rail": rail, "resource_key_hash": resource_key_hash,
        "method": method, "status_http": status_http, "body_sha256": body_sha256,
        "body_bytes": body_bytes, "content_type": content_type, "delivered": delivered,
        "trace_id": trace_id, "span_id": span_id, "transport": transport,
        "tool_name": tool_name, "origin": origin, "origin_ref": origin_ref,
        "origin_receipt_sig": origin_receipt_sig,
    })
    conn.commit()
    return rid


def insert_quote(
    conn: psycopg.Connection[Any],
    *,
    request_id: uuid.UUID,
    amount_minor: int,
    decimals: int,
    asset_network_caip2: str,
    asset_contract: str,
    pay_to: str,
    scheme: str,
) -> uuid.UUID:
    qid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO quote (id, request_id, amount_minor, decimals, asset_network_caip2,"
            " asset_contract, pay_to, scheme) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (qid, request_id, amount_minor, decimals, asset_network_caip2,
             asset_contract, pay_to, scheme),
        )
    integridade.registrar_elo(conn, "quote", {
        "id": qid, "request_id": request_id, "amount_minor": amount_minor,
        "decimals": decimals, "asset_network_caip2": asset_network_caip2,
        "asset_contract": asset_contract, "pay_to": pay_to, "scheme": scheme,
        "work_unit": None, "work_qty": None,
    })
    conn.commit()
    return qid


def insert_authz(
    conn: psycopg.Connection[Any],
    *,
    quote_id: uuid.UUID,
    rail: str,
    payer_ref: str,
    authorized_max_minor: int,
    valid_from_utc: datetime | None,
    valid_until_utc: datetime | None,
    rail_evidence: dict[str, Any],
    state: str,
) -> uuid.UUID:
    aid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO authz (id, quote_id, rail, payer_ref, authorized_max_minor,"
            " valid_from_utc, valid_until_utc, rail_evidence, state)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (aid, quote_id, rail, payer_ref, authorized_max_minor, valid_from_utc,
             valid_until_utc, json.dumps(rail_evidence), state),
        )
    integridade.registrar_elo(conn, "authz", {  # state fora do canônico (mutável no v0)
        "id": aid, "quote_id": quote_id, "rail": rail, "payer_ref": payer_ref,
        "authorized_max_minor": authorized_max_minor, "valid_from_utc": valid_from_utc,
        "valid_until_utc": valid_until_utc, "scope_hash": None, "principal_ref": None,
        "principal_evidence": None, "rail_evidence": rail_evidence,
    })
    conn.commit()
    # Fase 4 (D-06 fechado): o estado inicial também é EVENTO
    insert_authz_event(conn, authorization_id=aid, kind=state, detail=None)
    return aid


def insert_authz_event(
    conn: psycopg.Connection[Any],
    *,
    authorization_id: uuid.UUID,
    kind: str,
    detail: dict[str, Any] | None,
) -> uuid.UUID:
    """Fase 4: mudança de estado da autorização como EVENTO append-only."""
    eid = uuid.uuid4()
    ts = now_utc()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO authz_event (id, authorization_id, ts_utc, kind, detail)"
            " VALUES (%s,%s,%s,%s,%s)",
            (eid, authorization_id, ts, kind, json.dumps(detail) if detail else None),
        )
    integridade.registrar_elo(conn, "authz_event", {
        "id": eid, "authorization_id": authorization_id, "ts_utc": ts,
        "kind": kind, "detail": detail,
    })
    conn.commit()
    return eid


def insert_verification(
    conn: psycopg.Connection[Any],
    *,
    subject_type: str,
    subject_ref: str,
    method: str,
    result: str,
    evidence: dict[str, Any],
    expires_at_utc: datetime | None = None,
) -> uuid.UUID:
    """Invariante 4: evidência, não booleano — método + prova completa + validade."""
    vid = uuid.uuid4()
    ts = now_utc()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO verification (id, subject_type, subject_ref, method, result,"
            " evidence, verified_at_utc, expires_at_utc) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (vid, subject_type, subject_ref, method, result, json.dumps(evidence),
             ts, expires_at_utc),
        )
    integridade.registrar_elo(conn, "verification", {
        "id": vid, "subject_type": subject_type, "subject_ref": subject_ref,
        "method": method, "result": result, "evidence": evidence,
        "verified_at_utc": ts, "expires_at_utc": expires_at_utc,
    })
    conn.commit()
    return vid


def insert_settlement_event(
    conn: psycopg.Connection[Any],
    *,
    settlement_id: uuid.UUID,
    kind: str,
    block_number: int | None,
    confirmations: int | None,
    detail: dict[str, Any] | None,
) -> uuid.UUID:
    """Fase 4: observação/confirmação/reorg de settlement como EVENTO append-only."""
    eid = uuid.uuid4()
    ts = now_utc()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO settlement_event (id, settlement_id, ts_utc, kind,"
            " block_number, confirmations, detail) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (eid, settlement_id, ts, kind, block_number, confirmations,
             json.dumps(detail) if detail else None),
        )
    integridade.registrar_elo(conn, "settlement_event", {
        "id": eid, "settlement_id": settlement_id, "ts_utc": ts, "kind": kind,
        "block_number": block_number, "confirmations": confirmations, "detail": detail,
    })
    conn.commit()
    return eid
