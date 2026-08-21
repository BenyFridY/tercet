"""T5: as exigências normativas, com CITAÇÃO — acusação sem citação não entra.

DOIS textos existem para pagamento em MCP, e a T5 descobriu que só um está vivo:

1. VIVO — `coinbase/x402 specs/transports-v2/mcp.md` (x402 Foundation), lido em 20/08/2026.
   É o que os SDKs oficiais (Python 2.20.0, TS 2.23.0) declaram implementar.
2. DORMENTE — SEP-2007 (modelcontextprotocol PR #2007): fechado em 24/06/2026 com
   "This SEP has not received a sponsor in the past 6 months and is considered dormant".
   Definia OUTRO wire (erro JSON-RPC -32402, payment em params, não em _meta).

A suíte confere as implementações contra o texto VIVO; o dormente fica como apêndice
histórico (registro em D-34).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Norma:
    id: str
    citacao: str  # verbatim da fonte
    fonte: str


SPEC_VIVO = "coinbase/x402 specs/transports-v2/mcp.md (lido 20/08/2026)"
SEP_DORMENTE = "modelcontextprotocol PR #2007 (SEP-2007, fechado dormente 24/06/2026)"

NORMAS = [
    Norma(
        "N1-payment-required-in-band",
        "When a tool requires payment, servers MUST return a tool result with "
        "`isError: true` containing the `PaymentRequired` data.",
        SPEC_VIVO,
    ),
    Norma(
        "N2-structured-content",
        "Servers MUST provide the `PaymentRequired` in both formats: (1) `structuredContent` "
        "(REQUIRED): Direct `PaymentRequired` object; (2) `content[0].text` (REQUIRED): "
        "JSON-encoded string",
        SPEC_VIVO,
    ),
    Norma(
        "N3-cliente-le-os-dois",
        "Clients SHOULD prefer `structuredContent` when available, falling back to parsing "
        "`content[0].text`",
        SPEC_VIVO,
    ),
    Norma(
        "N4-meta-payment",
        "Clients send payment data using the MCP `_meta` field with key `x402/payment`.",
        SPEC_VIVO,
    ),
    Norma(
        "N5-meta-payment-response",
        'Servers communicate payment settlement results using the '
        '`_meta["x402/payment-response"]` field.',
        SPEC_VIVO,
    ),
    Norma(
        "N6-fluxo-retry",
        "Client calls a paid tool without payment; Server returns a tool result with "
        "`isError: true` and `PaymentRequired` data; Client extracts payment requirements "
        'and creates a `PaymentPayload`; Client retries the tool call with payment in '
        '`_meta["x402/payment"]`',
        SPEC_VIVO,
    ),
    # Apêndice histórico — o wire do SEP dormente, DIFERENTE do vivo:
    Norma(
        "H1-sep2007-erro-32402",
        "When payment is required for a tool invocation, servers MUST return error code "
        "`-32402` with protocol-specific payment information.",
        SEP_DORMENTE,
    ),
]

POR_ID = {n.id: n for n in NORMAS}

# O PaymentRequired mínimo usado nos cenários (shape do wire v2, camelCase)
ACCEPTS_EXEMPLO = [
    {
        "scheme": "exact",
        "network": "eip155:84532",
        "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "amount": "10000",
        "payTo": "0xe79B79edEF18A726c989da6546Ba4fa23a8F12d8",
        "maxTimeoutSeconds": 300,
    }
]

PAYMENT_REQUIRED_EXEMPLO = {
    "x402Version": 2,
    "accepts": ACCEPTS_EXEMPLO,
    "error": "Payment Required",
    "resource": {
        "url": "mcp://tool/consultar",
        "description": "cenario de conformance",
        "mimeType": "application/json",
    },
}
