"""Os dados das cinco telas — cada função devolve o contexto de UMA tela.

Regras (D-35, fase12.md): conexão SOMENTE leitura (escrita falha na sessão);
nenhum número digitado; livro VAZIO é estado válido (a tela diz "sem dados",
nunca 500); testnet/sintético rotulados; inferência marcada.
"""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

from mesa import decripto as dc
from mesa import laboratorio, ptax, reconcile, telas
from mesa import passaporte as pp
from mesa.config import Settings

# raiz do repo quando rodando do checkout (artefatos públicos: censo, passaportes);
# num install de PyPI esses caminhos não existem e as seções dizem isso.
_RAIZ = Path(__file__).resolve().parents[3]
_CANDIDATOS = _RAIZ / "scripts" / "fase3" / "candidatos.json"
_PASSAPORTES = _RAIZ / "scripts" / "fase10" / "saida"
_FISCAL = _RAIZ / "fiscal" / "decripto"
_CONTABIL = _RAIZ / "contabil"
_CARF = _RAIZ / "fiscal" / "carf"


def _subdirs(base: Path) -> list[str]:
    return [p.name for p in sorted(base.iterdir()) if p.is_dir()] if base.exists() else []

# canônicos conhecidos (D-11: o livro só tem hash; a tela traduz com mapa PÚBLICO)
CANONICOS_FIXOS = {
    "GET http://127.0.0.1:8402/brinquedo": "brinquedo (vendedor local)",
    "http://127.0.0.1:8402/brinquedo": "brinquedo (vendedor local)",
    "GET http://127.0.0.1:8402/free-ride": "free-ride (caos fase 1)",
    "mcp://127.0.0.1:8403/tool/consultar": "mcp · consultar (vendedor local)",
    "llm:anthropic:claude-sonnet-5": "anthropic · claude-sonnet-5",
    "GET http://127.0.0.1:8410/lote": "lote (vendedor c/ passaporte, fase 10)",
    "GET http://127.0.0.1:8411/recarga": "recarga (fase 10)",
}


def conectar_leitura() -> psycopg.Connection[Any]:
    """A conexão do APP: a sessão inteira é read-only — escrever FALHA (D-35)."""
    return psycopg.connect(
        Settings().database_url, connect_timeout=5,
        options="-c default_transaction_read_only=on",
    )


def mapa_dominios() -> dict[str, str]:
    mapa = {hashlib.sha256(c.encode()).hexdigest(): rotulo
            for c, rotulo in CANONICOS_FIXOS.items()}
    if _CANDIDATOS.exists():
        for c in json.loads(_CANDIDATOS.read_text(encoding="utf-8"))["candidatos"]:
            mapa[hashlib.sha256(c["url"].encode()).hexdigest()] = c["dominio"]
    return mapa


def status_livro(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    """O rodapé de honestidade: até onde o livro está atualizado (nunca 'tempo real')."""
    with conn.cursor() as cur:
        cur.execute("SELECT name, last_block, updated_utc FROM collector_cursor"
                    " ORDER BY name")
        cursores = [{"nome": n, "bloco": int(b), "em": u.isoformat()}
                    for n, b, u in cur.fetchall()]
        cur.execute("SELECT coalesce(max(seq),0), count(*) FROM ledger_hash")
        row = cur.fetchone()
        assert row is not None
        seq, elos = int(row[0]), int(row[1])
    return {"cursores": cursores, "corrente_seq": seq, "corrente_elos": elos}


# ------------------------------------------------------------------ 01 · blotter

def contexto_blotter(conn: psycopg.Connection[Any],
                     dias: int | None = None) -> dict[str, Any]:
    linhas = telas.carregar_linhas(conn, mapa_dominios())
    if dias is not None:  # janela de período: cards + gráfico + tabela juntos
        corte = datetime.now(UTC) - timedelta(days=dias)
        linhas = [ln for ln in linhas if ln.ts_utc >= corte]
    desperdicio = telas.marcar_desperdicio(linhas)
    ag = telas.agregar(linhas)
    problemas = [ln for ln in linhas
                 if ln.estado in ("pago-sem-entrega", "entregue-sem-cobrar")]
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FILTER (WHERE result='verified'), count(*)"
                    " FROM verification WHERE subject_type='pay_to'")
        row = cur.fetchone()
        assert row is not None
        verificados, total_verif = int(row[0]), int(row[1])
    serie = sorted(ag.por_dia.items())
    # a série REAL separada da total: a linha verde é dinheiro de verdade;
    # a apagada inclui testnet (rotulada) — nunca somadas numa curva só
    por_dia_real: dict[str, int] = {}
    for ln in linhas:
        if ln.network != "eip155:84532" and ln.settled_minor:
            d = ln.ts_utc.date().isoformat()
            por_dia_real[d] = por_dia_real.get(d, 0) + ln.settled_minor
    return {
        "linhas": list(reversed(linhas)),  # mais recente primeiro, como no design
        "ag": ag,
        "desperdicio": desperdicio,
        "problemas_n": len(problemas),
        "problemas_minor": sum(ln.settled_minor for ln in problemas),
        "verificacao": {"verified": verificados, "total": total_verif},
        "serie_diaria": serie,
        "svg_diaria": _svg_linha([v for _, v in serie]),
        "svg_diaria_real": _svg_linha(
            [por_dia_real.get(d, 0) for d, _ in serie],
            topo=max((v for _, v in serie), default=1)),
        "dias": dias,
    }


