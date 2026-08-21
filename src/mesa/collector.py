"""O coletor — a chain é a fonte de verdade; o livro casa com ela ou explica por quê.

Dois modos, mesma chave de join `(authorizer, nonce)`:

- **Vendedor** (`main`, Fase 1): `AuthorizationUsed` não carrega destinatário, então busca
  `Transfer(to = payTo)` no USDC e extrai o `AuthorizationUsed` do MESMO txHash.
- **Comprador** (`main_pagador`, Fase 3): no censo NÓS somos o pagador e o payTo muda por
  fonte — mas `AuthorizationUsed(authorizer, nonce)` tem o authorizer INDEXADO, então
  filtra direto pela NOSSA carteira. O `Transfer(from = nós)` do mesmo tx dá o valor.

Idempotente por construção: UNIQUE (rail, network, external_ref) em settlement +
ON CONFLICT DO NOTHING. Rodar duas vezes = as mesmas linhas. Cursor persistido em
collector_cursor (tabela operacional, fora do livro), nomeado por rede+modo.

Uso: uv run python -m mesa.collector [lookback_blocks_na_primeira_rodada]
     uv run python -m mesa.collector --pagador [lookback]   (mainnet, censo)
"""

import json
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from eth_typing import HexStr
from hexbytes import HexBytes
from rich.console import Console
from web3 import Web3

from mesa import db, integridade
from mesa.config import (
    CAIP2_BASE_MAINNET,
    CAIP2_BASE_SEPOLIA,
    USDC_BASE_MAINNET,
    USDC_BASE_SEPOLIA,
    Settings,
)

console = Console()
CURSOR_VENDEDOR = "base-sepolia-usdc-payto"
CURSOR_PAGADOR = "base-mainnet-usdc-authorizer"
CHUNK = 999           # RPC público limita ~1000 blocos por eth_getLogs
FINAL_AFTER = 10      # regra simples do v0: >10 confirmações = final

TRANSFER_SIG = "Transfer(address,address,uint256)"
AUTH_USED_SIG = "AuthorizationUsed(address,bytes32)"


def _upsert_cursor(conn: psycopg.Connection[Any], name: str, block: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO collector_cursor (name, last_block, updated_utc)"
            " VALUES (%s,%s,%s) ON CONFLICT (name) DO UPDATE"
            " SET last_block = EXCLUDED.last_block, updated_utc = EXCLUDED.updated_utc",
            (name, block, db.now_utc()),
        )
    conn.commit()


