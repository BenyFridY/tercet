"""Fase 13 / item 1: o MCP do produto — o livro como ferramentas READ-ONLY (D-37).

Não confundir com mesa/mcp/{buyer,seller}.py (Fase 2): aqueles são o trilho de
COMPRA via MCP (um agente pagando tool calls com x402). Este módulo é o produto
virado para o agente: "quanto gastei?", "tem veredito aberto?", "esse pagador
merece confiança?" — respondido do banco na hora da chamada, pela MESMA sessão
read-only do app (D-35): o servidor não tem caminho de escrita nem que queira.

Uso num agente:  claude mcp add mesa -- uv run mesa-mcp
Transporte: stdio, local — o mesmo postulado do app (nada exposto na rede).
"""

from datetime import UTC, datetime
from typing import Any

from mcp.server import MCPServer

from mesa import decripto as dc
from mesa import ptax, reconcile, telas
from mesa.app import dados

INSTRUCOES = (
    "O livro da mesa como ferramentas de LEITURA. Regras de honestidade do programa: "
    "nenhum número é digitado (tudo derivado do banco no momento da chamada); testnet "
    "vem rotulada (eip155:84532 = Base Sepolia, dinheiro de mentira; eip155:8453 = "
    "Base mainnet); o livro nunca finge tempo real — use status_do_livro para saber "
    "até que bloco ele enxerga. Campos *_minor são micro-USD (6 casas); *_usd é a "
    "string decimal correspondente."
)

ESTADOS = ("liquidado", "pago-sem-entrega", "entregue-sem-cobrar", "cobranca-pendente",
           "expirou-sem-uso", "autorizado-pendente", "sem-pagamento",
           "fatura-conciliada", "fatura-pendente", "ingerido")


def _usd(minor: int) -> str:
    return f"{minor / 1_000_000:.6f}"


def _linha_json(ln: telas.Linha) -> dict[str, Any]:
    return {
        "rid": ln.rid,
        "ts_utc": ln.ts_utc.isoformat(),
        "dominio": ln.dominio or f"hash:{ln.recurso_hash[:12]}",
        "agente": ln.agente,
        "tarefa": ln.tarefa,
        "trilho": ln.rail,
        "rede": ln.network,
        "estado": ln.estado,
        "cotado_minor": ln.amount_minor,
        "liquidado_minor": ln.settled_minor,
        "liquidado_usd": _usd(ln.settled_minor),
        "entregue": ln.delivered,
        "tx": ln.tx,
        "repetido": ln.repetido,
    }


