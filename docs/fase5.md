# Fase 5 — checagens no SDK + as duas contribuições de padrão (doc de design)

> **Status 21/08:** engenharia COMPLETA no mesmo dia — **GATE 5(a) ✅** (os 3 ataques
> recusados sem rede, com motivo nomeado: `tests/test_checagens.py`, 45 testes verdes);
> checagens integradas no seletor do censo e no `make_client`; vínculo reverso N2
> implementado (emissor no vendedor + verificador offline) e sondado no censo —
> **achado: 0/15 vendedores publicam vínculo** (verification rows no livro);
> os **3 textos de PR prontos** em `notes/` (Security Consideration, extensão
> payTo-binding, conserto do SDK Python — NC-1 confirmado AINDA vivo no main
> `dd927a2`; NC-2 meio-consertado, resta o `content[0]` como dict).
> **GATE 5(b) ⏳:** fecha quando o Beny postar as submissões (com as 2 já pendentes).

*Escrito em 21/08/2026, antes de qualquer código, pelo método do programa (D-31).
Fontes: PLANO.md (seção Fase 5), DECISOES.md (D-07, D-22, D-23, D-34), a escada N1–N4
do `arquivo/06`, e os dados REAIS do censo (Fase 3). Custo da fase: **zero**.*

## O que é esta fase, em linguagem direta

O golpe contra um comprador-agente acontece **antes de assinar**. A cotação chega e
diz "pague X do token Y para o endereço Z" — se o agente assina sem conferir, já era:
a autorização EIP-3009 é válida e o dinheiro sai. Os três golpes clássicos:

1. **payTo trocado** — a cotação é legítima na aparência, mas o endereço de
   recebimento é do atacante (site comprometido, MITM, típosquat);
2. **ativo sósia** — o token diz "USDC" mas o CONTRATO é outro (símbolo é grátis;
   endereço é identidade — D-07);
3. **decimais mentidos** — a cotação afirma decimais errados para o valor "parecer"
   pequeno (1000 unidades com 6 casas = US$ 0,001; com 2 casas = US$ 10).

A defesa vira **funções internas do SDK do livro** (D-23: nunca pacote standalone —
a Countersign já shipou esse produto; o valor aqui é proteger o NOSSO comprador
instrumentado e virar PR de warning nos SDKs oficiais). E roda **OFFLINE**: na hora
de decidir, zero rede — a verdade vem de um **registro pinado** construído e
validado on-chain ANTES (mesma filosofia point-in-time do seu trabalho quant:
decisão nunca usa dado que não estava validado no momento).

## Por que offline importa

Checagem que consulta a rede na hora da compra (a) adiciona latência no caminho da
decisão, (b) cria dependência que pode ser atacada (o mesmo MITM que trocou o payTo
responde a consulta), e (c) viola o D-05 se virar gargalo. O registro pinado é
pequeno (os USDC canônicos por rede, com decimais lidos do contrato uma única vez)
e versionado no repo — auditável, reproduzível.

## Os componentes

1. **`src/mesa/checagens.py`** — funções PURAS, sem rede, com veredito nomeado
   (evidência, não booleano — invariante 4):
   - `checar_ativo(cotacao, registro)` → recusa `ativo-sosia` se o ENDEREÇO do
     contrato não está no registro daquela rede (símbolo é ignorado por princípio);
   - `checar_decimais(cotacao, registro)` → recusa `decimais-mentidos` se a cotação
     afirma decimais ≠ pinado (e o valor cru é sempre calculado por NÓS);
   - `checar_payto(cotacao, vinculo)` → recusa `payto-nao-vinculado` conforme a
     política: o payTo confere com o vínculo domínio⇔endereço apresentado? `unverified`
     é estado de primeira classe (nível 4 da escada), NUNCA erro — a política do
     comprador decide o teto para contraparte não verificada;
   - `checar_cotacao(...)` → agrega tudo num `Veredito` (aprovada | recusada + motivo
     + evidência completa).
2. **Registro pinado** — `scripts/fase5/pinar_registro.py` (ONLINE, uma vez): lê
   `decimals()`/`symbol()` dos contratos canônicos (Sepolia + mainnet) e grava
   `src/mesa/registro_ativos.json` versionado. As checagens só LEEM o arquivo.