def _get_cursor(conn: psycopg.Connection[Any], name: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT last_block FROM collector_cursor WHERE name = %s", (name,))
        row = cur.fetchone()
        return int(row[0]) if row else None


def _addr_topic(address: str) -> HexStr:
    """Endereço EVM como topic indexado (32 bytes, zero-padded à esquerda)."""
    return HexStr("0x" + "0" * 24 + address[2:].lower())


def _gravar_settlement(
    cur: psycopg.Cursor[Any],
    w3: Web3,
    receipt: Any,
    latest: int,
    caip2: str,
    value: int,
    txh: HexBytes,
) -> tuple[Any, bool]:
    """Insere o settlement (idempotente); devolve (id, inserido_agora)."""
    block = w3.eth.get_block(receipt["blockNumber"])
    confirmations = latest - int(receipt["blockNumber"])
    fee_wei = int(receipt["gasUsed"]) * int(receipt.get("effectiveGasPrice", 0))
    sid: Any = uuid.uuid4()
    tx_hex = "0x" + txh.hex() if not txh.hex().startswith("0x") else txh.hex()
    cur.execute(
        "INSERT INTO settlement (id, rail, external_ref, network_caip2, block_number,"
        " block_ts_utc, confirmations, finality, total_amount_minor, fee_amount_minor)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON CONFLICT (rail, network_caip2, external_ref) DO NOTHING RETURNING id",
        (sid, "x402", tx_hex, caip2, int(receipt["blockNumber"]),
         datetime.fromtimestamp(int(block["timestamp"]), tz=UTC), confirmations,
         "final" if confirmations > FINAL_AFTER else "pending",
         value, fee_wei),  # fee em wei de ETH (gas do facilitator), não em USDC
    )
    row = cur.fetchone()
    if row is None:  # já existia (rodada anterior) — busca o id para o leg
        cur.execute(
            "SELECT id FROM settlement WHERE rail=%s AND network_caip2=%s"
            " AND external_ref=%s",
            ("x402", caip2, tx_hex),
        )
        fetched = cur.fetchone()
        assert fetched is not None
        return fetched[0], False

    # Fase 4: elo da corrente + observação como EVENTO (mesma transação do batch)
    conn = cur.connection
    integridade.registrar_elo(conn, "settlement", {
        "id": sid, "rail": "x402", "external_ref": tx_hex, "network_caip2": caip2,
        "block_number": int(receipt["blockNumber"]),
        "block_ts_utc": datetime.fromtimestamp(int(block["timestamp"]), tz=UTC),
        "facilitator_ref": None, "total_amount_minor": value,
        "fee_amount_minor": fee_wei, "fee_asset_contract": None,
    })
    eid = uuid.uuid4()
    ev_ts = db.now_utc()
    ev_kind = "final" if confirmations > FINAL_AFTER else "observed"
    cur.execute(
        "INSERT INTO settlement_event (id, settlement_id, ts_utc, kind, block_number,"
        " confirmations, detail) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (eid, sid, ev_ts, ev_kind, int(receipt["blockNumber"]), confirmations, None),
    )
    integridade.registrar_elo(conn, "settlement_event", {
        "id": eid, "settlement_id": sid, "ts_utc": ev_ts, "kind": ev_kind,
        "block_number": int(receipt["blockNumber"]), "confirmations": confirmations,
        "detail": None,
    })
    return row[0], True


def _casar(cur: psycopg.Cursor[Any], sid: Any, authorizer: str, nonce: str, value: int) -> bool:
    """O casamento: (authorizer, nonce) contra o livro. Devolve True se casou."""
    cur.execute(
        "SELECT id FROM authz WHERE rail='x402'"
        " AND lower((rail_evidence->'authorization')->>'from') = %s"
        " AND lower((rail_evidence->'authorization')->>'nonce') = %s",
        (authorizer.lower(), nonce.lower()),
    )
    hit = cur.fetchone()
    if not hit:
        return False
    cur.execute(
        "INSERT INTO settlement_leg (settlement_id, authorization_id,"
        " settled_amount_minor) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING 1",
        (sid, hit[0], value),
    )
    novo_leg = cur.fetchone() is not None
    cur.execute(  # coluna mantida por compatibilidade até a Fase 6; a verdade é o evento
        "UPDATE authz SET state='settled' WHERE id=%s", (hit[0],)
    )
    if novo_leg:  # Fase 4: elo do leg + 'settled' como EVENTO (mesma transação)
        conn = cur.connection
        integridade.registrar_elo(conn, "settlement_leg", {
            "settlement_id": sid, "authorization_id": hit[0],
            "settled_amount_minor": value,
        })
        eid = uuid.uuid4()
        ev_ts = db.now_utc()
        cur.execute(
            "INSERT INTO authz_event (id, authorization_id, ts_utc, kind, detail)"
            " VALUES (%s,%s,%s,%s,%s)",
            (eid, hit[0], ev_ts, "settled",
             json.dumps({"settlement_id": str(sid)})),
        )
        integridade.registrar_elo(conn, "authz_event", {
            "id": eid, "authorization_id": hit[0], "ts_utc": ev_ts,
            "kind": "settled", "detail": {"settlement_id": str(sid)},
        })
    return True


def main(first_run_lookback: int) -> None:
    """Modo VENDEDOR (Fase 1, testnet): Transfer(to = payTo) → AuthorizationUsed do mesmo tx."""
    s = Settings()
    conn = db.connect()
    db.apply_migrations(conn)

    w3 = Web3(Web3.HTTPProvider(s.rpc_url))
    latest = w3.eth.block_number
    start = _get_cursor(conn, CURSOR_VENDEDOR)
    if start is None:
        start = latest - first_run_lookback
    usdc = Web3.to_checksum_address(USDC_BASE_SEPOLIA)
    transfer_topic = w3.keccak(text=TRANSFER_SIG)
    auth_topic = w3.keccak(text=AUTH_USED_SIG)

    console.print(f"[vendedor] varrendo blocos {start}..{latest} em faixas de {CHUNK}")
    tx_hashes: list[HexBytes] = []
    frm = start
    while frm <= latest:
        to = min(frm + CHUNK, latest)
        logs = w3.eth.get_logs({
            "address": usdc,
            "fromBlock": frm,
            "toBlock": to,
            "topics": [transfer_topic, None, _addr_topic(s.seller_payto)],
        })
        tx_hashes.extend(HexBytes(lg["transactionHash"]) for lg in logs)
        frm = to + 1

    console.print(f"{len(tx_hashes)} transferências USDC para o payTo encontradas")
    inserted = matched = 0
    with conn.cursor() as cur:
        for txh in tx_hashes:
            receipt = w3.eth.get_transaction_receipt(txh)
            value = authorizer = nonce = None
            for lg in receipt["logs"]:
                if lg["address"].lower() != usdc.lower():
                    continue
                if lg["topics"][0] == transfer_topic and lg["topics"][2].hex().lower().endswith(
                    s.seller_payto[2:].lower()
                ):
                    value = int.from_bytes(lg["data"], "big")
                elif lg["topics"][0] == auth_topic:
                    authorizer = "0x" + lg["topics"][1].hex()[-40:]
                    nonce = "0x" + lg["topics"][2].hex()
            if value is None:
                continue

            sid, novo = _gravar_settlement(
                cur, w3, receipt, latest, CAIP2_BASE_SEPOLIA, value, txh
            )
            inserted += int(novo)
            if authorizer and nonce and _casar(cur, sid, authorizer, nonce, value):
                matched += 1
    conn.commit()
    _upsert_cursor(conn, CURSOR_VENDEDOR, latest)
    console.print(f"settlements novos: {inserted} · casados com o livro: {matched} "
                  f"· cursor -> {latest}")


def main_pagador(first_run_lookback: int) -> None:
    """Modo COMPRADOR (Fase 3, MAINNET): AuthorizationUsed(authorizer = carteira do censo)."""
    s = Settings()
    if not s.census_address:
        raise SystemExit("CENSUS_ADDRESS ausente no env — rodar a T1 da Fase 3 primeiro")
    conn = db.connect()
    db.apply_migrations(conn)

    w3 = Web3(Web3.HTTPProvider(s.rpc_url_mainnet))
    latest = w3.eth.block_number
    start = _get_cursor(conn, CURSOR_PAGADOR)
    if start is None:
        start = latest - first_run_lookback
    usdc = Web3.to_checksum_address(USDC_BASE_MAINNET)
    transfer_topic = w3.keccak(text=TRANSFER_SIG)
    auth_topic = w3.keccak(text=AUTH_USED_SIG)
    nos = _addr_topic(s.census_address)

    console.print(f"[pagador/mainnet] varrendo blocos {start}..{latest} em faixas de {CHUNK}")
    eventos: list[tuple[HexBytes, str, str]] = []  # (tx, authorizer, nonce)
    frm = start
    while frm <= latest:
        to = min(frm + CHUNK, latest)
        logs = w3.eth.get_logs({
            "address": usdc,
            "fromBlock": frm,
            "toBlock": to,
            "topics": [auth_topic, nos],  # o filtro é a NOSSA carteira como authorizer
        })
        eventos.extend(
            (HexBytes(lg["transactionHash"]),
             "0x" + lg["topics"][1].hex()[-40:],
             "0x" + lg["topics"][2].hex())
            for lg in logs
        )
        frm = to + 1

    console.print(f"{len(eventos)} autorizações NOSSAS usadas on-chain")
    inserted = matched = 0
    with conn.cursor() as cur:
        for txh, authorizer, nonce in eventos:
            receipt = w3.eth.get_transaction_receipt(txh)
            value = None
            for lg in receipt["logs"]:  # o valor: Transfer(from = nós) do mesmo tx
                if (lg["address"].lower() == usdc.lower()
                        and lg["topics"][0] == transfer_topic
                        and lg["topics"][1].hex().lower().endswith(
                            s.census_address[2:].lower())):
                    value = int.from_bytes(lg["data"], "big")
            if value is None:
                continue

            sid, novo = _gravar_settlement(
                cur, w3, receipt, latest, CAIP2_BASE_MAINNET, value, txh
            )
            inserted += int(novo)
            if _casar(cur, sid, authorizer, nonce, value):
                matched += 1
    conn.commit()
    _upsert_cursor(conn, CURSOR_PAGADOR, latest)
    console.print(f"settlements novos: {inserted} · casados com o livro: {matched} "
                  f"· cursor -> {latest}")


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--pagador"]
    lookback = int(argv[0]) if argv else 5000
    if "--pagador" in sys.argv:
        main_pagador(lookback)
    else:
        main(lookback)
