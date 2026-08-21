# Proposta de extensão: payTo Binding (vínculo reverso payTo⇔domínio)

*Texto pronto para o Beny propor no coinbase/x402 (specs/extensions/ — mesmo
framework da offer-and-receipt). Estrutura espelha a extension-offer-and-receipt.
Dado de campo: sondamos 15 vendedores x402 vivos na Base mainnet (21/08/2026) — 0/15
publicam qualquer prova de posse do payTo. Implementação de referência: mesa
(emissor + verificador, nível 2). Compõe com http-message-signatures (identidade do
AGENTE PAGADOR — problema diferente; lida verbatim, ela não cobre payTo⇔domínio).*

---

# payTo Binding Extension

**1. Overview**

An x402 payment requirement tells the buyer *where to send money* (`payTo`) but
nothing in the protocol binds that address to the service's identity (its domain).
A compromised server, a MITM on a misconfigured origin, or a lookalike deployment
can serve legitimate-looking requirements with an attacker's `payTo` — and an
EIP-3009 authorization, once signed, is final.

This extension defines a **bidirectional binding** between a domain and a payment
address, published by the seller and verifiable **offline** by any buyer:

- the **domain endorses the address** (the binding document is served under valid
  TLS on that domain), and
- the **address endorses the domain** (the document carries a signature by the
  address's own key over the domain name).

Neither alone suffices; an attacker must both control the domain's TLS *and* hold
the legitimate address's key. Field data point (2026-08-21): probing 15 live x402
sellers on Base mainnet, **0/15 publish any proof of payTo possession** today.

**2. Assurance ladder (level is part of the evidence)**

| Level | Method | Strength |
|---|---|---|
| 1 | DNS `TXT` under validated DNSSEC | end-to-end cryptographic; low real-world adoption |
| **2** | **Well-known document under TLS + address-key signature over the domain (this spec's operational core)** | strong; no DNSSEC dependency; DNS/BGP hijack alone insufficient |
| 3 | `TXT` via multiple independent DoH resolvers agreeing + TLS serving the same address | medium; resists local poisoning, not zone hijack |
| 4 | none | `unverified` — a **first-class state**, never an error; buyer policy decides (e.g., spend cap for unverified counterparties) |

Verifiers MUST record the achieved level in their evidence; clients MUST NOT treat
level 4 as a failure.

**3. The well-known document (level 2)**

Served at `https://<domain>/.well-known/x402-payto`, `application/json`:

```json
{
  "version": 1,
  "bindings": [
    {
      "address": "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea",
      "networks": ["eip155:8453"],
      "domain": "api.example.com",
      "signature": "0x…"
    }
  ]
}
```

`signature` is an EIP-191 (`personal_sign`) signature by `address`'s key over the
exact message:

```
x402-payto-binding v1
domain: <domain>
address: <address, lowercase>
```

The domain inside the signed message makes cross-domain replay useless: a document
copied to another host fails verification there.

**4. Verification (offline once fetched)**

1. Fetch the document over TLS from the domain under evaluation.
2. Select the binding whose `address` equals the quoted `payTo` (case-insensitive).
3. Reject if the binding's `domain` differs from the fetched domain.
4. Recover the signer of the canonical message; **valid iff signer == address**.
5. Record evidence: level, document, HTTP status, timestamps.

Buyers SHOULD refuse to sign when a valid binding exists for the domain and the
quoted `payTo` does **not** match it ("payTo swapped" — the attack this exists
for), and SHOULD apply policy caps to level-4 counterparties.

**5. Security considerations**

- **Key compromise:** whoever holds the address key can bind it to any domain they
  also control via TLS; the binding proves possession, not virtue. Rotation =
  publishing a new document (verifiers SHOULD honor freshness policy).
- **Non-EVM schemes:** the signature format is per-namespace; this document defines
  `eip155:*` (EIP-191). Other namespaces MAY be added with their native
  message-signing primitive.
- **Relationship to `http-message-signatures`:** that extension authenticates the
  *paying agent*; response signing there is optional and does not reference `payTo`
  or the seller's domain. The two compose; neither subsumes the other.
