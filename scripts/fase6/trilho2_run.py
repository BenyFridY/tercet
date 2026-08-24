"""Fase 6 / T3 — GATE 6(b): o trilho NÃO-cripto reconcilia no mesmo livro, sem migration.

O que roda (custo: ~US$ 0,001 de API — uma chamada LLM real e útil):
1. UMA chamada real ao claude-sonnet-5 pedindo o resumo de 1 linha do censo (dado
   da Fase 3) — o uso de tokens vira um CLAIM `rail='invoice'` no livro, pendurado
   no span da tarefa e anotado com `purchase.*` (aparece no Jaeger também);
2. gera o EXTRATO no formato do console da Anthropic — SINTÉTICO E ROTULADO (D-12),
   agregando os claims de hoje; quando o dono da conta exportar o CSV real do console, o
   MESMO ingestor roda contra ele (aí a deriva, se houver, aparece);
3. ingere o extrato: settlement + legs casando por (dia, modelo); estados viram
   eventos; relatório claim×statement fecha.

Uso: uv run python scripts/fase6/trilho2_run.py
"""

import asyncio
import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from anthropic import AsyncAnthropic
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from rich.console import Console

from mesa import db, exportador, trilho_invoice
from mesa.config import Settings
from mesa.otel import configurar_tracer, ids_do_span_atual

console = Console()
DIR = Path(__file__).parent
MODELO = "claude-sonnet-5"
OTLP = "http://localhost:4318"
CENSO = Path(__file__).resolve().parents[1] / "fase3" / "censo_fechamento.json"


async def chamada_llm_real(settings: Settings) -> tuple[str, int, int]:
    """Uma chamada real e ÚTIL: o resumo de 1 linha do censo. Devolve (texto, in, out)."""
    numeros = json.loads(CENSO.read_text(encoding="utf-8"))["numeros"]
    client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    msg = await client.messages.create(
        model=MODELO, max_tokens=120,
        messages=[{
            "role": "user",
            "content": ("Resuma em UMA frase em português, para um relatório público: "
                        f"num censo de 15 fontes x402 vivas, {numeros['respondem']} "
                        f"responderam, {numeros['aceitam']} aceitaram pagamento, "
                        f"{numeros['entregam']} entregaram e "
                        f"{numeros['ficaram_com_o_dinheiro']} cobraram."),
        }])
    texto = "".join(getattr(b, "text", "")
                    for b in msg.content if getattr(b, "type", "") == "text")
    return texto, int(msg.usage.input_tokens), int(msg.usage.output_tokens)


async def main() -> None:
    settings = Settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY ausente em C:\\dev\\mesa.env")
    conn = db.connect()
    db.apply_migrations(conn)
    tracer = configurar_tracer(conn, "mesa-fase6", otlp_endpoint=OTLP)

    # 1. a chamada real, dentro de um span de tarefa
    with tracer.start_as_current_span("fase6.tarefa-trilho2"):
        trace_id, span_id = ids_do_span_atual()
        texto, tok_in, tok_out = await chamada_llm_real(settings)
        custo_preview = trilho_invoice.custo_llm_micro_usd(
            MODELO, tok_in, tok_out, datetime.now(UTC).date())
        exportador.anotar_span_compra(
            amount_minor=custo_preview, decimals=6, currency="USD",
            rail="invoice", network=None, settlement_ref=None,
            resource_hash_hex=hashlib.sha256(
                f"llm:anthropic:{MODELO}".encode()).hexdigest())

    aid, custo = trilho_invoice.registrar_custo_llm(
        conn, model=MODELO, input_tokens=tok_in, output_tokens=tok_out,
        trace_id=trace_id, span_id=span_id)
    console.print(f"[1/3] LLM real: {tok_in} in + {tok_out} out = "
                  f"US$ {custo / 1e6:.6f} — claim no livro (authz {str(aid)[:8]}…)")
    console.print(f"    a frase que ela produziu: [italic]{texto}[/italic]")

    # 2. o extrato SINTÉTICO ROTULADO no formato do console (agrega claims de hoje)
    hoje = datetime.now(UTC).date().isoformat()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT a.rail_evidence->>'model', "
            "  sum((a.rail_evidence->>'input_tokens')::bigint), "
            "  sum((a.rail_evidence->>'output_tokens')::bigint), "
            "  sum(a.authorized_max_minor) "
            "FROM authz a WHERE a.rail='invoice' AND a.state='authorized' "
            "AND a.rail_evidence->>'dia_utc' = %s GROUP BY 1", (hoje,))
        grupos = cur.fetchall()
    extrato = DIR / "fatura_SINTETICA_demo.csv"
    with extrato.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "model", "input_tokens", "output_tokens", "cost_usd"])
        for model, t_in, t_out, micro in grupos:
            w.writerow([hoje, model, int(t_in), int(t_out),
                        str(Decimal(int(micro)) / Decimal(10**6))])
    console.print(f"[2/3] extrato sintético ROTULADO gerado ({len(grupos)} linha(s)) — "
                  f"o CSV real do console substitui este arquivo quando você exportar")

    # 3. ingerir + reconciliar
    relatorio = trilho_invoice.ingerir_fatura_csv(conn, extrato, "sintetica-demo")
    for linha in relatorio:
        console.print(
            f"[3/3] {linha['dia']} {linha['model']}: statement "
            f"US$ {linha['statement_micro_usd'] / 1e6:.6f} × {linha['claims']} claim(s) "
            f"US$ {linha['claims_micro_usd'] / 1e6:.6f} · deriva "
            f"{linha['deriva_micro_usd']} micro-USD")
        assert linha["claims"] >= 1, "nenhum claim casou"
        assert linha["deriva_micro_usd"] == 0, "deriva no extrato sintético = bug nosso"

    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    provider.force_flush()
    console.print("[bold green]GATE 6(b) VERDE: trilho não-cripto (fatura de API) "
                  "reconciliado no MESMO schema — zero migration[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
