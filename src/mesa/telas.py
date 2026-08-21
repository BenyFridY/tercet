"""Fase 8: o dado das telas — cada número do blotter/TCA sai DAQUI, com regra nomeada.

Separação igual à do Laboratório: as REGRAS (estado da compra, desperdício) são
funções puras testáveis em memória; o SQL só carrega linhas. Nenhum UPDATE — as
telas LEEM o livro.

Regra de desperdício (docs/fase8.md): dentro do mesmo `resource_key_hash`, a
1ª entrega de cada `body_sha256` é conteúdo novo; as demais são REPETIDAS — pagou
de novo pelo mesmo byte. Conteúdo dinâmico legítimo tem hash diferente e NÃO conta.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psycopg

TESTNET = "eip155:84532"


@dataclass
class Linha:
    """Uma compra (ou tentativa) do livro, pronta para a tela."""

    rid: str
    ts_utc: datetime
    recurso_hash: str          # hex completo (a tela encurta)
    dominio: str | None        # só quando o mapa público conhece o hash
    metodo: str
    status_http: int | None
    delivered: bool
    body_sha256: str | None
    body_bytes: int | None
    rail: str
    agente: str | None
    tarefa: str | None
    trace_id: str
    amount_minor: int | None
    pay_to: str | None
    network: str | None
    valid_until: datetime | None
    principal_ref: str | None  # D-14: quem aprovou (quando houve aprovação)
    settled_minor: int
    tx: str | None
    estado: str = ""
    dedup_n: int = 1
    repetido: bool = False     # esta entrega trouxe byte JÁ visto do mesmo recurso


def derivar_estado(*, delivered: bool, tem_authz: bool, settled_minor: int,
                   valid_until: datetime | None, agora: datetime, rail: str) -> str:
    """O estado da compra DERIVADO do livro — nunca digitado na tela."""
    if rail == "invoice":
        return "fatura-conciliada" if settled_minor > 0 else "fatura-pendente"
    if rail in ("mpp", "ap2"):
        return "ingerido"
    if not tem_authz:
        return "sem-pagamento"
    if settled_minor > 0:
        return "liquidado" if delivered else "pago-sem-entrega"
    expirou = valid_until is not None and valid_until < agora
    if delivered:
        # cobrança ainda possível ≠ dívida morta: estados distintos (EIP-3009)
        return "entregue-sem-cobrar" if expirou else "cobranca-pendente"
    return "expirou-sem-uso" if expirou else "autorizado-pendente"


def marcar_desperdicio(linhas: list[Linha]) -> dict[str, Any]:
    """Marca repetições in-place e devolve o resumo do desperdício (regra do doc)."""
    por_recurso: dict[str, list[Linha]] = {}
    for ln in linhas:
        if ln.delivered:
            por_recurso.setdefault(ln.recurso_hash, []).append(ln)
    resumo: list[dict[str, Any]] = []
    for recurso, grupo in por_recurso.items():
        grupo.sort(key=lambda x: x.ts_utc)
        vistos: set[str] = set()
        repetidas = 0
        gasto_repetido = 0
        for ln in grupo:
            ln.dedup_n = len(grupo)
            corpo = ln.body_sha256 or ""
            if corpo in vistos:
                ln.repetido = True
                repetidas += 1
                gasto_repetido += ln.settled_minor
            else:
                vistos.add(corpo)
        if len(grupo) > 1:
            resumo.append({
                "recurso_hash": recurso, "dominio": grupo[0].dominio,
                "network": grupo[0].network, "compras": len(grupo),
                "conteudos_distintos": len(vistos), "repetidas": repetidas,
                "gasto_repetido_minor": gasto_repetido,
            })
    resumo.sort(key=lambda r: (-r["repetidas"], -r["compras"]))
    return {"recursos_repetidos": resumo,
            "gasto_repetido_total_minor": sum(r["gasto_repetido_minor"] for r in resumo)}


def carregar_linhas(conn: psycopg.Connection[Any],
                    mapa_dominios: dict[str, str]) -> list[Linha]:
    """Todas as compras do livro, com agente (span) e recibo (settlement) juntos."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT r.id, r.ts_utc, encode(r.resource_key_hash,'hex'), r.method,"
            "       r.status_http, r.delivered, encode(r.body_sha256,'hex'),"
            "       r.body_bytes, r.rail, sp.agent_ref, r.trace_id,"
            "       q.amount_minor, q.pay_to, q.asset_network_caip2,"
            "       a.id, a.valid_until_utc, a.principal_ref,"
            "       coalesce(sl.settled_amount_minor, 0), s.external_ref "
            "FROM request r "
            "JOIN span sp ON sp.span_id = r.span_id "
            "LEFT JOIN quote q ON q.request_id = r.id "
            "LEFT JOIN authz a ON a.quote_id = q.id "
            "LEFT JOIN settlement_leg sl ON sl.authorization_id = a.id "
            "LEFT JOIN settlement s ON s.id = sl.settlement_id "
            "ORDER BY r.ts_utc")
        brutas = cur.fetchall()
        # a tarefa = nome do span RAIZ da árvore daquela compra
        cur.execute("SELECT trace_id, name FROM span WHERE parent_span_id IS NULL")
        raiz_por_trace = dict(cur.fetchall())
    agora = datetime.now(UTC)
    linhas: list[Linha] = []
    for (rid, ts, rh, metodo, status, delivered, corpo, nbytes, rail, agente,
         trace, amount, pay_to, network, aid, valid_until, principal,
         settled, tx) in brutas:
        ln = Linha(
            rid=str(rid), ts_utc=ts, recurso_hash=str(rh),
            dominio=mapa_dominios.get(str(rh)), metodo=metodo,
            status_http=status, delivered=bool(delivered),
            body_sha256=str(corpo) if corpo else None, body_bytes=nbytes,
            rail=rail, agente=agente, tarefa=raiz_por_trace.get(trace),
            trace_id=trace, amount_minor=int(amount) if amount is not None else None,
            pay_to=pay_to, network=network, valid_until=valid_until,
            principal_ref=principal, settled_minor=int(settled),
            tx=tx)
        ln.estado = derivar_estado(
            delivered=ln.delivered, tem_authz=aid is not None,
            settled_minor=ln.settled_minor, valid_until=ln.valid_until,
            agora=agora, rail=rail)
        linhas.append(ln)
    return linhas