# ------------------------------------------------------------------ 02 · tca

def contexto_tca(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    linhas = telas.carregar_linhas(conn, mapa_dominios())
    desperdicio = telas.marcar_desperdicio(linhas)

    fontes: dict[str, dict[str, Any]] = {}
    for ln in linhas:
        if ln.amount_minor is None or ln.estado == "sem-pagamento":
            continue
        chave = ln.dominio or f"não mapeado · {ln.recurso_hash[:12]}"
        g = fontes.setdefault(chave, {"fonte": chave, "network": ln.network,
                                      "rail": ln.rail, "compras": 0,
                                      "gasto_minor": 0, "entregas": 0,
                                      "valores": []})
        g["compras"] += 1
        g["gasto_minor"] += ln.settled_minor
        g["entregas"] += int(ln.delivered)
        if ln.settled_minor:
            g["valores"].append(ln.settled_minor)
    for g in fontes.values():
        g["custo_por_entrega_minor"] = (
            round(g["gasto_minor"] / g["entregas"]) if g["entregas"] else None)
        vs = sorted(g.pop("valores"))
        g["preco_min"] = vs[0] if vs else None
        g["preco_max"] = vs[-1] if vs else None
        g["preco_mediana"] = vs[len(vs) // 2] if vs else None

    # dedup entre agentes: o MESMO recurso comprado por ≥2 agentes distintos
    por_recurso: dict[str, set[str]] = {}
    gasto_recurso: dict[str, int] = {}
    for ln in linhas:
        if ln.amount_minor is None:
            continue
        por_recurso.setdefault(ln.recurso_hash, set()).add(ln.agente or "—")
        gasto_recurso[ln.recurso_hash] = (
            gasto_recurso.get(ln.recurso_hash, 0) + ln.settled_minor)
    mapa = mapa_dominios()
    dedup: list[dict[str, Any]] = [
        {"recurso": mapa.get(h) or f"não mapeado · {h[:12]}", "agentes": sorted(ags),
         "gasto_minor": gasto_recurso[h]}
        for h, ags in por_recurso.items() if len(ags) >= 2]
    dedup.sort(key=lambda d: -d["gasto_minor"])

    # dinheiro real primeiro (testnet no fim) — misturar rede na ordenação era o
    # erro clássico: a recarga de mentira de $0,90 dominava o topo da tabela
    return {"fontes": sorted(fontes.values(),
                             key=lambda g: (g["network"] == "eip155:84532",
                                            -g["gasto_minor"])),
            "desperdicio": desperdicio, "dedup": dedup,
            "n_linhas": sum(1 for ln in linhas if ln.amount_minor is not None)}


# ------------------------------------------------------------------ 03 · risco

def contexto_risco(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    with conn.cursor() as cur:
        # as tarefas (spans raiz) com gasto, para a árvore D-02
        cur.execute("""
            SELECT sp.name, coalesce(sum(sl.settled_amount_minor), 0) AS gasto
            FROM span sp
            JOIN span f ON f.trace_id = sp.trace_id AND f.parent_span_id IS NOT NULL
            LEFT JOIN request r ON r.span_id = f.span_id
            LEFT JOIN quote q ON q.request_id = r.id
            LEFT JOIN authz a ON a.quote_id = q.id
            LEFT JOIN settlement_leg sl ON sl.authorization_id = a.id
            WHERE sp.parent_span_id IS NULL
            GROUP BY sp.name ORDER BY gasto DESC LIMIT 6
        """)
        raizes = [str(r[0]) for r in cur.fetchall()]
        # aprovações vinculadas (D-14)
        cur.execute("""
            SELECT a.principal_ref, encode(a.scope_hash,'hex'), q.pay_to,
                   q.amount_minor, a.valid_until_utc
            FROM authz a JOIN quote q ON q.id = a.quote_id
            WHERE a.principal_ref IS NOT NULL ORDER BY a.valid_until_utc DESC
        """)
        aprovacoes = [{"quem": q_, "escopo": e, "pay_to": p, "amount_minor": int(m),
                       "valid_until": (v.isoformat() if v else None)}
                      for q_, e, p, m, v in cur.fetchall()]
    arvores = [telas.arvore_orcamento(conn, nome) for nome in raizes]

    # passaportes (F10): artefatos REAIS emitidos, verificados offline aqui e agora
    passaportes: list[dict[str, Any]] = []
    if _PASSAPORTES.exists():
        for arq in sorted(_PASSAPORTES.glob("passaporte-*.json")):
            art = json.loads(arq.read_text(encoding="utf-8"))
            falhas = pp.verificar_offline(art)
            aceito, motivos = (pp.avaliar_politica(art, pp.Politica(),
                                                   datetime.now(UTC))
                               if not falhas else (False, ["documento-invalido"]))
            m = art["payload"]["metricas"]
            passaportes.append({
                "nome": arq.stem.removeprefix("passaporte-"),
                "sujeito": art["payload"]["sujeito"]["payer_ref"],
                "rede": art["payload"]["sujeito"]["rede"],
                "emitido": art["payload"]["emitido_utc"],
                "metricas": m, "integro": not falhas,
                "aceito": aceito, "motivos": motivos,
            })
    return {"arvores": arvores, "aprovacoes": aprovacoes, "passaportes": passaportes}


# ------------------------------------------------------------- 04 · laboratório

def contexto_laboratorio(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    s = Settings()
    pontos: list[laboratorio.PontoDeDecisao] = []
    desfechos: dict[int, laboratorio.Desfecho] = {}
    if s.census_address:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.ts_utc, encode(r.resource_key_hash,'hex'),"
                "       a.authorized_max_minor, r.delivered,"
                "       coalesce(sl.settled_amount_minor, 0) "
                "FROM authz a JOIN quote q ON q.id = a.quote_id "
                "JOIN request r ON r.id = q.request_id "
                "LEFT JOIN settlement_leg sl ON sl.authorization_id = a.id "
                "WHERE a.rail='x402' AND lower(a.payer_ref) = lower(%s) "
                # só MAINNET: a carteira do censo também comprou na testnet (fase 10)
                # e misturar rede no backtest seria o erro clássico
                "AND q.asset_network_caip2 = 'eip155:8453' "
                "ORDER BY r.ts_utc",
                (s.census_address,))
            for ordem, (_ts, h, valor, entregue, liq) in enumerate(cur.fetchall()):
                pontos.append(laboratorio.PontoDeDecisao(ordem, str(h)[:16],
                                                         int(valor), 4))
                desfechos[ordem] = laboratorio.Desfecho(bool(entregue), int(liq))
    resultados = ([laboratorio.backtest(pontos, desfechos, nome, pol)
                   for nome, pol in laboratorio.politicas_da_rodada1().items()]
                  if pontos else [])
    return {"n_pontos": len(pontos), "resultados": resultados,
            "rotulos": list(laboratorio.ROTULOS)}


# ------------------------------------------------------------------ 05 · livros

def _cotacoes_somente_leitura(conn: psycopg.Connection[Any],
                              ops: list[dc.OperacaoSaida]
                              ) -> dict[date, tuple[date, Decimal]] | None:
    """PTAX SÓ do fx_ptax já persistido (o app não busca rede nem escreve).
    None = falta cotação → a tela manda rodar o build da fase 11."""
    out: dict[date, tuple[date, Decimal]] = {}
    for d in sorted({ptax.data_sp(op.ts_utc) for op in ops}):
        achou = None
        for k in range(ptax.DIAS_MAX_RETROCESSO + 1):
            dk = d - timedelta(days=k)
            venda = ptax._ler(conn, dk)
            if venda is not None:
                achou = (dk, venda)
                break
        if achou is None:
            return None
        out[d] = achou
    return out


def contexto_livros(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    compras, liquidacoes = reconcile.carregar(conn)
    vereditos = reconcile.reconciliar(compras, liquidacoes)
    contagens = [{"veredito": str(v), "n": len(itens),
                  "explica": reconcile.EXPLICACAO[v]}
                 for v, itens in vereditos.items() if itens]

    with conn.cursor() as cur:
        cur.execute("SELECT period_date, first_seq, last_seq,"
                    " encode(merkle_root,'hex'), closed_utc FROM period_close"
                    " ORDER BY period_date")
        periodos = [{"data": str(d), "de": int(a), "ate": int(b), "raiz": r,
                     "fechado": c.isoformat()} for d, a, b, r, c in cur.fetchall()]
        cur.execute("SELECT period_date, kind, length(proof), ts_utc"
                    " FROM period_stamp ORDER BY ts_utc")
        carimbos = [{"periodo": str(d), "tipo": k, "bytes": int(n),
                     "em": t.isoformat()} for d, k, n, t in cur.fetchall()]
        # fatura consolidada por contraparte (liquidado, por pay_to)
        cur.execute("""
            SELECT q.pay_to, q.asset_network_caip2, count(*),
                   sum(sl.settled_amount_minor)
            FROM settlement_leg sl JOIN authz a ON a.id = sl.authorization_id
            JOIN quote q ON q.id = a.quote_id
            GROUP BY q.pay_to, q.asset_network_caip2 ORDER BY 4 DESC
        """)
        fatura = [{"pay_to": p, "network": n, "compras": int(c),
                   "total_minor": int(t)} for p, n, c, t in cur.fetchall()]
        cur.execute("SELECT count(*), coalesce(sum(total_amount_minor),0)"
                    " FROM settlement WHERE rail='invoice'")
        row = cur.fetchone()
        assert row is not None
        invoice = {"n": int(row[0]), "micro_usd": int(row[1])}

    # fiscal (F11): recomputado ao vivo, com PTAX já persistido — sem rede, sem escrita
    hoje_sp = datetime.now(UTC).astimezone(ptax.TZ_SP).date()
    ops = dc.carregar_saidas_mainnet(conn, ano=hoje_sp.year, mes=hoje_sp.month,
                                     plataforma_por_tx={})
    fiscal: dict[str, Any] = {"competencia": f"{hoje_sp.year:04d}-{hoje_sp.month:02d}",
                              "n_ops": len(ops)}
    cotacoes = _cotacoes_somente_leitura(conn, ops) if ops else {}
    if ops and cotacoes is None:
        fiscal["pendente"] = ("sem PTAX persistido para a competência — rodar "
                              "scripts/fase11/decripto_build.py")
    elif ops:
        assert cotacoes is not None
        _l0450, _l0980, total = dc.montar_competencia(ops, cotacoes)
        devida, veredicto = dc.obrigacao(total)
        fiscal.update({"total_reais": str(total), "devida": devida,
                       "veredicto": veredicto})
    return {"vereditos": contagens, "n_compras": len(compras),
            "n_liquidacoes": len(liquidacoes), "periodos": periodos,
            "carimbos": carimbos, "fatura": fatura, "invoice": invoice,
            "fiscal": fiscal, "competencias_geradas": _subdirs(_FISCAL),
            "contabil_gerados": _subdirs(_CONTABIL),
            "carf_gerados": _subdirs(_CARF)}


# ------------------------------------------------------------------ helpers

def _svg_linha(valores: list[int], largura: int = 1000, altura: int = 80,
               topo: int | None = None) -> str:
    """Polyline SVG da série (o gráfico do design, gerado no servidor).
    `topo` fixa a escala — duas séries no MESMO gráfico têm de dividir o eixo."""
    if not valores:
        return ""
    topo = max(topo if topo is not None else max(valores), 1)
    n = len(valores)
    pts = []
    for i, v in enumerate(valores):
        x = (largura * i / (n - 1)) if n > 1 else largura / 2
        y = altura - 6 - (altura - 16) * v / topo
        pts.append(f"{x:.1f} {y:.1f}")
    return "M" + " L".join(pts)
