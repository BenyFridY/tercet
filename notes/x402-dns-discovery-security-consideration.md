# Security Consideration: posse do endpoint ≠ posse do payTo

*Texto pronto para o Beny propor ao autor do `draft-jeftovic-x402-dns-discovery`
(vivo no datatracker, checado 21–22/08/2026) — como issue/e-mail sugerindo a seção,
ou PR se o draft tiver repo público. D-22(i): a seção não existe hoje.*

---

**Proposed addition — Security Considerations: Endpoint possession vs. payment
address possession**

DNS-based discovery answers one question: *where* an x402-capable endpoint for a
name lives. Implementers frequently assume it answers a second one — *whom the
buyer would be paying* — and it does not. Three distinct trust statements are
involved, and this mechanism establishes only the first:

1. **Zone control at publication time.** A discovery record proves that whoever
   published it controlled the DNS zone then. Without DNSSEC validation, resolution
   is subject to cache poisoning and on-path rewriting; with DNSSEC, the proof is
   only as fresh as the record's TTL and signing period.

2. **Endpoint possession.** Control of the zone does not imply control of the host
   the record points at (dangling records, expired hosting, compromised origin).
   A buyer that trusts the record has still only reached *some* endpoint.

3. **Payment address possession.** Nothing in discovery — nor in TLS on the
   endpoint — binds the `payTo` inside the endpoint's payment requirements to the
   entity that owns the name. A compromised or spoofed endpoint serves
   well-formed requirements with an attacker's address, and a signed EIP-3009
   authorization is final.

Recommended text for implementers:

> Discovery records MUST NOT be interpreted as endorsement of any payment address
> served by the discovered endpoint. Clients performing automated payments SHOULD
> verify payment-address possession through an independent mechanism (e.g., an
> address-key-signed domain binding published by the seller) and SHOULD apply
> spending policy to counterparties whose addresses are unverified. Publishers
> SHOULD sign discovery records (DNSSEC) and SHOULD keep them consistent with any
> address-binding documents they publish, so that a mismatch is detectable rather
> than silent.

Field observation supporting the concern: probing 15 live x402 sellers indexed on
Base mainnet (2026-08-21), 0/15 publish any verifiable binding between their domain
and their `payTo`; buyers today have no way to distinguish a legitimate quote from
a swapped-address quote served by the same URL.
