"""Fase 11 — GATE 11: a DeCripto da competência, 100% gerada do livro, validada.

O que este script faz, com asserts que quebram se um número divergir:
1. Carrega as compras LIQUIDADAS na Base MAINNET cuja data de SP cai na competência
   (testnet excluída pela query — não por disciplina).
2. Converte cada uma para reais pelo PTAX venda da data de SP (point-in-time,
   persistido em fx_ptax; dia sem cotação usa a última anterior e o resumo DIZ isso).
3. Escreve o arquivo 0450 (uma linha por compra) e o arquivo-demonstração 0980
   (a alternativa do art. 9º § único: hash + explorador).
4. Valida os dois contra o leiaute codificado do manual v1.01 — e prova que o
   validador MORDE: adultera 1 campo em memória e exige o VERMELHO.
5. Confere os totais contra uma query INDEPENDENTE (timezone convertido pelo
   Postgres, não pelo Python) e imprime a obrigação com honestidade (limiar R$ 35 mil).

Custo: zero. Uso: uv run python scripts/fase11/decripto_build.py [AAAA-MM]
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from mesa import db
from mesa import decripto as dc

console = Console()
RAIZ = Path(__file__).resolve().parents[2]
CENSO = RAIZ / "scripts" / "fase3" / "censo_fechamento.json"


def conferencia_independente(conn: Any, ano: int, mes: int) -> tuple[int, int]:
    """A MESMA competência, recomputada pelo Postgres (AT TIME ZONE), não pelo Python."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), coalesce(sum(l.settled_amount_minor), 0)
            FROM settlement_leg l JOIN settlement s ON s.id = l.settlement_id
            WHERE s.rail = 'x402' AND s.network_caip2 = 'eip155:8453'
              AND to_char(s.block_ts_utc AT TIME ZONE 'America/Sao_Paulo',
                          'YYYY-MM') = %s
            """,
            (f"{ano:04d}-{mes:02d}",),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0]), int(row[1])


def main() -> None:
    competencia = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    conn = db.connect()
    db.apply_migrations(conn)

    censo = json.loads(CENSO.read_text(encoding="utf-8"))
    plataforma_por_tx = {str(f["tx"]).lower(): str(f["dominio"])
                         for f in censo["por_fonte"] if f.get("tx")}

    ops = dc.carregar_saidas_mainnet(conn, ano=ano, mes=mes,
                                     plataforma_por_tx=plataforma_por_tx)
    if not ops:
        raise SystemExit(f"nenhuma compra liquidada na mainnet em {competencia} — "
                         "nada a declarar, nada a demonstrar")

    cotacoes = dc.cotacoes_para(conn, ops)
    l0450, l0980, total = dc.montar_competencia(ops, cotacoes)
    texto_0450 = dc.render(l0450)
    texto_0980 = dc.render(l0980)

    # 4a. os arquivos passam no leiaute…
    falhas = dc.validar(texto_0450) + dc.validar(texto_0980)
    assert falhas == [], f"arquivo gerado fora do leiaute?! {falhas}"
    # 4b. …e o validador MORDE: 1 campo adulterado tem que dar VERMELHO
    adulterado = texto_0450.replace("|IV|", "|X|", 1)
    assert dc.validar(adulterado), "validador não pegou código adulterado — gate FALHOU"
    adulterado2 = texto_0450.replace("\r\n", "|extra\r\n", 1)
    assert dc.validar(adulterado2), "validador não pegou campo extra — gate FALHOU"

    # 5. conferência independente (Postgres converte o fuso, não o Python)
    n_livro, minor_livro = conferencia_independente(conn, ano, mes)
    assert n_livro == len(l0450), f"livro diz {n_livro} operações; arquivo tem {len(l0450)}"
    assert minor_livro == sum(op.amount_minor for op in ops), "soma minor divergiu do livro"

    devida, veredicto = dc.obrigacao(total)

    saida = RAIZ / "fiscal" / "decripto" / competencia
    saida.mkdir(parents=True, exist_ok=True)
    # newline="" preserva o CRLF do leiaute (§2.2) — sem tradução do Windows/Python
    (saida / "decripto-0450.txt").write_text(texto_0450, encoding="utf-8", newline="")
    (saida / "decripto-0980-alternativa.txt").write_text(texto_0980, encoding="utf-8",
                                                         newline="")

    linhas_ptax = "\n".join(
        f"- {d}: PTAX venda de {usada} = R$ {venda}" + ("" if usada == d else
        "  *(dia sem cotação — usada a última anterior, point-in-time)*")
        for d, (usada, venda) in sorted(cotacoes.items()))
    gerado = datetime.now(UTC).isoformat(timespec="seconds")
    resumo = f"""# DeCripto — competência {competencia} (SIMULAÇÃO ROTULADA)

*Gerado em {gerado} por `scripts/fase11/decripto_build.py` — 100% derivado do livro;
nenhum número digitado à mão. Leiaute: Manual v1.01 (ADE Copes nº 02/2025,
IN RFB nº 2.291/2025), capítulo 6 — PF/PJ sem prestador de serviço (autocustódia).*

## O veredito do motor

**{veredicto}**

## Os números (conferidos por query independente — fuso convertido pelo Postgres)

- Operações liquidadas na Base mainnet na competência: **{len(l0450)}**
- Total declarável: **R$ {total}** ({minor_livro} unidades mínimas de USDC)
- Registro usado: **0450** (operação IV, TipoTransferenciaSaida 4 —
  "aquisição de bens ou serviços", CARF604)
- Alternativa do art. 9º § único demonstrada: **{len(l0980)}** linhas 0980
  (hash da transação + {dc.BASESCAN})

## PTAX aplicado (fx_ptax, point-in-time)

{linhas_ptax}

## Decisões de classificação declaradas (revisáveis com contador — fase11.md)

- USDC valorado a **1 USD × PTAX venda** (aproximação declarada;
  `AvaliacaoAlternativaValor = 4`, estimativa razoável). Num depeg este valor erra.
- Contraparte como **TipoNI 8 (Plataforma Descentralizada)** + domínio do vendedor —
  é o que o livro sabe; identidade verificada (escada N1–N4) migra o campo sozinha.
- **Taxas vazias**: no scheme `exact` o facilitator paga o gas — o pagador não incorre.
- **Testnet excluída por construção** (filtro de rede na query).

## O que este arquivo NÃO é

Não é uma entrega devida ({"acima" if devida else "abaixo"} do limiar de
R$ {dc.LIMIAR_OBRIGACAO_REAIS}/mês da IN RFB 2.291/2025) e não foi transmitido ao
e-CAC. É o motor recibo→obrigação demonstrado sobre operações REAIS com recibo
on-chain — pronto para o gatilho.
"""
    (saida / "resumo.md").write_text(resumo, encoding="utf-8")

    console.print(f"[bold]{len(l0450)}[/bold] operações → R$ [bold]{total}[/bold] · "
                  f"{'OBRIGADA' if devida else 'abaixo do limiar (demonstração)'}")
    console.print(f"arquivos em {saida}")
    console.print("[green]GATE 11: leiaute validado, adulteração detectada, "
                  "números conferidos contra o livro[/green]")


if __name__ == "__main__":
    main()
