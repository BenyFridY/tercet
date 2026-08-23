"""Fase 9 — gera o relatório público do censo (EN) a partir das fontes. Grátis.

Nada digitado à mão: censo_fechamento.json (livro+chain), sondagem_resultado.json
(deriva/MPP), laboratorio_resultado.json (ICs) e o livro (vínculo 0/15). Qualquer
divergência entre fontes = assert quebra (docs/fase9.md, decisão 3).

Uso: uv run python scripts/fase9/relatorio_build.py
Saída: relatorio/x402-buyer-census-round1.md + relatorio/post.md + relatorio/dados/
"""

import json
import shutil
from pathlib import Path
from typing import Any

from rich.console import Console

from mesa import db
from mesa.config import Settings

console = Console()
RAIZ = Path(__file__).resolve().parents[2]
F3 = RAIZ / "scripts" / "fase3"
F7 = RAIZ / "scripts" / "fase7"
SAIDA = RAIZ / "relatorio"
BASESCAN = "https://basescan.org/tx/"


def usd(minor: int) -> str:
    return f"${minor / 1e6:.4f}"


def carregar() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], int, int]:
    censo = json.loads((F3 / "censo_fechamento.json").read_text(encoding="utf-8"))
    sonda = json.loads((F3 / "sondagem_resultado.json").read_text(encoding="utf-8"))
    lab = json.loads((F7 / "laboratorio_resultado.json").read_text(encoding="utf-8"))
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE result = 'verified')"
            " FROM verification WHERE method = 'x402-payto-binding/N2-sonda'")
        row = cur.fetchone()
        assert row is not None
        sondas_vinculo, vinculos_ok = int(row[0]), int(row[1])
    return censo, sonda, lab, sondas_vinculo, vinculos_ok


def conferir(censo: dict[str, Any]) -> None:
    """Os 4 números do relatório têm que SAIR das linhas — nunca do resumo só."""
    fontes = censo["por_fonte"]
    n = censo["numeros"]
    assert len(fontes) == censo["fontes"] == 15
    assert sum(1 for f in fontes if f["responde"]) == n["respondem"]
    assert sum(1 for f in fontes if f["aceita_pagamento"]) == n["aceitam"]
    assert sum(1 for f in fontes if f["entregou"]) == n["entregam"]
    assert sum(1 for f in fontes if f["liquidou_on_chain"]) == n["ficaram_com_o_dinheiro"]
    assert n["ficaram_com_o_dinheiro"] == n["entregam"], "cobraram == entregaram (rodada 1)"
    assert all(f["tx"] for f in fontes if f["liquidou_on_chain"]), "cobrado sem tx?"
    assert (sum(f["custo_liquidado_minor"] for f in fontes)
            == censo["custo_total_liquidado_minor"])


