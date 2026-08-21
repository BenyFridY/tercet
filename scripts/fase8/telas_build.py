"""Fase 8 — GATE 8: gera as telas (blotter + TCA) do dado REAL do livro. Grátis.

Página HTML autocontida (docs/fase8.md): visual de design/produto/, dados embutidos
em JSON, JS puro para abas/filtros/drawer. Regenerar = rodar de novo. Nunca mock.

Uso: uv run python scripts/fase8/telas_build.py
Saída: scripts/fase8/mesa-telas.html (abrir no navegador)
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from mesa import db, telas

console = Console()
DIR = Path(__file__).parent
SAIDA = DIR / "mesa-telas.html"
CANDIDATOS = DIR.parent / "fase3" / "candidatos.json"

# canônicos conhecidos (D-11: o LIVRO só tem hash; a tela traduz com este mapa público)
CANONICOS_FIXOS = {
    "GET http://127.0.0.1:8402/brinquedo": "brinquedo (vendedor local)",
    "http://127.0.0.1:8402/brinquedo": "brinquedo (vendedor local)",
    "GET http://127.0.0.1:8402/free-ride": "free-ride (caos fase 1)",
    "mcp://127.0.0.1:8403/tool/consultar": "mcp · consultar (vendedor local)",
    "llm:anthropic:claude-sonnet-5": "anthropic · claude-sonnet-5",
}


def construir_mapa() -> dict[str, str]:
    mapa = {hashlib.sha256(c.encode()).hexdigest(): rotulo
            for c, rotulo in CANONICOS_FIXOS.items()}
    if CANDIDATOS.exists():
        for c in json.loads(CANDIDATOS.read_text(encoding="utf-8"))["candidatos"]:
            mapa[hashlib.sha256(c["url"].encode()).hexdigest()] = c["dominio"]
    return mapa


def fontes_tca(linhas: list[telas.Linha]) -> list[dict[str, Any]]:
    """TCA: custo por ENTREGA por fonte (compras com cotação, agrupadas por rótulo)."""
    grupos: dict[str, dict[str, Any]] = {}
    for ln in linhas:
        # cotação sem pagamento (sondagem) NÃO é compra — fora da tabela de fontes
        if ln.amount_minor is None or ln.estado == "sem-pagamento":
            continue
        chave = ln.dominio or ln.recurso_hash[:12]
        g = grupos.setdefault(chave, {
            "fonte": chave, "network": ln.network, "rail": ln.rail,
            "compras": 0, "gasto_minor": 0, "entregas": 0})
        g["compras"] += 1
        g["gasto_minor"] += ln.settled_minor
        g["entregas"] += int(ln.delivered)
    for g in grupos.values():
        g["custo_por_entrega_minor"] = (
            round(g["gasto_minor"] / g["entregas"]) if g["entregas"] else None)
    return sorted(grupos.values(), key=lambda g: -g["gasto_minor"])


def main() -> None:
    conn = db.connect()
    db.apply_migrations(conn)
    mapa = construir_mapa()

    linhas = telas.carregar_linhas(conn, mapa)
    desperdicio = telas.marcar_desperdicio(linhas)
    ag = telas.agregar(linhas)
    arvore = telas.arvore_orcamento(conn, "censo.rodada1")
    eventos = {ln.rid: telas.eventos_da_compra(conn, ln.rid)
               for ln in linhas if ln.amount_minor is not None}
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM authz WHERE principal_ref IS NOT NULL")
        row = cur.fetchone()
        aprovacoes_d14 = int(row[0]) if row else 0

    dados: dict[str, Any] = {
        "gerado_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "linhas": [{
            "rid": ln.rid, "ts": ln.ts_utc.isoformat(timespec="seconds"),
            "recurso": ln.dominio or (ln.recurso_hash[:10] + "…"),
            "recurso_hash": ln.recurso_hash[:16],
            "metodo": ln.metodo, "status": ln.status_http,
            "agente": ln.agente or "—", "tarefa": ln.tarefa or "—",
            "rail": ln.rail, "network": ln.network,
            "testnet": ln.network == telas.TESTNET,
            "valor_minor": ln.amount_minor, "liq_minor": ln.settled_minor,
            "tx": ln.tx, "estado": ln.estado, "dedup": ln.dedup_n,
            "repetido": ln.repetido, "aprovador": ln.principal_ref,
            "corpo": (ln.body_sha256 or "")[:12], "bytes": ln.body_bytes,
        } for ln in reversed(linhas)],
        "eventos": eventos,
        "agregados": {
            "real_minor": ag.gasto_real_minor,
            "teste_minor": ag.gasto_teste_minor,
            "invoice_micro": ag.invoice_micro_usd,
            "compras": ag.compras, "entregas": ag.entregas,
            "pago_sem_entrega": ag.pago_sem_entrega,
            "por_dia": ag.por_dia, "por_rail": ag.por_rail,
            "aprovacoes_d14": aprovacoes_d14,
        },
        "desperdicio": desperdicio,
        "arvore": arvore,
        "fontes": fontes_tca(linhas),
        "teto_rodada_minor": 20_000_000,
    }

    html = (DIR / "telas_template.html").read_text(encoding="utf-8")
    html = html.replace("__DADOS__", json.dumps(dados, ensure_ascii=False))
    SAIDA.write_text(html, encoding="utf-8")

    # ---- GATE 8, conferido AQUI (não a olho): a página responde a pergunta? ----
    censo = [x for x in dados["linhas"] if x["agente"] == "mesa-censo"
             and x["valor_minor"] is not None]
    com_recibo = [x for x in censo if x["tx"]]
    assert censo and com_recibo, "blotter sem compras do censo com recibo on-chain"
    assert {x["agente"] for x in dados["linhas"]} >= {"mesa-censo", "agente-t6"}, \
        "dimensão POR AGENTE ausente"
    assert any(x["tarefa"] == "censo.rodada1" for x in dados["linhas"]), \
        "dimensão POR TAREFA ausente"
    assert dados["desperdicio"]["recursos_repetidos"], "desperdício não calculado"
    assert arvore["existe"] and arvore["total_minor"] == sum(
        f["gasto_minor"] for f in arvore["filhos"]), "árvore D-02 não soma"

    console.print(f"[bold]{len(dados['linhas'])}[/bold] linhas no blotter · "
                  f"{len(com_recibo)} compras do censo com recibo on-chain · "
                  f"desperdício repetido: US$ "
                  f"{dados['desperdicio']['gasto_repetido_total_minor'] / 1e6:.4f} "
                  f"(testnet) · aprovações D-14: {aprovacoes_d14}")
    console.print(f"gravado em {SAIDA}")
    console.print("[bold green]GATE 8 VERDE: o blotter responde por agente, por "
                  "tarefa, com recibo e com desperdício — com dado real[/bold green]")


if __name__ == "__main__":
    main()
