Thanks for this — having `gen_ai.usage.cost.*` land as a convention (instead of every
SDK inventing its own cost attribute) is exactly what's been missing.

One gap from the agent-payments side (x402 / MPP / virtual cards): with the enum now
simplified to `provider`/`local`, a cost whose value is "received from upstream
(provider, gateway, or broker)" covers two very different things — a provider-metered
bill and a **purchase from a third party**. For the purchase case,
`amount + currency + source` is not enough to reconcile the span against the money
that actually moved. Two small additions would make this usable for purchase
attribution:

1. **A settlement/receipt reference attribute** — e.g. `gen_ai.usage.cost.settlement_ref`
   (string): a rail-specific settlement identifier (tx hash, payment intent ID, capture ID,
   receipt ID). Without it, cost-per-span can never be tied back to the money that moved, and
   the attribute silently becomes "self-reported cost" with no verification path.
2. **A way to tell metered cost apart from a third-party purchase** — either an additional
   `cost.source` value (e.g. `purchase`) or a separate attribute like
   `gen_ai.usage.cost.kind`. Under the current two-value enum, both land in `provider`
   and become indistinguishable downstream.

Happy to write up concrete examples from x402 (EIP-3009 settlement: `(authorizer, nonce)` +
tx hash) and MPP's `Payment-Receipt` header if useful — both already carry exactly this
reference today, so the convention would be aligning with shipped wire formats, not inventing.
