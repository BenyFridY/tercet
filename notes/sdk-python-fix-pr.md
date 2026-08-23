# PR: fix Python SDK `x402.mcp` compatibility with `mcp` SDK 2.x

*Texto pronto para o Beny abrir como PR no coinbase/x402 (fork → branch → PR),
referenciando a issue do relatório de conformance (notes/x402-mcp-conformance-report.md,
postar a issue PRIMEIRO e linkar aqui). Verificado contra `main` @ `dd927a2`
(21–22/08/2026). O conserto abaixo é o que o mesa roda EM PRODUÇÃO desde 20/08
(adapters da nossa Fase 2, validados com pagamentos reais em testnet).*

---

**Title:** `fix(python/mcp): support mcp>=2.0 — server wrapper import & content-item
fallback in payment-required detection`

## Problem

The `x402.mcp` module targets the `mcp` 1.x SDK surface. Against `mcp>=2.0.0`
(current stable), two failures — one hard, one silent:

**1. Server wrapper is unusable (hard failure).** `python/x402/mcp/server.py:87`

```python
# Lazy import mcp types so the module can be imported without mcp installed
from mcp.server.fastmcp import Context
```

`mcp.server.fastmcp` was removed in mcp 2.0 (`MCPServer` replaced it) →
`ModuleNotFoundError` the moment `create_payment_wrapper(...)` is called. (The
module-level docstring example also instructs users to `from mcp.server.fastmcp
import FastMCP`, which no longer exists.) Additionally, meta extraction
(`server.py:317-319`) reads `request_context.meta.model_extra` — the 1.x pydantic
shape. In mcp 2.0, `Context.request_context.meta` is a plain open mapping; there
is no `.model_extra`, the resulting `AttributeError` is swallowed by the
`except (ValueError, AttributeError)` right below, so even with the import fixed,
`_meta["x402/payment"]` is never found and every paid call is treated as unpaid
(server returns payment-required forever).

**2. Client silently treats paid tools as free when the seller uses the
`content[0].text` channel (silent failure).** `python/x402/mcp/utils.py:139-141`

```python
first_item = result.content[0]
if isinstance(first_item, dict) and first_item.get("type") == "text":
```

Under mcp 2.0, content items are typed pydantic objects (`TextContent`), never
dicts → the branch is dead. The x402 MCP transport spec (specs/transports-v2/mcp.md)
makes BOTH channels REQUIRED on payment-required results (`structuredContent` and
`content[0].text`); a client that cannot read the `content` channel breaks against
any seller where `structured_content` is absent or stripped by an intermediary —
and fails not with an error, but by returning the 402 body as if it were the tool's
real (free) output. This is the worst failure mode for an autonomous buyer: it
thinks it got the product.

## Proposed changes (validated in production by our instrumented buyer)

**`server.py` — dual-SDK meta extraction:**

```python
def _extract_meta(request_meta: Any) -> Any:
    if request_meta is None:
        return None
    # mcp >= 2.0: plain mapping
    if isinstance(request_meta, dict):
        return request_meta.get(MCP_PAYMENT_META_KEY)
    # mcp 1.x: pydantic extras
    extra = getattr(request_meta, "model_extra", None)
    if extra:
        return extra.get(MCP_PAYMENT_META_KEY)
    return None
```

and guard the fastmcp import (`try: from mcp.server.fastmcp import FastMCP` with a
clear error naming the supported paths), adding an `MCPServer`-based wrapper for
mcp 2.0 (we can contribute ours — `@server.tool` handler wrapping with
verify/settle primitives, which is how we bypassed the breakage).

**`utils.py` — content items as dicts OR typed objects:**

```python
def _text_of(item: Any) -> str | None:
    if isinstance(item, dict):
        return item.get("text") if item.get("type") == "text" else None
    if getattr(item, "type", None) == "text":
        return getattr(item, "text", None)
    return None
```

used by `extract_payment_required_from_result` for the `content[0]` fallback.

## Tests

Our conformance suite (pytest, in the linked issue's repro) encodes these as
`xfail(strict=True)` against the released package — happy to adapt it as regression
tests in `python/x402/mcp/tests/` (parametrized over dict-shaped and typed-object
results).

## Context

Found while building a buyer-side ledger for agent purchases; the failures were hit
live and the fixes above have been running since 2026-08-20 against `mcp==2.0.0`
(streamable HTTP transport, real settlements on Base Sepolia).

## Side observation (happy to split into its own issue if preferred)

While hardening our buyer we noticed `x402AsyncTransport.handle_async_request`
(`python/x402/http/clients/httpx.py`) does `await response.aread()` +
`response.json()` on the **402 response body with no size bound** before the
selector runs. A hostile seller can answer the unauthenticated 402 with a
multi-GB body and exhaust the buyer's memory before any payment decision is made
(v2 carries the quote in the `payment-required` header, so the body isn't even
needed on the happy path). A `Content-Length`/streamed-read cap (even a generous
fixed one) on that pre-payment read would close it.
