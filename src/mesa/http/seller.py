"""T2: o vendedor de brinquedo — um endpoint x402 que cobra 0,01 USDC (`exact`) na Base Sepolia.

Sem banco ainda (T3). O middleware do SDK faz o 402 -> verify -> settle via facilitator;
ninguém aqui toca em gas: o facilitator submete a transação (D-18).
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.http.types import PaymentOption, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from mesa.config import CAIP2_BASE_SEPOLIA, Settings

settings = Settings()
if not settings.seller_payto:
    raise SystemExit("SELLER_PAYTO vazio — rode scripts/setup_wallets.py primeiro.")

app = FastAPI(title="mesa — vendedor de brinquedo (T2)")

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
resource_server = x402ResourceServer(facilitator)
resource_server.register(CAIP2_BASE_SEPOLIA, ExactEvmServerScheme())  # type: ignore[no-untyped-call]

routes = {
    "GET /brinquedo": RouteConfig(
        accepts=PaymentOption(
            scheme="exact",
            pay_to=settings.seller_payto,
            price="$0.01",
            network=CAIP2_BASE_SEPOLIA,
        )
    )
}

_x402_middleware = payment_middleware(routes, resource_server)


@app.middleware("http")
async def x402_mw(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    return await _x402_middleware(request, call_next)


# CAOS — CENÁRIO 1 (kill-after-settle). Registrado DEPOIS do x402 => roda POR FORA dele:
# quando a resposta volta aqui, o settle JÁ aconteceu (o SDK é serve-then-settle).
# Só mata requisição PAGA (com PAYMENT-SIGNATURE) — senão mataria o 402 inicial e
# o cliente nunca pagaria.
@app.middleware("http")
async def chaos_mw(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if (
        request.headers.get("x-chaos") == "kill-after-settle"
        and request.headers.get("payment-signature") is not None
    ):
        raise RuntimeError("CHAOS: settle feito, resposta destruída antes de chegar ao cliente")
    return response


@app.get("/brinquedo")
async def brinquedo(request: Request) -> dict[str, str | bool]:
    # CAOS — CENÁRIO 3 (handler falha DEPOIS da verificação). Fato do SDK (Tarefa 0):
    # ele NÃO liquida em resposta de erro => resultado esperado é autorização assinada
    # SEM liquidação (dinheiro não sai), não "cobrou e falhou".
    if request.headers.get("x-chaos") == "fail-handler":
        raise HTTPException(500, "CHAOS: handler quebrou depois de o pagamento ser verificado")
    return {"produto": "um fato de brinquedo", "entregue": True}


# CAOS — CENÁRIO 2 (free-ride): rota FORA da config x402 — serve sem cobrar.
@app.get("/free-ride")
async def free_ride() -> dict[str, str | bool]:
    return {"produto": "de graça, por engano", "entregue": True}
