"""Fase 7 — GATE 7: as 5 políticas contra os 15 pontos REAIS do censo. Grátis.

Carrega do livro cada decisão da rodada 1 (valor que foi assinado, na ordem real)
e o desfecho (entregou? liquidou quanto?), roda as políticas do doc, e produz o
relatório com IC honesto + o(s) resultado(s) NEGATIVO(s) documentado(s).

Uso: uv run python scripts/fase7/laboratorio_run.py
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from mesa import db, laboratorio
from mesa.config import Settings

console = Console()
SAIDA = Path(__file__).parent / "laboratorio_resultado.json"


def carregar_do_livro() -> tuple[list[laboratorio.PontoDeDecisao],
                                 dict[int, laboratorio.Desfecho]]:
    """Os 15 pontos da rodada 1 do censo, na ordem real, + desfechos."""
    s = Settings()
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT r.ts_utc, encode(r.resource_key_hash,'hex'), "
            "       a.authorized_max_minor, r.delivered, "
            "       coalesce(sl.settled_amount_minor, 0) "
            "FROM authz a "
            "JOIN quote q ON q.id = a.quote_id "
            "JOIN request r ON r.id = q.request_id "
            "LEFT JOIN settlement_leg sl ON sl.authorization_id = a.id "
            "WHERE a.rail='x402' AND lower(a.payer_ref) = lower(%s) "
            "ORDER BY r.ts_utc",
            (s.census_address,),
        )
        linhas = cur.fetchall()
    pontos: list[laboratorio.PontoDeDecisao] = []
    desfechos: dict[int, laboratorio.Desfecho] = {}
    for ordem, (_ts, h, valor, entregue, liquidado) in enumerate(linhas):
        # vínculo na hora da decisão: N4 para todos (medido pós-rodada: 0/15 — rótulo)
        pontos.append(laboratorio.PontoDeDecisao(ordem, str(h)[:16], int(valor), 4))
        desfechos[ordem] = laboratorio.Desfecho(bool(entregue), int(liquidado))
    return pontos, desfechos


def main() -> None:
    pontos, desfechos = carregar_do_livro()
    assert len(pontos) == 15, f"esperava as 15 compras do censo, vieram {len(pontos)}"
    console.print(f"{len(pontos)} decisões reais carregadas do livro (ordem da rodada)")

    resultados = [laboratorio.backtest(pontos, desfechos, nome, pol)
                  for nome, pol in laboratorio.politicas_da_rodada1().items()]

    t = Table(title="Laboratório — rodada 1 do censo, 5 políticas (point-in-time)")
    t.add_column("política")
    t.add_column("compras", justify="right")
    t.add_column("gasto US$", justify="right")
    t.add_column("entregas", justify="right")
    t.add_column("taxa [IC 95%]")
    t.add_column("US$/entrega", justify="right")
    t.add_column("perdidas", justify="right")
    for r in resultados:
        lo, hi = r.ic_wilson_95
        taxa = (f"{r.taxa_entrega:.0%} [{lo:.0%}–{hi:.0%}]"
                if r.taxa_entrega is not None else "— (comprou nada)")
        cpe = (f"{r.custo_por_entrega_minor / 1e6:.4f}"
               if r.custo_por_entrega_minor is not None else "—")
        t.add_row(r.politica, str(r.n_compras),
                  f"{r.gasto_liquidado_minor / 1e6:.4f}", str(r.entregas),
                  taxa, cpe, str(r.entregas_perdidas))
    console.print(t)

    # os resultados NEGATIVOS que o gate exige — detectados do dado, escritos claro
    negativos: list[str] = []
    por_nome = {r.politica: r for r in resultados}
    vo = por_nome["verified-only"]
    if vo.n_compras == 0:
        negativos.append(
            "verified-only: a política que PARECE a mais segura compra ZERO hoje "
            "(0/15 vendedores publicam vínculo) — segurança que custa 100% das "
            f"{vo.entregas_perdidas} entregas disponíveis. Ela só fica viável quando "
            "a extensão payTo-binding tiver adoção (a proposta está em notes/).")
    pr = por_nome["premium"]
    base = por_nome["real-rodada1"]
    if (pr.taxa_entrega is not None and base.taxa_entrega is not None
            and pr.taxa_entrega < base.taxa_entrega):
        lo, hi = pr.ic_wilson_95
        negativos.append(
            f"premium ('caro = confiável'): taxa de entrega {pr.taxa_entrega:.0%} "
            f"contra {base.taxa_entrega:.0%} do baseline — a compra mais cara da "
            f"rodada (US$ 0,50) foi exatamente uma das que falhou. Com n={pr.n_compras} "
            f"o IC é [{lo:.0%}–{hi:.0%}]: a leitura honesta é 'sem evidência a favor, "
            "anedota contra'.")
    assert negativos, "gate exige ≥1 resultado negativo documentado"
    console.print("\n[bold]Resultados NEGATIVOS documentados (o gate exige):[/bold]")
    for n in negativos:
        console.print(f"  • {n}")
    console.print("\n[dim]Rótulos e premissas (D-12):[/dim]")
    for rot in laboratorio.ROTULOS:
        console.print(f"  [dim]- {rot}[/dim]")

    SAIDA.write_text(json.dumps({
        "gerado_utc": datetime.now(UTC).isoformat(),
        "n_pontos": len(pontos),
        "rotulos_e_premissas": laboratorio.ROTULOS,
        "ic_metodo": "Wilson 95%",
        "resultados_negativos": negativos,
        "politicas": [{
            "politica": r.politica, "n_compras": r.n_compras,
            "gasto_autorizado_minor": r.gasto_autorizado_minor,
            "gasto_liquidado_minor": r.gasto_liquidado_minor,
            "entregas": r.entregas, "compras_que_falharam": r.compras_que_falharam,
            "taxa_entrega": r.taxa_entrega, "ic_wilson_95": list(r.ic_wilson_95),
            "custo_por_entrega_minor": r.custo_por_entrega_minor,
            "entregas_perdidas": r.entregas_perdidas, "detalhe": r.detalhe,
        } for r in resultados],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\ngravado em {SAIDA}")
    console.print("[bold green]GATE 7 VERDE: políticas avaliadas point-in-time, IC "
                  "honesto, resultado negativo documentado[/bold green]")


if __name__ == "__main__":
    main()
