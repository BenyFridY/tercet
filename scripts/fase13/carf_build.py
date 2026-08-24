"""GATE 13c: a visão CARF (OECD) das nossas transações — DEMO/teste rotulada.

O que este script prova:
1. o XML sai do livro real (transações REAIS, identidades SINTÉTICAS), nascendo
   OECD11 (New Test Data) e com Warning de DEMONSTRAÇÃO;
2. o agregado bate com SQL independente (fuso de SP recomputado no Postgres);
3. o validador (codado do guia oficial jul/2025) passa no documento verdadeiro e
   ACUSA as adulterações, nomeando o campo.

Uso: uv run python scripts/fase13/carf_build.py [ano]
"""

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from mesa import carf, ptax
from mesa.app import dados

RAIZ = Path(__file__).resolve().parents[2]


def main() -> None:
    hoje_sp = datetime.now(UTC).astimezone(ptax.TZ_SP).date()
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else hoje_sp.year

    with dados.conectar_leitura() as conn:
        ag = carf.agregar_ano(conn, dados.mapa_dominios(), ano)
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
            """, (ano,))
            row = cur.fetchone()
            assert row is not None
            n_sql, total_sql_minor = int(row[0]), int(row[1])

    assert ag.n_transacoes == n_sql, (ag.n_transacoes, n_sql)
    assert ag.usd_exato == Decimal(total_sql_minor) / Decimal(1_000_000)
    print(f"[1/3] agregado bate com SQL independente: {n_sql} transferências de "
          f"saída, USD {ag.usd_exato} ({ag.cripto_ativo})")

    if ag.n_transacoes == 0:
        print(f"sem transações mainnet em {ano} — nada a gerar (estado válido).")
        return

    xml = carf.montar_xml(ag)
    problemas = carf.validar(xml)
    assert problemas == [], problemas
    assert b"OECD11" in xml and b"DEMONSTRACAO" in xml  # nasce rotulado teste
    print("[2/3] validador (do guia jul/2025) limpo; documento nasce OECD11 + "
          "Warning de demonstração")

    # adulterações TÊM de falhar, nomeando o campo
    sab1 = xml.replace(b"CARF603", b"CARF999")
    assert any(p.startswith("TransferType-fora-da-tabela")
               for p in carf.validar(sab1))
    sab2 = xml.replace(f">{ag.amount_2c}<".encode(),
                       f">{ag.usd_exato}<".encode())
    assert any(p.startswith("Amount-sem-2-casas") for p in carf.validar(sab2))
    sab3 = xml.replace(b">CARF<", b">XXXX<")
    assert "MessageType-diferente-de-CARF" in carf.validar(sab3)
    print("[3/3] adulteração acusada nomeando o campo (3 sabotagens testadas)")

    destino = RAIZ / "fiscal" / "carf" / f"{ano:04d}"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "carf-demo-test-data.xml").write_bytes(xml)
    (destino / "resumo.md").write_text(f"""# CARF (OECD) — visão demo {ano}

Gerado do livro real em {datetime.now(UTC).isoformat(timespec='seconds')}.

**O que é:** a visão de conformidade — o que um RCASP reportaria sobre estas
transações a partir de 2027. A mesa NÃO é RCASP; isto NÃO é um reporte. O
documento nasce **OECD11 (New Test Data)** com Warning de DEMONSTRAÇÃO;
identidades SINTÉTICAS; transações REAIS do livro.

- `CryptoTransferOut` · `TransferType CARF603` (compra de bens/serviços,
  guia jul/2025) · **{ag.n_transacoes} transações** · Amount **USD
  {ag.amount_2c}** (2 casas, regra do guia) · NumberofUnits {ag.usd_exato:.6f}
  ({ag.cripto_ativo}) · AltValuation CARF1004 (USDC→USD 1:1, estimativa
  DECLARADA — D-12).
- Conferido contra SQL independente: bateu.

## Ressalvas ditas com todas as letras
- Fonte primária: OECD "CARF XML Schema (July 2025) — User Guide for Tax
  Administrations". O **XSD oficial não é público** (CARFXML_v1.5.xsd é
  distribuído às administrações): a validação aqui é o validador próprio codado
  do guia — o mesmo padrão do validador do leiaute da Fase 11. Quando o XSD
  aparecer, pluga `lxml.XMLSchema` (watchlist).
- URIs de namespace por convenção OECD — A CONFIRMAR contra o XSD.
- A tabela BR (DeCripto, TipoTransferenciaSaida) é derivada da família de enums
  CARF, mas a numeração não é 1:1 com jul/2025 (compra = CARF603; 604 é
  collateral).
""", encoding="utf-8")
    print(f"gerado em {destino}")
    print("GATE 13c VERDE — a visão CARF sai do livro, rotulada teste, e o "
          "validador morde.")


if __name__ == "__main__":
    main()