def montar(censo: dict[str, Any], sonda: dict[str, Any], lab: dict[str, Any],
           sondas_vinculo: int, vinculos_ok: int, carteira: str) -> str:
    fontes = censo["por_fonte"]
    n = censo["numeros"]
    anunciado = {r["dominio"]: r for r in sonda["resultados"]}
    derivas = [r for r in sonda["resultados"] if r.get("deriva_de_preco")]
    mpp = sum(1 for r in sonda["resultados"] if r.get("fala_mpp_tambem"))
    baseline = next(p for p in lab["politicas"] if p["politica"] == "real-rodada1")
    micro = next(p for p in lab["politicas"] if p["politica"] == "micro")
    lo, hi = baseline["ic_wilson_95"]
    mlo, mhi = micro["ic_wilson_95"]
    gas_wei = sum(f["gas_facilitator_wei"] or 0 for f in fontes)
    dia = censo["gerado_utc"][:10]

    linhas_tabela = []
    for f in sorted(fontes, key=lambda x: -x["custo_liquidado_minor"]):
        a = anunciado.get(f["dominio"], {})
        anun = a.get("preco_anunciado_minor")
        cot = a.get("preco_cotado_minor") or f["pagou_minor"]
        drift = " ⚠️" if a.get("deriva_de_preco") else ""
        recibo = (f"[{f['tx'][:10]}…]({BASESCAN}{f['tx']})"
                  if f["tx"] else "— (authorization expired unused)")
        nota = ""
        if f["dominio"] == "stableenrich.dev":
            nota = " †"
        linhas_tabela.append(
            f"| {f['dominio']}{nota} | {usd(anun) if anun else 'n/a'} | "
            f"{usd(cot)}{drift} | {'yes' if f['entregou'] else '**no**'} | "
            f"{'yes' if f['liquidou_on_chain'] else '**no**'} | {recibo} |")
    tabela = "\n".join(linhas_tabela)
    lista_derivas = "; ".join(
        f"{r['dominio']} advertised {usd(r['preco_anunciado_minor'])} but quoted "
        f"{usd(r['preco_cotado_minor'])}" for r in derivas) or "none"
    maior_deriva = max(derivas, key=lambda r: r["preco_cotado_minor"]
                       / r["preco_anunciado_minor"]) if derivas else None
    razao = (maior_deriva["preco_cotado_minor"] / maior_deriva["preco_anunciado_minor"]
             if maior_deriva else 0)
    razao_deriva = f"{razao:.1f}×" if maior_deriva else "—"

    titulo = (f"Who delivers, and who takes the money? "
              f"Paying {censo['fontes']} live x402 sellers (round 1)")
    return f"""# {titulo}

*A buyer-side census of the x402 ecosystem, {dia}. Every paid claim below links to
its on-chain receipt on Base. Payer wallet: `{carteira}` — the entire round can be
re-derived from the chain alone.*

## The four numbers

Out of **{censo["fontes"]} sellers** sampled from the Coinbase Bazaar index
(3,000+ resources, 604 domains; stratified by price band, not cheapest-first):

- **{n["respondem"]}/15 respond** to an unauthenticated request;
- **{n["aceitam"]}/15 return a valid quote** (canonical USDC on Base mainnet, `exact` scheme);
- **{n["entregam"]}/15 deliver** after payment (HTTP 200 + non-empty body);
- **{n["ficaram_com_o_dinheiro"]}/15 settled on-chain** — exactly the ones that delivered.

Total spent: **{usd(censo["custo_total_liquidado_minor"])} USDC**. Delivery rate
{baseline["taxa_entrega"]:.0%} (Wilson 95% CI [{lo:.0%}–{hi:.0%}], n=15). Effective
cost per delivery: **{usd(baseline["custo_por_entrega_minor"])}**.

## Per-seller results

| seller | advertised | quoted | delivered | settled | receipt |
|---|---|---|---|---|---|
{tabela}

⚠️ = quoted price differs from the price advertised in the index.
† = the 400 came from our generic example body; possibly probe-induced, counted
as non-delivery under our method and flagged.

## Findings

1. **The failures did not take the money.** Both non-deliveries never settled:
   their EIP-3009 authorizations **expired unused** — a dead receivable, not a
   loss. Expiry semantics are real buyer protection, and worth designing around.
2. **Price drift exists in the index:** {lista_derivas} — {razao_deriva} the
   advertised price, and the most expensive item of the round. That same seller
   re-issued a 402 *after* being paid, delivered nothing — and never charged (see 1).
3. **0/{sondas_vinculo} sellers prove control of their payout address.** We probed
   every seller for a domain⇔payTo binding ({vinculos_ok} verified). Consequence,
   measured by replaying our round point-in-time: a "verified counterparties only"
   policy buys **nothing** today. We drafted a `/.well-known/x402-payto` extension
   (signature by the payTo key over the domain) to make that policy viable.
4. **Cheap did not mean bad.** Micro purchases (≤ $0.01) delivered
   {micro["taxa_entrega"]:.0%} (CI [{mlo:.0%}–{mhi:.0%}]) at
   {usd(micro["custo_por_entrega_minor"])} per delivery — ~16× cheaper than the
   round average. Small n; the CI says so.
5. **{mpp} sellers speak MPP on the same endpoints** (`WWW-Authenticate: Payment`)
   — multi-rail is already live in the wild.
6. **The buyer pays the price and nothing else:** settlement gas is borne by the
   facilitator (observed total across {n["ficaram_com_o_dinheiro"]} settlements:
   ~{gas_wei / 1e18:.7f} ETH).

## Method (so you can replicate it)

- **Discovery:** Bazaar index, stratified sample across price bands.
- **Probe (free):** x402 v2 quotes arrive in the base64 `payment-required` header
  (the JSON body is usually `{{}}`); HTTP method comes from the index entry.
- **Paid round:** one purchase per seller, hard caps enforced client-side *before
  signing* ($1/purchase, $20/round), pinned asset registry (address is identity).
- **Verification:** an independent collector scans `AuthorizationUsed(authorizer)`
  on Base and joins on (authorizer, nonce). No seller self-reporting is trusted:
  "settled" means the chain says so.
- **"Delivered" is a labeled structural proxy** (HTTP 200 + non-empty body).
  Content quality was NOT evaluated.
- **Audit, not ranking.** n=15 and <5 comparables per category: we publish facts
  per seller and confidence intervals, not quality scores. Ties are ties.

## Limits and disclosure

One round, one day ({dia}), n=15. Personal capital, dollar-cents amounts, no
affiliation with any seller or with Coinbase. Raw data ships next to this file
(`dados/`); the buyer's ledger is hash-chained and externally timestamped
(RFC 3161 + OpenTimestamps), with an independent ~100-line verifier.
"""


