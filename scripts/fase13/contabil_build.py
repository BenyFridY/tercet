"""GATE 13b: o export contábil da competência, gerado do livro real.

O que este script prova:
1. os 4 CSVs saem do livro (conexão READ-ONLY — gerar arquivo não escreve no banco);
2. partidas dobradas: débito == crédito, e o detalhe (6 casas) soma no exato;
3. conferência INDEPENDENTE: o total bate com SQL próprio recomputando o fuso de
   São Paulo dentro do Postgres (a mesma prova da Fase 11);
4. adulteração → validar acusa nomeando o campo (obrigatório falhar).

Uso: uv run python scripts/fase13/contabil_build.py [ano] [mes]
"""

import dataclasses
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from mesa import contabil, ptax
from mesa.app import dados

RAIZ = Path(__file__).resolve().parents[2]


def main() -> None:
    hoje_sp = datetime.now(UTC).astimezone(ptax.TZ_SP).date()
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else hoje_sp.year
    mes = int(sys.argv[2]) if len(sys.argv) > 2 else hoje_sp.month

    with dados.conectar_leitura() as conn:
        compras = contabil.carregar_compras(conn, dados.mapa_dominios(), ano, mes)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*), coalesce(sum(sl.settled_amount_minor), 0)
                FROM settlement_leg sl JOIN authz a ON a.id = sl.authorization_id
                JOIN quote q ON q.id = a.quote_id
                JOIN request r ON r.id = q.request_id
                WHERE q.asset_network_caip2 = 'eip155:8453' AND a.rail = 'x402'
                  AND sl.settled_amount_minor > 0
                  AND extract(year FROM (r.ts_utc AT TIME ZONE
                      'America/Sao_Paulo')) = %s
                  AND extract(month FROM (r.ts_utc AT TIME ZONE
                      'America/Sao_Paulo')) = %s
            """, (ano, mes))
            row = cur.fetchone()
            assert row is not None
            n_sql, total_sql_minor = int(row[0]), int(row[1])

    if not compras:
        print(f"sem compras liquidadas na mainnet em {ano:04d}-{mes:02d} — "
              "nada a gerar (estado válido).")
        assert n_sql == 0, "o SQL independente discorda do carregador"
        return

    lanc = contabil.montar_lancamento(compras, ano, mes)

    # [1] validador limpo no documento verdadeiro
    problemas = contabil.validar(lanc, compras, ano, mes)
    assert problemas == [], problemas

    # [2] conferência independente (fuso recomputado DENTRO do Postgres)
    assert lanc.n_compras == n_sql, (lanc.n_compras, n_sql)
    assert lanc.valor_exato == Decimal(total_sql_minor) / contabil.MICRO
    print(f"[1/3] conferência independente OK: {n_sql} compras, "
          f"USD {lanc.valor_exato} exato → USD {lanc.valor_2c} no diário")

    # [3] adulteração TEM de falhar, nomeando o campo
    adulterado = dataclasses.replace(lanc, conta_credito=lanc.conta_debito)
    assert "debito-e-credito-na-mesma-conta" in contabil.validar(
        adulterado, compras, ano, mes)
    adulterado2 = dataclasses.replace(
        lanc, valor_2c=lanc.valor_2c + Decimal("0.01"))
    assert "arredondamento-nao-confere-com-o-exato" in contabil.validar(
        adulterado2, compras, ano, mes)
    print("[2/3] adulteração acusada nomeando o campo (2 sabotagens testadas)")

    destino = RAIZ / "contabil" / f"{ano:04d}-{mes:02d}"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "journal-universal.csv").write_text(
        contabil.render_universal(lanc), encoding="utf-8")
    (destino / "journal-qbo.csv").write_text(
        contabil.render_qbo(lanc), encoding="utf-8")
    (destino / "journal-xero.csv").write_text(
        contabil.render_xero(lanc), encoding="utf-8")
    (destino / "detalhe-compras.csv").write_text(
        contabil.render_detalhe(compras), encoding="utf-8")
    (destino / "resumo.md").write_text(f"""# Export contábil — {ano:04d}-{mes:02d}

Gerado do livro real em {datetime.now(UTC).isoformat(timespec='seconds')}.

- **{lanc.n_compras} compras** x402 liquidadas na mainnet (competência pela data
  de São Paulo — a mesma régua da Fase 11).
- Total exato **USD {lanc.valor_exato}** → lançamento de **USD {lanc.valor_2c}**
  (2 casas, ROUND_HALF_UP; a diferença está declarada na narrativa).
- Débito `{lanc.conta_debito}` × crédito `{lanc.conta_credito}`.
- Conferido contra SQL independente (fuso recomputado no Postgres): bateu.

## Ressalvas ditas com todas as letras
- Regime de CAIXA (só liquidado); só mainnet; sem ganho/perda de disposição
  (USDC ao valor de face) — recortes do v0, doc `docs/fase13-export.md`.
- `journal-qbo.csv`: leiaute do artigo oficial da Intuit.
- `journal-xero.csv`: leiaute de fontes secundárias convergentes — **conferir com
  o template baixado de dentro do Xero antes de importar**; TaxRate padrão
  "Tax Exempt" (ajuste à região da organização).
- `detalhe-compras.csv` é a ponte de auditoria: soma exatamente o total (6 casas)
  e liga cada valor ao tx hash.
""", encoding="utf-8")
    print(f"[3/3] gerado em {destino}")
    print("GATE 13b VERDE — o diário sai do livro, se prova, e acusa adulteração.")


if __name__ == "__main__":
    main()
