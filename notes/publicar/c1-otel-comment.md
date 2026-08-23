Thanks for this — the explicit scope of "all operation costs, not limited to token-derived
expenses" is exactly what's been missing.

One gap from the agent-payments side (x402 / MPP / virtual cards): when the cost is a
**purchase from a third party** rather than a metered operation, `amount + currency + source`
is not enough to reconcile the span against what actually settled. Two small additions would
make this usable for purchase attribution:

1. **A settlement/receipt reference attribute** — e.g. `gen_ai.usage.cost.settlement_ref`
   (string): a rail-specific settlement identifier (tx hash, payment intent ID, capture ID,
   receipt ID). Without it, cost-per-span can never be tied back to the money that moved, and
   the attribute silently becomes "self-reported cost" with no verification path.
2. **Clarify `source` semantics for purchases** — whether `source` is meant to distinguish
   "provider-billed token cost" from "third-party purchase" (x402, card, invoice), or whether a
   separate attribute like `gen_ai.usage.cost.kind` is preferable.

Happy to write up concrete examples from x402 (EIP-3009 settlement: `(authorizer, nonce)` +
tx hash) and MPP's `Payment-Receipt` header if useful — both already carry exactly this
reference today, so the convention would be aligning with shipped wire formats, not inventing.