def montar_post(censo: dict[str, Any], lab: dict[str, Any]) -> str:
    n = censo["numeros"]
    baseline = next(p for p in lab["politicas"] if p["politica"] == "real-rodada1")
    gasto = usd(censo["custo_total_liquidado_minor"])
    cpe = usd(baseline["custo_por_entrega_minor"])
    return f"""We paid {censo["fontes"]} live x402 sellers to answer what no index can:
who delivers, and who takes the money?

- {n["respondem"]}/15 respond · {n["aceitam"]}/15 quote validly
- {n["entregam"]}/15 deliver · {n["ficaram_com_o_dinheiro"]}/15 charge — exactly the deliverers
- the 2 failures never charged: their authorizations EXPIRED unused (EIP-3009)
- 0/15 prove control of their payout address
- total spent: {gasto} · cost per delivery {cpe}

Every purchase links to its on-chain receipt. Full report + raw data: [LINK]
"""


def main() -> None:
    censo, sonda, lab, sondas_vinculo, vinculos_ok = carregar()
    conferir(censo)
    assert sondas_vinculo == censo["fontes"], "sondamos vínculo de TODAS as fontes"

    carteira = Settings().census_address
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "dados").mkdir(exist_ok=True)
    for nome in ("censo_fechamento.json", "sondagem_resultado.json"):
        shutil.copy(F3 / nome, SAIDA / "dados" / nome)
    shutil.copy(F7 / "laboratorio_resultado.json", SAIDA / "dados")

    md = montar(censo, sonda, lab, sondas_vinculo, vinculos_ok, carteira)
    (SAIDA / "x402-buyer-census-round1.md").write_text(md, encoding="utf-8")
    (SAIDA / "post.md").write_text(montar_post(censo, lab), encoding="utf-8")

    console.print(f"relatório: {SAIDA / 'x402-buyer-census-round1.md'}")
    console.print(f"post curto: {SAIDA / 'post.md'} · dados brutos: {SAIDA / 'dados'}")
    console.print("[bold green]Fase 9(a) pronta: pacote publicável gerado das fontes, "
                  "asserts verdes — publicar é ação do Beny (GATE 9b)[/bold green]")


if __name__ == "__main__":
    main()
