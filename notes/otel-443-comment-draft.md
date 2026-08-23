# Rascunho — comentário no open-telemetry semantic-conventions-genai PR #443 (D-28)

*SUBSTITUÍDO em 21/08 à noite pela versão certificada em `notes/publicar/c1-otel-comment.md`.
Motivo: a "citação" de escopo ("all operation costs, not limited to token-derived expenses")
NÃO existe no PR (nem corpo, nem diff, nem comentários — era paráfrase do D-28 que virou
aspas). A versão nova ancora no que o PR diz de verdade (enum `provider`/`local`, rebase de
22/08) e o ponto técnico continua o mesmo: custo de COMPRA precisa de referência de
settlement.*

---

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

---

*Link do PR: github.com/open-telemetry/semantic-conventions (genai) #443 — conferir o repo exato
antes de postar; a 3ª rodada registrou "semconv-genai #443, awaiting final review".*