def arvore_orcamento(conn: psycopg.Connection[Any], nome_raiz: str) -> dict[str, Any]:
    """D-02 na tela: a árvore de UMA tarefa com o gasto LIQUIDADO por nó.

    v0: árvores de 2 níveis (raiz → compras). A invariante mostrada é a soma:
    total da raiz == soma dos filhos — a mesma dos testes da Fase 2.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sp.trace_id FROM span sp WHERE sp.name = %s"
            " AND sp.parent_span_id IS NULL ORDER BY sp.started_utc DESC LIMIT 1",
            (nome_raiz,))
        row = cur.fetchone()
        if row is None:
            return {"raiz": nome_raiz, "existe": False, "filhos": [], "total_minor": 0}
        trace = row[0]
        cur.execute(
            "SELECT sp.name, coalesce(sp.attributes->>'censo.dominio', sp.span_id),"
            "       coalesce(sum(sl.settled_amount_minor), 0) "
            "FROM span sp "
            "LEFT JOIN request r ON r.span_id = sp.span_id "
            "LEFT JOIN quote q ON q.request_id = r.id "
            "LEFT JOIN authz a ON a.quote_id = q.id "
            "LEFT JOIN settlement_leg sl ON sl.authorization_id = a.id "
            "WHERE sp.trace_id = %s AND sp.parent_span_id IS NOT NULL "
            "GROUP BY sp.span_id, sp.name, sp.attributes ORDER BY min(sp.started_utc)",
            (trace,))
        filhos = [{"span": n, "rotulo": rot, "gasto_minor": int(g)}
                  for n, rot, g in cur.fetchall()]
    return {"raiz": nome_raiz, "existe": True, "trace_id": trace, "filhos": filhos,
            "total_minor": sum(f["gasto_minor"] for f in filhos)}


def eventos_da_compra(conn: psycopg.Connection[Any], rid: str) -> list[dict[str, Any]]:
    """A cadeia de eventos de UMA compra (o drawer): authz_event + settlement_event."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ae.ts_utc, ae.kind, 'authz' FROM authz_event ae"
            " JOIN authz a ON a.id = ae.authorization_id"
            " JOIN quote q ON q.id = a.quote_id WHERE q.request_id = %s::uuid"
            " UNION ALL "
            "SELECT se.ts_utc, se.kind, 'settlement' FROM settlement_event se"
            " JOIN settlement_leg sl ON sl.settlement_id = se.settlement_id"
            " JOIN authz a ON a.id = sl.authorization_id"
            " JOIN quote q ON q.id = a.quote_id WHERE q.request_id = %s::uuid"
            " ORDER BY 1",
            (rid, rid))
        return [{"ts": ts.isoformat(), "kind": k, "de": origem}
                for ts, k, origem in cur.fetchall()]


@dataclass
class Agregados:
    """Os números do topo das telas — calculados das linhas, rotulados por rede."""

    gasto_real_minor: int = 0          # mainnet liquidado (dinheiro de verdade)
    gasto_teste_minor: int = 0         # testnet liquidado (dinheiro de mentira)
    invoice_micro_usd: int = 0         # trilho fatura (micro-USD)
    compras: int = 0
    entregas: int = 0
    pago_sem_entrega: int = 0
    por_rail: dict[str, int] = field(default_factory=dict)
    por_agente: dict[str, dict[str, int]] = field(default_factory=dict)
    por_dia: dict[str, int] = field(default_factory=dict)


def agregar(linhas: list[Linha]) -> Agregados:
    ag = Agregados()
    for ln in linhas:
        eh_teste = ln.network == TESTNET
        if ln.rail == "invoice":
            ag.invoice_micro_usd += ln.settled_minor
        elif eh_teste:
            ag.gasto_teste_minor += ln.settled_minor
        else:
            ag.gasto_real_minor += ln.settled_minor
        if ln.amount_minor is not None:
            ag.compras += 1
        if ln.delivered:
            ag.entregas += 1
        if ln.estado == "pago-sem-entrega":
            ag.pago_sem_entrega += 1
        ag.por_rail[ln.rail] = ag.por_rail.get(ln.rail, 0) + ln.settled_minor
        ag_ag = ag.por_agente.setdefault(ln.agente or "—", {"compras": 0, "gasto": 0})
        if ln.amount_minor is not None:
            ag_ag["compras"] += 1
        ag_ag["gasto"] += ln.settled_minor if not eh_teste or ln.rail == "invoice" else 0
        dia = ln.ts_utc.date().isoformat()
        ag.por_dia[dia] = ag.por_dia.get(dia, 0) + ln.settled_minor
    return ag
