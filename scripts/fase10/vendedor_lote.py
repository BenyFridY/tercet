"""Fase 10 — o vendedor de brinquedo que MUDA OS TERMOS para quem tem passaporte.

Duas rotas x402 na testnet:
- GET /unidade — aberta a estranhos: 0,01 USDC por chamada (varejo, pré-pago).
- GET /lote   — 0,10 USDC (o "teto maior" do GATE 10): só para portador de
  passaporte VÁLIDO (mesa-passaporte/v0) com prova de posse fresca.

O portão de passaporte roda POR FORA do middleware x402 (último registrado = mais
externo no FastAPI): quem não passa recebe 403 com os motivos ANTES de pagar —
recusar depois de cobrar seria o footgun, não o produto.

A validação é o nível 1 (offline): assinatura ⇔ sujeito, consistência interna,
política do vendedor (limiares em mesa.passaporte.Politica), prova de posse de 60s.
O vendedor NÃO toca em RPC — é exatamente o que o gate exige.

Subir: uv run uvicorn scripts.fase10.vendedor_lote:app --port 8410
"""

import base64
import binascii
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.http.types import PaymentOption, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from mesa import passaporte as pp
from mesa.config import CAIP2_BASE_SEPOLIA, Settings

settings = Settings()
if not settings.seller_payto:
    raise SystemExit("SELLER_PAYTO vazio — rode scripts/setup_wallets.py primeiro.")

POLITICA = pp.Politica()  # limiares nomeados — decisão DESTE vendedor
HEADER_MAX = 64_000       # mesmo teto da nossa rede segura: header gigante é ataque

app = FastAPI(title="mesa — vendedor com passaporte (Fase 10)")

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
resource_server = x402ResourceServer(facilitator)
resource_server.register(CAIP2_BASE_SEPOLIA, ExactEvmServerScheme())  # type: ignore[no-untyped-call]

routes = {
    "GET /unidade": RouteConfig(
        accepts=PaymentOption(scheme="exact", pay_to=settings.seller_payto,
                              price="$0.01", network=CAIP2_BASE_SEPOLIA)
    ),
    "GET /lote": RouteConfig(
        accepts=PaymentOption(scheme="exact", pay_to=settings.seller_payto,
                              price="$0.10", network=CAIP2_BASE_SEPOLIA)
    ),
}

_x402_middleware = payment_middleware(routes, resource_server)


@app.middleware("http")
async def x402_mw(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    return await _x402_middleware(request, call_next)


def _ler_header_json(request: Request, nome: str) -> dict[str, Any] | None:
    bruto = request.headers.get(nome)
    if bruto is None or len(bruto) > HEADER_MAX:
        return None
    try:
        decodificado = json.loads(base64.b64decode(bruto, validate=True))
    except (ValueError, binascii.Error):
        return None
    return decodificado if isinstance(decodificado, dict) else None


def _recusa(status: int, erro: str, motivos: list[str]) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "erro": erro, "motivos": motivos,
        "termos": {"/unidade": "US$ 0,01 por chamada, aberto a estranhos",
                   "/lote": "US$ 0,10 — exige passaporte valido + prova de posse"},
    })


# O PORTÃO — registrado por último = roda POR FORA do x402: recusa ANTES de cobrar.
@app.middleware("http")
async def portao_passaporte(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path != "/lote":
        return await call_next(request)
    artefato = _ler_header_json(request, "x-passaporte")
    prova = _ler_header_json(request, "x-passaporte-prova")
    if artefato is None or prova is None:
        return _recusa(403, "sem-passaporte",
                       ["apresente x-passaporte e x-passaporte-prova (base64 de JSON)"])
    if falhas := pp.verificar_offline(artefato):
        return _recusa(403, "passaporte-invalido", falhas)
    if falhas := pp.verificar_prova(prova, artefato, rota="/lote",
                                    agora_unix=int(time.time())):
        return _recusa(403, "prova-de-posse-invalida", falhas)
    aceito, motivos = pp.avaliar_politica(artefato, POLITICA, datetime.now(UTC))
    if not aceito:
        return _recusa(403, "recusado-pela-politica", motivos)
    return await call_next(request)


@app.get("/unidade")
async def unidade() -> dict[str, Any]:
    return {"produto": "um fato de brinquedo", "quantidade": 1, "entregue": True}


@app.get("/lote")
async def lote() -> dict[str, Any]:
    return {"produto": "lote de fatos de brinquedo", "quantidade": 10, "entregue": True,
            "termos": "teto maior concedido pelo passaporte"}
