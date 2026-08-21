# Fase 3 — o censo comprador (doc de design)

> ✅ **GATE 3 VERDE em 21/08/2026** — fase inteira em 1 dia, as 3 aprovações dadas na
> ordem (desenho · US$ 10 financiados · "vai"). Resultado: **15/15 respondem · 15/15
> aceitam · 13/15 entregam · 13/15 ficaram com o dinheiro** (= exatamente as que
> entregaram; as 2 falhas não cobraram, mas seguram autorização viva — vigilância).
> **Custo total liquidado: US$ 0,272** (teto US$ 20) · saldo restante US$ 9,73.
> Dados por fonte com tx hash: `scripts/fase3/censo_fechamento.json`.

*Escrito em 21/08/2026, antes de qualquer código e de qualquer centavo, pelo método do
programa (D-31). Nada desta fase gasta dinheiro sem aprovação explícita do Beny — os
pontos de aprovação estão marcados com 🔑.*

## O que é esta fase, em linguagem direta

Até aqui, todos os pagamentos foram em **testnet** (dinheiro de mentira) contra vendedores
que **nós mesmos** criamos. A Fase 3 sai a campo: vamos descobrir quais vendedores x402
estão **de verdade vivos na internet**, e **comprar uma rodada de cada um** — com USDC real,
na rede principal (Base mainnet).

**Por que isso vale a pena:** todo mundo que "avalia" fontes x402 hoje só olha de fora (o
site responde? o endpoint anuncia preço?). Ninguém publica o que acontece quando você
**paga de verdade** — porque medir isso custa dinheiro. Nós vamos medir e guardar a prova
de cada medida (o recibo on-chain). Esse dado bruto vira o relatório público da Fase 9 —
a nossa primeira peça de distribuição.

## Os quatro números (o que medimos de cada fonte)

| # | Pergunta | Como se mede | Custa? |
|---|---|---|---|
| 1 | **Responde?** | requisição simples; esperamos o "pague primeiro" (402) | grátis |
| 2 | **Aceita pagamento?** | a cotação que ela devolve é válida? (USDC canônico, rede certa, esquema `exact`, campos coerentes) | grátis |
| 3 | **Entrega?** | pagamos 1 vez e conferimos: HTTP 200 + corpo não-vazio + coerente com o anunciado | 💰 |
| 4 | **Ficou com o dinheiro?** | a blockchain confirma a liquidação da NOSSA autorização (evento `AuthorizationUsed` com a nossa carteira) | grátis (leitura on-chain) |

Mais a métrica quant (D-15): **custo total de liquidação por fonte** — preço pago + taxas
observáveis, rateados por compra. Tudo entra no livro como qualquer compra; toda afirmação
sai com o hash da transação do lado.

## As regras de segurança (decididas ANTES de ver qualquer fonte)

1. **Carteira nova e exclusiva do censo**, com SÓ o orçamento dentro — se qualquer coisa
   der errado, o dano máximo é o orçamento. Nunca as carteiras de teste, nunca chave reusada.
2. **Só pagamos cotação em USDC canônico da Base mainnet** (contrato oficial da Circle,
   conferido on-chain via `decimals()` antes da rodada — mini-antecipação da Fase 5).
   Token "parecido" = fonte reprovada no número 2, sem pagar.
3. **Só esquema `exact`** (valor fechado, autorização que não dá poder além do valor).
4. **Teto duro por compra: US$ 1,00.** Fonte que cobra mais = registrada como "cara demais",
   sem pagar. **Teto global da rodada 1: US$ 20,00** — o script PARA sozinho no teto.
5. **Payload comprado nunca é executado nem armazenado em claro** — só hash + tamanho +
   content-type no livro (D-11 vale aqui também). A validação (número 3) é estrutural.
6. **1 compra por fonte** na rodada 1. Repetição/aprofundamento só com novo OK.
7. Nós somos SÓ compradores: não precisamos de facilitator (quem liquida é o vendedor);
   nossa parte é assinar a autorização e conferir o resultado na chain.

## As etapas (as duas primeiras são 100% grátis)

