"""Fase 3 / T5 — o fechamento: os 4 números POR FONTE, com recibo linkado. GATE 3.

Cruza as quatro pontas do livro para cada fonte do censo:
1. **Responde?**            — sondagem (request sem pagamento, status 402)
2. **Aceita pagamento?**    — quote válida gravada na sondagem
3. **Entrega?**             — request da rodada com delivered=true
4. **Ficou com o dinheiro?**— settlement on-chain casado por (authorizer, nonce),
                              com o tx hash como recibo

Mais o custo (D-15): valor liquidado por fonte + gas do facilitator observado.

Autorização assinada mas NÃO liquidada fica como **pendente** — não é "nunca cobrou":
o vendedor segura uma autorização viva até o validBefore e pode liquidar tarde.
Re-rodar o coletor + este fechamento nos dias seguintes é parte do método.

Asserts do gate: consistência interna do livro (leg == quote, delivered coerente,
soma liquidada bate com a chain via coletor) — NUNCA assert de comportamento das
fontes (comportamento é RESULTADO do censo, não expectativa).

Uso: uv run python scripts/fase3/fechamento.py
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from mesa import db
from mesa.config import CAIP2_BASE_MAINNET, Settings

console = Console()
DIR = Path(__file__).parent
SAIDA = DIR / "censo_fechamento.json"


def main() -> None:
    s = Settings()
    conn = db.connect()
    candidatos = json.loads((DIR / "candidatos.json").read_text(encoding="utf-8"))
    fontes = candidatos["candidatos"]

    linhas: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for f in fontes:
            h = hashlib.sha256(f["url"].encode()).digest()

            # 1. responde? — alguma request SEM pagamento com resposta HTTP
            cur.execute(
                "SELECT bool_or(status_http IS NOT NULL), bool_or(status_http=402)"
                " FROM request r WHERE r.resource_key_hash=%s"
                " AND NOT EXISTS (SELECT 1 FROM quote q JOIN authz a ON a.quote_id=q.id"
                "                 WHERE q.request_id=r.id)",
                (h,),
            )
            row = cur.fetchone()
            responde = bool(row and row[0])
            pediu_402 = bool(row and row[1])

            # 2. aceita? — quote mainnet gravada (sondagem validou antes de gravar)
            cur.execute(
                "SELECT count(*) FROM quote q JOIN request r ON r.id=q.request_id"
                " WHERE r.resource_key_hash=%s AND q.asset_network_caip2=%s",
                (h, CAIP2_BASE_MAINNET),
            )
            row2 = cur.fetchone()
            aceita = bool(row2 and int(row2[0]) > 0)

            # 3. entrega? + 4. liquidou? — a compra da rodada (request COM authz)
            cur.execute(
                "SELECT r.delivered, r.status_http, q.amount_minor, a.state,"
                "       se.external_ref, sl.settled_amount_minor, se.fee_amount_minor"
                " FROM request r JOIN quote q ON q.request_id=r.id"
                " JOIN authz a ON a.quote_id=q.id"
                " LEFT JOIN settlement_leg sl ON sl.authorization_id=a.id"
                " LEFT JOIN settlement se ON se.id=sl.settlement_id"
                " WHERE r.resource_key_hash=%s AND lower(a.payer_ref)=lower(%s)"
                " ORDER BY r.ts_utc DESC LIMIT 1",
                (h, s.census_address),
            )
            compra = cur.fetchone()
            entregue = bool(compra and compra[0])
            liquidada = bool(compra and compra[4])
            if compra and compra[5] is not None and compra[2] != compra[5]:
                raise SystemExit(  # consistência do LIVRO, não das fontes
                    f"{f['dominio']}: leg {compra[5]} != quote {compra[2]}")
            linhas.append({
                "dominio": f["dominio"],
                "responde": responde,
                "pediu_402": pediu_402,
                "aceita_pagamento": aceita,
                "pagou_minor": int(compra[2]) if compra else None,
                "entregou": entregue,
                "status_da_compra": int(compra[1]) if compra and compra[1] else None,
                "liquidou_on_chain": liquidada,
                "tx": str(compra[4]) if compra and compra[4] else None,
                "estado_authz": str(compra[3]) if compra else None,
                "custo_liquidado_minor": int(compra[5]) if compra and compra[5] else 0,
                "gas_facilitator_wei": int(compra[6]) if compra and compra[6] else None,
            })

    # os 4 números do censo
    n = len(linhas)
    respondem = sum(1 for x in linhas if x["responde"])
    aceitam = sum(1 for x in linhas if x["aceita_pagamento"])
    entregam = sum(1 for x in linhas if x["entregou"])
    liquidaram = sum(1 for x in linhas if x["liquidou_on_chain"])
    pendentes = [x for x in linhas if x["estado_authz"] == "authorized"]
    custo_total = sum(x["custo_liquidado_minor"] for x in linhas)

    # asserts do GATE (livro íntegro; comportamento das fontes é resultado, não assert)
    assert all(x["liquidou_on_chain"] == (x["estado_authz"] == "settled")
               for x in linhas if x["estado_authz"]), "estado authz != settlement"
    assert all(x["tx"] for x in linhas if x["liquidou_on_chain"]), "liquidada sem tx"

    t = Table(title=f"CENSO x402 — rodada 1 ({n} fontes, Base mainnet)")
    t.add_column("domínio")
    t.add_column("responde")
    t.add_column("aceita")
    t.add_column("entregou")
    t.add_column("cobrou?")
    t.add_column("US$", justify="right")
    t.add_column("tx (recibo)")
    for x in linhas:
        t.add_row(
            x["dominio"],
            "sim" if x["responde"] else "NÃO",
            "sim" if x["aceita_pagamento"] else "não",
            "sim" if x["entregou"] else "[red]NÃO[/red]",
            ("sim" if x["liquidou_on_chain"]
             else ("[yellow]pendente[/yellow]" if x["estado_authz"] == "authorized"
                   else ("não (expirou)" if x["estado_authz"] == "failed" else "não"))),
            f"{x['custo_liquidado_minor'] / 1e6:.4f}",
            (x["tx"][:16] + "…") if x["tx"] else "—",
        )
    console.print(t)
    console.print(
        f"[bold]{respondem}/{n} respondem · {aceitam}/{n} aceitam · "
        f"{entregam}/{n} entregam · {liquidaram}/{n} ficaram com o dinheiro · "
        f"custo total liquidado US$ {custo_total / 1e6:.4f}[/bold]"
    )
    if pendentes:
        console.print(
            f"[yellow]{len(pendentes)} autorização(ões) assinada(s) e NÃO liquidada(s) "
            f"(o vendedor pode liquidar até o validBefore — re-rodar coletor+fechamento "
            f"nos próximos dias): "
            + ", ".join(f"{x['dominio']} (US$ {x['pagou_minor'] / 1e6:.4f})"
                        for x in pendentes) + "[/yellow]"
        )
    expiradas = [x for x in linhas if x["estado_authz"] == "failed"]
    if expiradas:
        console.print(
            f"{len(expiradas)} autorização(ões) EXPIRARAM sem liquidação — o vendedor "
            f"não cobrou e não pode mais cobrar (vigilância encerrada): "
            + ", ".join(x["dominio"] for x in expiradas)
        )

    SAIDA.write_text(json.dumps({
        "gerado_utc": datetime.now(UTC).isoformat(),
        "fontes": n,
        "numeros": {"respondem": respondem, "aceitam": aceitam,
                    "entregam": entregam, "ficaram_com_o_dinheiro": liquidaram},
        "custo_total_liquidado_minor": custo_total,
        "pendentes": [x["dominio"] for x in pendentes],
        "por_fonte": linhas,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"gravado em {SAIDA}")
    console.print("[bold green]GATE 3: os 4 números fecham com recibo linkado[/bold green]")


if __name__ == "__main__":
    main()