def criar_servidor() -> MCPServer:
    server = MCPServer(name="mesa-livro", version="0.1.0", instructions=INSTRUCOES)

    @server.tool(
        name="status_do_livro",
        description="Até onde o livro está atualizado: cursores do coletor (bloco por "
                    "rede) e a corrente de hash (seq/elos). Chame antes de confiar em "
                    "qualquer número — o livro nunca finge tempo real.",
    )
    def status_do_livro() -> dict[str, Any]:
        with dados.conectar_leitura() as conn:
            st = dados.status_livro(conn)
        st["nota"] = "atualizado até os blocos acima; rode o coletor para avançar"
        return st

    @server.tool(
        name="gasto",
        description="Resumo do gasto no livro inteiro: real (mainnet) vs testnet vs "
                    "invoice, por trilho, por agente, por dia, e o desperdício "
                    "(mesmo recurso, mesmo byte, comprado de novo).",
    )
    def gasto() -> dict[str, Any]:
        with dados.conectar_leitura() as conn:
            linhas = telas.carregar_linhas(conn, dados.mapa_dominios())
            desp = telas.marcar_desperdicio(linhas)
            st = dados.status_livro(conn)
        ag = telas.agregar(linhas)
        return {
            "gasto_real_minor": ag.gasto_real_minor,
            "gasto_real_usd": _usd(ag.gasto_real_minor),
            "gasto_testnet_minor": ag.gasto_teste_minor,
            "gasto_testnet_usd": _usd(ag.gasto_teste_minor),
            "invoice_micro_usd": ag.invoice_micro_usd,
            "compras": ag.compras,
            "entregas": ag.entregas,
            "pago_sem_entrega": ag.pago_sem_entrega,
            "por_trilho_minor": ag.por_rail,
            "por_agente": ag.por_agente,
            "por_dia_minor": ag.por_dia,
            "desperdicio": {
                "gasto_repetido_minor": desp["gasto_repetido_total_minor"],
                "recursos_repetidos": len(desp["recursos_repetidos"]),
            },
            "atualizado": st,
            "nota": "gasto_real = mainnet liquidado; testnet é dinheiro de mentira "
                    "e vem SEPARADO, nunca somado",
        }

    @server.tool(
        name="compras",
        description="As compras do livro, mais recentes primeiro, com filtros: "
                    f"estado (um de {', '.join(ESTADOS)}), rede (CAIP-2), trilho "
                    "(x402/invoice/mpp/ap2), agente, contem (texto no domínio) e "
                    "limite (1-100, padrão 20).",
    )
    def compras(estado: str | None = None, rede: str | None = None,
                trilho: str | None = None, agente: str | None = None,
                contem: str | None = None, limite: int = 20) -> dict[str, Any]:
        with dados.conectar_leitura() as conn:
            linhas = telas.carregar_linhas(conn, dados.mapa_dominios())
            telas.marcar_desperdicio(linhas)  # marca .repetido nas linhas
        sel = [ln for ln in reversed(linhas)
               if (estado is None or ln.estado == estado)
               and (rede is None or ln.network == rede)
               and (trilho is None or ln.rail == trilho)
               and (agente is None or (ln.agente or "").lower() == agente.lower())
               and (contem is None
                    or contem.lower() in (ln.dominio or ln.recurso_hash).lower())]
        lim = max(1, min(limite, 100))
        return {
            "n_no_livro": len(linhas),
            "n_apos_filtro": len(sel),
            "devolvidas": min(lim, len(sel)),
            "linhas": [_linha_json(ln) for ln in sel[:lim]],
            "nota_redes": "eip155:84532 = Base Sepolia (TESTNET); "
                          "eip155:8453 = Base mainnet (dinheiro real)",
        }

    @server.tool(
        name="compra",
        description="Uma compra específica (por rid, vindo de 'compras') com a cadeia "
                    "de eventos dela — a gaveta do blotter.",
    )
    def compra(rid: str) -> dict[str, Any]:
        with dados.conectar_leitura() as conn:
            linhas = telas.carregar_linhas(conn, dados.mapa_dominios())
            alvo = next((ln for ln in linhas if ln.rid == rid), None)
            if alvo is None:
                return {"erro": f"rid {rid} não está no livro"}
            eventos = telas.eventos_da_compra(conn, rid)
        return {"compra": _linha_json(alvo), "eventos": eventos}

    @server.tool(
        name="vereditos",
        description="A reconciliação de três pontas (pedido × autorização × chain) "
                    "feita AGORA: contagem por veredito nomeado, com a explicação de "
                    "cada um. Uma diferença nunca é um gap silencioso.",
    )
    def vereditos() -> dict[str, Any]:
        with dados.conectar_leitura() as conn:
            compras_, liqs = reconcile.carregar(conn)
        vs = reconcile.reconciliar(compras_, liqs)
        return {
            "n_compras": len(compras_),
            "n_liquidacoes": len(liqs),
            "vereditos": [{"veredito": v.value, "n": len(itens),
                           "explica": reconcile.EXPLICACAO[v]}
                          for v, itens in vs.items() if itens],
        }

    @server.tool(
        name="passaportes",
        description="Os passaportes de pagador (F10) emitidos neste checkout, "
                    "RE-VERIFICADOS offline nesta chamada: íntegro?, aceito pela "
                    "política?, motivos nomeados, métricas assinadas.",
    )
    def passaportes() -> dict[str, Any]:
        with dados.conectar_leitura() as conn:
            ctx = dados.contexto_risco(conn)
        return {
            "passaportes": ctx["passaportes"],
            "nota": "verificação nível 1 (offline) feita agora; nível 2 (chain) = "
                    "verificador/verificar_passaporte.py --rpc",
        }

    @server.tool(
        name="fiscal",
        description="A competência fiscal BR (DeCripto, F11): nº de saídas mainnet, "
                    "total em R$ pela PTAX persistida e o veredito do limiar de "
                    "obrigação PF. Sem ano/mes usa a competência atual (data de SP).",
    )
    def fiscal(ano: int | None = None, mes: int | None = None) -> dict[str, Any]:
        hoje_sp = datetime.now(UTC).astimezone(ptax.TZ_SP).date()
        a, m = ano or hoje_sp.year, mes or hoje_sp.month
        with dados.conectar_leitura() as conn:
            ops = dc.carregar_saidas_mainnet(conn, ano=a, mes=m, plataforma_por_tx={})
            cot = dados._cotacoes_somente_leitura(conn, ops) if ops else {}
        out: dict[str, Any] = {"competencia": f"{a:04d}-{m:02d}",
                               "n_ops_mainnet": len(ops),
                               "limiar_pf_reais": str(dc.LIMIAR_OBRIGACAO_REAIS)}
        if not ops:
            out["nota"] = "sem saídas mainnet na competência"
        elif cot is None:
            out["pendente"] = ("sem PTAX persistido para a competência — rodar "
                               "scripts/fase11/decripto_build.py (o MCP não busca "
                               "rede nem escreve)")
        else:
            _l0450, _l0980, total = dc.montar_competencia(ops, cot)
            devida, veredicto = dc.obrigacao(total)
            out.update({"total_reais": str(total), "obrigacao_devida": devida,
                        "veredicto": veredicto})
        return out

    return server


def main() -> None:
    criar_servidor().run("stdio")


if __name__ == "__main__":
    main()