| # | Etapa | O quê | Custa? | Pronto quando |
|---|---|---|---|---|
| T1 ✅ 21/08 | Fundação | carteira do censo `0x637f…B2DC`; config de rede dupla (testnet intacta); **coletor mainnet por pagador** (`main_pagador`: filtra `AuthorizationUsed` pela NOSSA carteira como authorizer) | grátis | smoke VERDE: chain 8453, USDC canônico on-chain, tx conhecida reencontrada pelo filtro; suíte 22/22 |
| T2 ✅ 21/08 | Descoberta | Bazaar da Coinbase: 3.000+ recursos, 604 domínios; filtros pré-comprometidos + seleção estratificada por preço; método/corpo/uso-30d capturados (x402.org sem discovery — 404) | grátis | `candidatos.json` versionado, 15 fontes, descartes contados por motivo |
| T3 ✅ 21/08 | Sondagem | 15 sondas sem pagar, wire V2 (header `payment-required` base64) + método do índice; tudo no livro em spans reais | grátis | **15/15 respondem · 15/15 cotações válidas · rodada ≈ US$ 0,77**; deriva de preço achada (dripstack 0,50 vs 0,20); MPP visto em produção |
| T4 ✅ 21/08 | 🔑 A rodada | 15 compras (tetos no SELETOR do SDK, fail-closed; `--vai` obrigatório); 13 entregaram; 2 falhas honestas (400 e re-402) | 💰 US$ 0,774 autorizado | compras gravadas com tripla completa |
| T5 ✅ 21/08 | Fechamento | coletor pagador: 13/13 casados na 1ª rodada; entregou ⇔ cobrou em 15/15; custo liquidado US$ 0,272; 2 authz pendentes vigiadas | grátis | **GATE 3 ✅** |

> **GATE 3:** os quatro números fecham com recibo linkado — respondem / aceitam pagamento /
> entregam payload válido / ficaram com o dinheiro — e o custo total sai por fonte.

## 🔑 O que depende de você (três coisas, em ordem)

1. **Aprovar este desenho e o orçamento** (US$ 20 na rodada 1, teto duro; até US$ 50 no
   total da fase se uma rodada 2 se justificar — com novo OK na hora).
2. **Financiar a carteira do censo** quando eu gerar o endereço (T1): mandar ~US$ 25 em
   USDC pela rede **Base** (da sua exchange ou carteira — te passo o passo a passo).
3. **O "vai" da rodada de compras** (T4) — DEPOIS de ver o relatório parcial da sondagem
   grátis, com a lista exata de quem vamos pagar e quanto.

## Custos declarados (regra transversal)

- **Grátis:** T1, T2, T3, T5 (descoberta, sondagem e leitura on-chain não pagam nada).
- **Real:** T4 — até US$ 20,00 em USDC (rodada 1) + o troco que sobrar fica na carteira.
- **Gas:** zero para nós no `exact` (o facilitator do vendedor submete a transação).
- **LLM:** zero — censo é script determinístico ("LLM nunca faz conta que código faz melhor").

## Riscos, ditos com franqueza

- **Pode ter POUCA fonte viva** (o ecossistema real é pequeno — nossos docs estimam
  ~US$ 28–42k/dia de comércio real no x402 inteiro). Se só 4 fontes passarem na sondagem,
  o relatório publica 4 — **o número baixo É o dado**, não um fracasso da fase.
- **Fonte maliciosa:** payload nunca executado, tetos duros, carteira isolada.
- **Preço anunciado ≠ preço cobrado:** é exatamente um dos achados que o censo existe para
  pegar (a cotação da sondagem vs a cobrança real da rodada).
- **Nossa carteira do censo é pública por natureza** (qualquer um vê as compras dela na
  chain) — sem problema: o censo será publicado mesmo (Fase 9).

## O que NÃO muda

Nenhuma migration nova prevista: o schema já é multi-rede (`network_caip2` em toda parte) e
o cursor do coletor é nomeado por rede. Se algo faltar, é sinal de erro de desenho — parar
e registrar em DECISOES antes de mexer no schema.