3. **`src/mesa/vinculo.py` — o vínculo reverso (a contribuição ii do D-22).** A escada
   N1–N4 do `arquivo/06`, com o nível na evidência:
   - N1: TXT com DNSSEC validado (forte, adoção baixa);
   - **N2 (o achado): `/.well-known/x402-payto` sob TLS contendo o endereço E uma
     assinatura da chave daquele endereço atestando o domínio** — bidirecional, sem
     DNSSEC; DNS/BGP sozinho não vence;
   - N3: TXT via DoH em resolvedores independentes concordando;
   - N4: `unverified`.
   Implementamos: **emitir** (nosso vendedor publica o well-known assinado — dogfood)
   e **verificar** (sonda o domínio, valida a assinatura OFFLINE, grava `verification`
   com nível e prova).
4. **Integração nos compradores** — o seletor do censo e os clientes x402 ganham as
   checagens client-side (D-05: enforcement é do comprador; nunca no caminho de
   ninguém).
5. **Sonda de vínculo no censo (grátis):** bater no `/.well-known/x402-payto` dos 15
   domínios do censo. Achado esperado: **0/15 publicam** — é o dado que justifica a
   proposta de extensão ("ninguém tem como provar que o payTo é seu; aqui está o
   mecanismo").
6. **Os três textos de PR** (prontos em `notes/`, submissão é SUA — 🔑):
   - (a) **Security Consideration de posse do endpoint** no draft de discovery DNS do
     x402 (D-22-i: um dia de trabalho, crédito permanente, inexistente hoje);
   - (b) **extensão do vínculo reverso** no framework de extensões do x402 v2 (a
     escada N1–N4; compõe com a `http-message-signatures` da Cloudflare — que, lido
     verbatim, NÃO cobre payTo⇔domínio: D-22 nota da 3ª rodada);
   - (c) **PR de conserto do SDK Python** (NC-1/NC-2 do nosso relatório de
     conformance): os adapters da Fase 2 são o conserto já validado em produção.

## As etapas

| # | Etapa | O quê | Custa? | Pronto quando |
|---|---|---|---|---|
| T1 | As checagens | registro pinado (on-chain 1×, depois offline) + `checagens.py` puras + testes dos 3 ataques SEM rede | grátis | **GATE 5(a)**: os 3 ataques recusados em teste reproduzível offline |
| T2 | Integração | checagens no seletor do censo e nos clientes; teste de integração (cotação forjada → compra não acontece) | grátis | comprador instrumentado recusa por padrão |
| T3 | Vínculo reverso | `vinculo.py` (emitir + verificar, escada N1–N4) + nosso vendedor publica o N2 + sonda nos 15 domínios do censo | grátis | round-trip N2 verde; achado do censo documentado com evidência |
| T4 | Os 3 textos | Security Consideration + extensão do vínculo reverso + PR de conserto do SDK Python (patch + texto) em `notes/` | grátis | textos prontos para você postar |
| T5 | 🔑 GATE 5 | (a) já verde na T1; (b) **submissões são AÇÕES SUAS** (junto com as 2 pendentes: relatório de conformance e OTel #443) | grátis | (a) automático; (b) marcado "pronto para submissão" — o gate fecha quando você postar |

## Custos declarados

- **Dinheiro: zero.** Sondas são HTTP grátis; o registro lê a chain (leitura é grátis).
- **LLM: zero.**

## Riscos, ditos com franqueza

1. **O gate (b) depende de ação externa sua** — o doc marca "pronto para submissão"
   e o gate fecha de verdade quando os PRs existirem. Sem drama: é 15 min seus.
2. **O draft de discovery DNS pode ter mudado/morrido** desde a pesquisa (era o
   `draft-jeftovic-x402-dns-discovery`) — a T4 confere o estado ANTES de escrever, e
   se ele morreu, a Security Consideration muda de alvo (o doc registra).
3. **O patch do SDK Python** precisa ser gerado contra o `main` atual do
   coinbase/x402 (o 2.20.0 instalado pode ter divergido) — a T4 clona e confere.
4. **Escopo contido:** N1 (DNSSEC) e N3 (DoH múltiplo) ficam ESPECIFICADOS na
   extensão mas só o N2 é implementado nesta fase — é o que roda em produção e o que
   o censo pode medir. Implementar resolvedor DNSSEC agora seria overengineering.
