"""T6 (Fase 2): o agente real, do ZERO (D-33) — decide sozinho quando vale pagar.

Loop de tool-calling com o SDK oficial da Anthropic (Tool Runner), modelo
`claude-sonnet-5`. Duas ferramentas: uma GRATUITA (notas locais, que não têm a
resposta) e uma PAGA (a ferramenta MCP `consultar`, 0,01 USDC, preço declarado na
descrição). A decisão de comprar é do MODELO — o roteiro só define a tarefa.

Arquitetura (D-05): as ferramentas são wrappers LOCAIS sobre o nosso cliente MCP
instrumentado — a assinatura do pagamento acontece nesta máquina, e cada chamada de
ferramenta vira um span OTel com a compra pendurada no passo exato da decisão.
"""

from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic, beta_async_tool
from mcp import ClientSession
from opentelemetry.trace import StatusCode, Tracer

from mesa.config import Settings
from mesa.mcp.buyer import CapturedMcp, make_mcp_client, result_text_of
from mesa.otel import ids_do_span_atual

MODELO = "claude-sonnet-5"  # D-33

TAREFA = (
    "Você é um agente de pesquisa com orçamento próprio. Sua tarefa: descobrir qual é "
    "o fato de hoje da fonte da mesa e me responder com ele, citando de onde veio. "
    "Gaste o mínimo possível: só use a fonte paga se a gratuita não resolver."
)


@dataclass
class CompraDoAgente:
    """Uma compra feita durante o run do agente, capturada no span da ferramenta."""

    trace_id: str
    span_id: str
    captured: CapturedMcp
    result_text: str | None
    is_error: bool


@dataclass
class RunDoAgente:
    resposta_final: str = ""
    compras: list[CompraDoAgente] = field(default_factory=list)
    chamadas_gratuitas: int = 0
    turnos: int = 0
    # Fase 6: uso de tokens por turno — vira claim rail='invoice' no livro
    usos: list[dict[str, Any]] = field(default_factory=list)


async def rodar_agente(
    settings: Settings, session: ClientSession, tracer: Tracer, tarefa: str = TAREFA
) -> RunDoAgente:
    """Roda a tarefa com o Tool Runner; devolve a resposta e as compras capturadas."""
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY ausente em C:\\dev\\mesa.env — T6 precisa dela.")

    run = RunDoAgente()

    @beta_async_tool
    async def consultar_notas_gratuitas(pergunta: str) -> str:
        """Consulta as notas locais gratuitas do agente. Não custa nada.

        Args:
            pergunta: O que você quer saber.
        """
        with tracer.start_as_current_span("ferramenta.notas-gratuitas") as sp:
            run.chamadas_gratuitas += 1
            sp.set_status(StatusCode.OK)
            return (
                "As notas locais não têm nada sobre o fato de hoje da mesa. "
                "Esse dado só existe na fonte paga da mesa."
            )

    @beta_async_tool
    async def consultar_fonte_paga(pergunta: str) -> str:
        """Consulta a fonte PAGA da mesa. CUSTA 0,01 USDC por chamada (pago na hora,
        da sua carteira). Use somente se for necessário para completar a tarefa.

        Args:
            pergunta: O que você quer saber da fonte paga.
        """
        with tracer.start_as_current_span("ferramenta.fonte-paga") as sp:
            # cliente + captura NOVOS por compra (mesmo padrão da T3) — sem estado cruzado
            captured = CapturedMcp()
            xmcp = make_mcp_client(settings, session, captured)
            t_id, s_id = ids_do_span_atual()
            result = await xmcp.call_tool("consultar", {"pergunta": pergunta})
            texto = result_text_of(result) or ""
            run.compras.append(
                CompraDoAgente(
                    trace_id=t_id,
                    span_id=s_id,
                    captured=captured,
                    result_text=texto,
                    is_error=bool(result.is_error),
                )
            )
            sp.set_status(StatusCode.ERROR if result.is_error else StatusCode.OK)
            return texto if texto else "a fonte paga não devolveu conteúdo"

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    runner = client.beta.messages.tool_runner(
        model=MODELO,
        max_tokens=2048,
        tools=[consultar_notas_gratuitas, consultar_fonte_paga],
        messages=[{"role": "user", "content": tarefa}],
    )
    ultimo: Any = None
    async for message in runner:
        run.turnos += 1
        ultimo = message
        uso = getattr(message, "usage", None)
        if uso is not None:  # Fase 6: cada turno tem custo — o driver grava no livro
            run.usos.append({
                "model": MODELO,
                "input_tokens": int(getattr(uso, "input_tokens", 0)),
                "output_tokens": int(getattr(uso, "output_tokens", 0)),
            })

    if ultimo is not None:
        run.resposta_final = "".join(
            bloco.text for bloco in ultimo.content if getattr(bloco, "type", "") == "text"
        )
    return run
