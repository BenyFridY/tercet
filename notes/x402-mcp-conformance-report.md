# x402-over-MCP conformance findings — Python SDK 2.20.0 vs TypeScript SDK 2.23.0

*Draft issue for github.com/coinbase/x402 — produced by an independent conformance
harness (pytest, offline, no facilitator required). 2026-08-20.*

## Context: which text is normative?

Two texts describe payments over MCP, with **different wire shapes**:

1. **`specs/transports-v2/mcp.md`** (this repo) — the live spec. Payment-required is an
   in-band tool result: *"When a tool requires payment, servers MUST return a tool result
   with `isError: true` containing the `PaymentRequired` data"*, with *"`structuredContent`
   (REQUIRED)"* and *"`content[0].text` (REQUIRED)"*, and `_meta` keys `x402/payment` /
   `x402/payment-response`.
2. **SEP-2007** (modelcontextprotocol PR #2007) — defined a JSON-RPC error `-32402` with
   `payment` in params. Closed on 2026-06-24: *"This SEP has not received a sponsor in the
   past 6 months and is considered dormant."*

This report tests both official SDKs against text (1).

## Findings

### NC-1 — Python: `create_payment_wrapper` is broken against MCP SDK 2.x (blocker)

`x402.mcp.server.create_payment_wrapper` does `from mcp.server.fastmcp import Context`
inside the decorator. The `mcp.server.fastmcp` module was removed in `mcp` 2.0 (the
high-level server is now `mcp.server.MCPServer` / `mcp.server.mcpserver`). Any server
built on the current MCP SDK major cannot use the official wrapper at all:

```python
# x402==2.20.0, mcp==2.0.0
from x402.mcp import create_payment_wrapper
paid = create_payment_wrapper(resource_server, accepts=accepts)
paid(my_handler)   # ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

Additionally, `_extract_payment_from_context` reads `ctx.request_context.meta.model_extra`
(a pydantic-model API from mcp 1.x). In mcp 2.x, `RequestParamsMeta` is an open mapping —
so even with the import fixed, payment extraction would silently return `None` and the
wrapper would answer every paid call with payment-required.

*Workaround we used: call `resource_server.verify_payment` / `settle_payment` directly from
an `MCPServer` tool handler and read `ctx.request_context.meta["x402/payment"]`.*

### NC-2 — Python: client cannot detect payment-required from MCP SDK 2.x results (blocker)

`x402MCPClient` (via `convert_mcp_result` + `extract_payment_required_from_result`)
expects the mcp 1.x wire shape: `content` items as dicts (`isinstance(first_item, dict)`),
and `isError` / `_meta` / `structuredContent` as attributes. mcp 2.x returns pydantic
models with snake_case fields (`is_error`, `meta`, `structured_content`) and typed content
blocks. Result: a **fully spec-conformant** payment-required response (isError=true +
structuredContent + JSON text) is classified as a free-tool result, `payment_made=False`,
and the client never creates a `PaymentPayload` — the normative retry flow never happens.

```python
# x402==2.20.0, mcp_types from mcp==2.0.0
from mcp_types import CallToolResult, TextContent
from x402.mcp.utils import convert_mcp_result, extract_payment_required_from_result
ctr = CallToolResult(content=[TextContent(type="text", text=json.dumps(payment_required))],
                     structured_content=payment_required, is_error=True)
extract_payment_required_from_result(convert_mcp_result(ctr))   # -> None (should parse)
```

*Workaround we used: an adapter that `model_dump(by_alias=True)`s the 2.x result back into
the 1.x wire shape before handing it to `x402MCPClient`.*

### NC-3 — Both SDKs: `MCP_PAYMENT_REQUIRED_CODE = 402` has no normative basis (minor)

Python 2.20.0 and TypeScript 2.23.0 both export `MCP_PAYMENT_REQUIRED_CODE = 402` and a
`createPaymentRequiredError` path that emits a JSON-RPC error with that code. The live
spec defines **no** JSON-RPC error for payment-required (in-band result only); the only
text that ever defined a code — dormant SEP-2007 — required `-32402`. As shipped, the
constant invites implementers to emit a non-standard error shape. Suggest removing it or
documenting it as non-normative.

## What passed (for balance)

- **TypeScript 2.23.0**: payment-required shape fully conformant (isError in-band,
  structuredContent + JSON text), `_meta` keys match the spec, and the wrapper works with
  the current MCP SDK. The TS package is ahead of the Python one.
- **Python 2.20.0**: `_meta` key constants match the spec; payment-required detection
  works correctly for the mcp 1.x wire shape (the failures above are 2.x-compat only).

## Repro

Offline pytest harness (no facilitator, no network):
`conformance/` — `test_python_sdk.py`, `test_typescript_sdk.py` (+ `ts/check.mjs`).
Confirmed non-conformances are encoded as `xfail(strict=True)`, so the suite goes red the
day the bug is fixed. Environment: Windows 11, Python 3.13, `x402==2.20.0`, `mcp==2.0.0`,
Node 24, `@x402/mcp@2.23.0`.
