# Who delivers, and who takes the money? Paying 15 live x402 sellers (round 1)

*A buyer-side census of the x402 ecosystem, 2026-08-21. Every paid claim below links to
its on-chain receipt on Base. Payer wallet: `0x637f374eFB45582554A2EC0066188d4Fa95aB2DC` — the entire round can be
re-derived from the chain alone.*

## The four numbers

Out of **15 sellers** sampled from the Coinbase Bazaar index
(3,000+ resources, 604 domains; stratified by price band, not cheapest-first):

- **15/15 respond** to an unauthenticated request;
- **15/15 return a valid quote** (canonical USDC on Base mainnet, `exact` scheme);
- **13/15 deliver** after payment (HTTP 200 + non-empty body);
- **13/15 settled on-chain** — exactly the ones that delivered.

Total spent: **$0.2720 USDC**. Delivery rate
87% (Wilson 95% CI [62%–96%], n=15). Effective
cost per delivery: **$0.0209**.

## Per-seller results

| seller | advertised | quoted | delivered | settled | receipt |
|---|---|---|---|---|---|
| api.arkm.com | $0.2000 | $0.2000 | yes | yes | [0x659b8b1a…](https://basescan.org/tx/0x659b8b1a6370305f77212e4499c1f182f0b40e95e758b92054a71a6d06a4851f) |
| conc-exe.xyz | $0.0200 | $0.0200 | yes | yes | [0x22cf4994…](https://basescan.org/tx/0x22cf4994c52dc6764c1d27d25d85f6dd573c6071e956332b5b9f4e53b292a135) |
| screenshots.underscoredone.com | $0.0200 | $0.0200 | yes | yes | [0x29ef388c…](https://basescan.org/tx/0x29ef388c8c97bb06c59be03796a761efb76db1ebd45b35ad4e687f488f930cb8) |
| fresh-feeds.foomworks.workers.dev | $0.0200 | $0.0200 | yes | yes | [0xb8306c91…](https://basescan.org/tx/0xb8306c91920c1b89b278a549d7180eb5d2a52e8653b14835235ac53c3aacaa8f) |
| riddlex402.vercel.app | $0.0020 | $0.0020 | yes | yes | [0xcc28ba6a…](https://basescan.org/tx/0xcc28ba6ae46795e103985d86a101749965e4c4ddbca5d71dc6881ae9c56f82b3) |
| jokes-endpoint.vercel.app | $0.0020 | $0.0020 | yes | yes | [0x5a514e31…](https://basescan.org/tx/0x5a514e31756255daa35fb12d10778c2ba44127424814d5bc07d7f4e14b1bab75) |
| api.printmoneylab.com | $0.0020 | $0.0020 | yes | yes | [0xd7c147ed…](https://basescan.org/tx/0xd7c147ed46c7a49d858d166f67fda7c34a33d4d85f89f9388b2ac6d6a6368d70) |
| api.onesource.io | $0.0010 | $0.0010 | yes | yes | [0x34d06f9b…](https://basescan.org/tx/0x34d06f9ba6da38195565fd2a67e2014058ac51ccdea01b34b5c54fef8f6bad79) |
| x402.ottoai.services | $0.0010 | $0.0010 | yes | yes | [0x7b6ac907…](https://basescan.org/tx/0x7b6ac907aa48ae5ea8cd82687f60f3795789d7169ef31e39de2e6010901fb0d1) |
| randomfactsx402.vercel.app | $0.0010 | $0.0010 | yes | yes | [0xb3bccf39…](https://basescan.org/tx/0xb3bccf39c611845bdbd6ebd916b3c91a0fd67a4875c62820e6b699a20449e5e7) |
| coinflip402.vercel.app | $0.0010 | $0.0010 | yes | yes | [0xe6cd835c…](https://basescan.org/tx/0xe6cd835c1b34a536433b006c151116e31fbeae0999dcf45e9ac6787f95243c7f) |
| memegeneratorx402.vercel.app | $0.0010 | $0.0010 | yes | yes | [0x69a5fa4b…](https://basescan.org/tx/0x69a5fa4bc79eb25f6725d93a273971fd1f0832cc0975e82d4d5998f07a230d10) |
| x402lifeadvice.vercel.app | $0.0010 | $0.0010 | yes | yes | [0x2b3dfcb3…](https://basescan.org/tx/0x2b3dfcb3fd3049c8a427939101e8d01edcfc3ff4401626520d2cd50d06fac63b) |
| stableenrich.dev † | $0.0020 | $0.0020 | **no** | **no** | — (authorization expired unused) |
| dripstack.xyz | $0.2000 | $0.5000 ⚠️ | **no** | **no** | — (authorization expired unused) |

⚠️ = quoted price differs from the price advertised in the index.
† = the 400 came from our generic example body; possibly probe-induced, counted
as non-delivery under our method and flagged.

## Findings

1. **The failures did not take the money.** Both non-deliveries never settled:
   their EIP-3009 authorizations **expired unused** — a dead receivable, not a
   loss. Expiry semantics are real buyer protection, and worth designing around.
2. **Price drift exists in the index:** dripstack.xyz advertised $0.2000 but quoted $0.5000 — 2.5× the
   advertised price, and the most expensive item of the round. That same seller
   re-issued a 402 *after* being paid, delivered nothing — and never charged (see 1).
3. **0/15 sellers prove control of their payout address.** We probed
   every seller for a domain⇔payTo binding (0 verified). Consequence,
   measured by replaying our round point-in-time: a "verified counterparties only"
   policy buys **nothing** today. We drafted a `/.well-known/x402-payto` extension
   (signature by the payTo key over the domain) to make that policy viable.
4. **Cheap did not mean bad.** Micro purchases (≤ $0.01) delivered
   90% (CI [60%–98%]) at
   $0.0013 per delivery — ~16× cheaper than the
   round average. Small n; the CI says so.
5. **3 sellers speak MPP on the same endpoints** (`WWW-Authenticate: Payment`)
   — multi-rail is already live in the wild.
6. **The buyer pays the price and nothing else:** settlement gas is borne by the
   facilitator (observed total across 13 settlements:
   ~0.0000058 ETH).

## Method (so you can replicate it)

- **Discovery:** Bazaar index, stratified sample across price bands.
- **Probe (free):** x402 v2 quotes arrive in the base64 `payment-required` header
  (the JSON body is usually `{}`); HTTP method comes from the index entry.
- **Paid round:** one purchase per seller, hard caps enforced client-side *before
  signing* ($1/purchase, $20/round), pinned asset registry (address is identity).
- **Verification:** an independent collector scans `AuthorizationUsed(authorizer)`
  on Base and joins on (authorizer, nonce). No seller self-reporting is trusted:
  "settled" means the chain says so.
- **"Delivered" is a labeled structural proxy** (HTTP 200 + non-empty body).
  Content quality was NOT evaluated.
- **Audit, not ranking.** n=15 and <5 comparables per category: we publish facts
  per seller and confidence intervals, not quality scores. Ties are ties.

## Limits and disclosure

One round, one day (2026-08-21), n=15. Personal capital, dollar-cents amounts, no
affiliation with any seller or with Coinbase. Raw data ships next to this file
(`dados/`); the buyer's ledger is hash-chained and externally timestamped
(RFC 3161 + OpenTimestamps), with an independent ~100-line verifier.
