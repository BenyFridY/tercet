# Fase 10 — o passaporte do pagador single-buyer (doc de design)

> ✅ **GATE 10 VERDE em 23/08/2026** — o ciclo completo demonstrado
> (`scripts/fase10/gate10_demo.py`, tudo por assert): caos RECUSADO
> (nonce-reusado + 5 órfãos), mcp RECUSADO (1 órfão — o achado da fase), censo
> ACEITO e comprou o `/lote` de 0,10 na testnet com os termos mudados pelo
> passaporte; recusas ANTES de cobrar; ladrão de arquivo derrotado pela prova de
> posse; coletor casou as compras novas por (authorizer, nonce). Verificador
> independente: nível 1 offline VERDE; nível 2 confirmou as 13 liquidações na Base
> MAINNET com varredura sem liquidação escondida; métrica adulterada → VERMELHO.
> 15 testes puros novos; custo real zero.

*Escrito em 23/08/2026, antes de qualquer código, pelo método do programa (D-31).
Fontes: PLANO.md (seção Fase 10), DECISOES.md (D-08, D-12, D-06), e a infraestrutura
que a Fase 4 deixou pronta (canonicalização RFC 8785, assinatura recuperável,
fechamento de período). Esta fase roda 100% em testnet — custo real: zero.*

## O que é esta fase, em linguagem direta

Hoje, quando o nosso agente chega num vendedor novo, ele é um estranho: o vendedor
cobra pré-pago, no teto mínimo, porque não tem como saber se esse pagador honra o que
assina. Mas o livro do mesa **já sabe**: registra cada autorização que assinamos, cada
liquidação na chain, cada nonce, cada entrega. A Fase 10 transforma esse histórico em
um **documento portátil e assinado** — o passaporte — que o comprador apresenta ao
vendedor, e o vendedor **verifica offline, sem confiar na gente**, e decide dar termos
melhores: teto maior, pós-pago, lote em vez de varejo.

É crédito comercial mecanizado: **quem tem histórico paga depois; quem não tem, paga
antes** (D-08).

**O que preciso de você: nada.** Fase inteira em testnet (o facilitator paga o gas,
USDC de faucet), nenhuma ação externa, nenhuma publicação.

## As quatro alegações (D-08, na letra)

O passaporte atesta, sobre o livro do PRÓPRIO comprador, para UM `payer_ref` numa
janela declarada:

| # | Alegação | Como sai do livro |
|---|---|---|
| 1 | **Taxa de liquidação sobre autorização** | `authz` do payer × quantas têm `settlement_leg`. Publicada como dois inteiros (autorizações, liquidadas) — o verificador faz a divisão, nós não publicamos float. |
| 2 | **Nonce nunca reusado** | contagem de `(payer, nonce)` duplicados nas `rail_evidence` — a mesma chave da reconciliação da Fase 1. |
| 3 | **Nenhuma entrega consumida sem pagar** | requests entregues com autorização cuja validade EXPIROU sem liquidar (= o vendedor não pode mais cobrar; o dinheiro nunca vai sair). Autorização viva pendente NÃO é calote — é cobrança em curso, e aparece em campo separado. |
| 4 | **Reconciliação fechada** | órfãos chain→livro inexplicados = 0 (toda liquidação do payer na chain tem par no livro). |

**Nuance da alegação 3, dita com franqueza:** `uncollected` (vendedor entregou sem
nunca cobrar) NÃO conta contra o pagador — é escolha do vendedor. O que conta é
autorização assinada + entrega consumida + validade morta sem liquidação.

## Honestidade estrutural (D-12) — o que o passaporte NÃO consegue provar

Um atestado sobre o próprio livro tem uma assimetria que o documento declara em campo
próprio (`ressalvas`), em vez de esconder:

- **O que a chain confirma (nível 2):** toda liquidação alegada existe mesmo — cada tx
  da evidência tem `AuthorizationUsed(payer, nonce)` on-chain. E mais forte: a chain é
  o registro COMPLETO das liquidações daquele endereço — **esconder compra liquidada é
  detectável** por varredura (liquidação na chain fora da lista → VERMELHO).
- **O que ninguém consegue conferir:** autorizações assinadas que NUNCA liquidaram não
  deixam rastro na chain. O **denominador da taxa é auto-reportado** — um pagador
  mal-intencionado poderia omitir autorizações que assinou e abandonou. O passaporte
  declara isso; o vendedor precifica a ressalva (e é exatamente por isso que a versão
  de REDE do passaporte, D-08 v4, precisaria de vendedores observando — fora do v0).
- **A janela é visível e escolhida pelo emissor.** Janela parcial pode esconder um
  período sujo — por isso ela é campo assinado do payload e a política do vendedor
  exige mínimo de compras e cobertura.

## Quem assina — e por que isso importa

O passaporte é assinado **pela chave do próprio `payer_ref`** (a "mesa" single-buyer
roda NO comprador — a chave operacional é a dele). Isso compra duas propriedades de
graça:

1. **Ninguém veste histórico alheio**: recuperar o assinante e comparar com o sujeito
   é uma operação offline; passaporte de terceiro não valida.
2. **Prova de posse ao vivo**: apresentar o arquivo não basta (arquivo vaza). O
   vendedor exige uma **prova fresca**: assinatura sobre
   `{hash do passaporte, rota, timestamp}` com a mesma chave, janela de 60s. Sem
   estado de sessão no vendedor.

**Formato próprio, com justificativa registrada:** D-27 ("nunca formato próprio")
vale para RECIBOS, onde três padrões já nasceram. Para atestação de pagador não
existe padrão nascido — `mesa-passaporte/v0`, versionado, é a abertura da vaga, não
uma reinvenção. Assinatura: payload canônico RFC 8785 → sha256 → EIP-191 — as mesmas
regras normativas de `docs/canonicalizacao.md`, que o verificador da Fase 4 já
reimplementa sem importar o mesa.

## O que viaja no passaporte

```
{ "formato": "mesa-passaporte/v0",
  "payload": {
    "sujeito":   { "payer_ref": "0x…", "rede": "eip155:84532", "rail": "x402" },
    "janela":    { "de": "…Z", "ate": "…Z" },
    "metricas":  { "autorizacoes": N, "liquidadas": M, "nonces_reusados": K,
                   "entregas_sem_pagar": E, "cobrancas_pendentes": P,
                   "orfaos_chain_inexplicados": O },
    "evidencia": [ { "tx", "nonce", "amount_minor", "asset_contract", "pay_to" } … ],
    "integridade": { "period_close": [ { "data", "merkle_root" } … ] },
    "ressalvas": [ "denominador auto-reportado", … ],
    "emitido_utc": "…Z" },
  "assinatura": "0x…" }
```

`evidencia` lista SÓ o que é público na chain de qualquer jeito (tx, nonce, valores,
payTo). Nenhuma URL em claro — D-11 continua valendo. `integridade` referencia as
raízes de Merkle carimbadas (RFC3161 + OTS) dos períodos fechados que cobrem a janela:
o terceiro sabe que o livro por trás já existia carimbado antes da emissão.

## Os dois níveis de verificação

| Nível | Quem | Precisa de | Responde |
|---|---|---|---|
| 1 — offline | o vendedor, na hora | nada (nem RPC) | assinatura ⇔ sujeito; contagens ⇔ evidência; nonces da evidência sem duplicata; prova de posse fresca |
| 2 — contra a chain | auditor cético | um RPC | cada tx alegada existe com `AuthorizationUsed(payer, nonce)`; varredura não acha liquidação do payer FORA da lista |

O GATE exige o nível 1 (o vendedor muda os termos offline). O nível 2 fica no
verificador standalone, como na Fase 4.

**A EMISSÃO é online, de propósito:** quem emite é o dono do livro, na máquina do
livro — e a emissão atribui cada liquidação sem par ao seu authorizer real via
`AuthorizationUsed` na chain, para que `orfaos_chain_inexplicados` seja DO payer, não
da rede inteira. Offline é a obrigação do VERIFICADOR, não do emissor.

## O vendedor de brinquedo e a mudança de termos

Duas rotas no vendedor x402 de teste:

- **`/unidade`** — aberta a estranhos: 0,01 USDC por chamada, pré-pago (`exact`).
- **`/lote`** — 0,10 USDC (o "teto maior" do gate): **só para portador de passaporte
  válido** pela política do vendedor. Sem passaporte → 403 com a explicação.

A política do vendedor (constantes nomeadas, decisão DELE, não do formato):
taxa de liquidação ≥ 80% · nonces reusados = 0 · entregas sem pagar = 0 ·
órfãos inexplicados = 0 · mínimo de 3 compras · emitido há < 30 dias · prova de
posse fresca (60s).

## O ciclo do gate, com o dado REAL que o livro já tem

O livro de hoje entrega os dois lados da demo sem fabricar nada (conferido em 23/08
contra o banco E contra a chain — os 6 settlements sem par do livro foram atribuídos
por `AuthorizationUsed` on-chain):

| Payer | Histórico real | Veredito esperado da política |
|---|---|---|
| `0xDc25…A985` (comprador do caos, Fase 1, testnet) | 32 autorizações, 28 liquidadas, **1 nonce reusado** (o replay deliberado da tabela-oráculo) e **5 liquidações on-chain sem par no livro** (T2 pré-livro + fantasma do caos) | **RECUSADO** — o passaporte é honesto a ponto de reprovar a carteira do próprio dono |
| `0x6C32…E6AB` (servidor MCP, Fase 2, testnet) | 3/3 liquidadas, zero reuso — mas **1 órfão on-chain** (compra de teste da T4 fora da instrumentação) | **RECUSADO** — achado desta fase: a carteira que parecia limpa no banco não é limpa contra a chain |
| `0x637f…B2DC` (carteira do censo, Fase 3, **mainnet**) | 15 autorizações, 13 liquidadas (86,7% ≥ 80%), zero reuso, zero órfão, zero calote — história REAL com dinheiro real | **ACEITO** — compra o `/lote` |

**Nota de rede:** o passaporte aceito atesta história na Base MAINNET e o vendedor de
brinquedo roda na testnet — reputação ganha numa rede usada para termos em outra é
decisão do vendedor (como aceitar um bureau de crédito estrangeiro), e a demo declara
isso. A compra do `/lote` é assinada pela MESMA chave do censo, na testnet (a EOA vale
em qualquer chain EVM); se a carteira do censo não tiver USDC de teste, o fundo entra
por uma compra x402 normal (vendedor de recarga com `payTo` = censo) — o facilitator
paga o gas, e a recarga cai no livro como qualquer compra.

> **GATE 10:** o vendedor de brinquedo valida a atestação OFFLINE e muda os termos
> (teto maior) para o portador — o ciclo completo demonstrado. Na prática: o payer
> limpo compra o `/lote` de 0,10 USDC na testnet e a compra cai no livro como
> qualquer outra; o payer sujo é recusado COM o motivo; e um bit adulterado no
> passaporte é detectado pelo verificador.

## As etapas

| # | Etapa | O quê | Pronto quando |
|---|---|---|---|
| T1 | Este doc | design antes do código (D-31) | você está lendo |
| T2 | O núcleo | `src/mesa/passaporte.py`: montar (função pura sobre linhas do livro), assinar, verificar, prova de posse, política | testes puros: adulteração → VERMELHO na métrica certa; assinatura de terceiro → recusa; replay do dono → REPORTADO, não escondido |
| T3 | O verificador | `verificador/verificar_passaporte.py` (sem imports do mesa) — nível 1 + nível 2 opcional com RPC | dump limpo VERDE; 1 bit virado VERMELHO; tx fantasma na evidência → VERMELHO no nível 2 |
| T4 | O vendedor | `scripts/fase10/vendedor_lote.py`: `/unidade` aberta, `/lote` só com passaporte + prova fresca | sem passaporte 403; com passaporte inválido 403 com motivo; com válido → cotação x402 de 0,10 |
| T5 | O ciclo | `scripts/fase10/gate10_demo.py`: emite os 2 passaportes reais, roda o ciclo na testnet, registra | GATE ✅: recusa honesta + compra do lote liquidada on-chain + tudo no livro; DIARIO/PLANO atualizados |

## Custos declarados

- **Dinheiro real: zero.** Testnet (USDC de faucet; gas é do facilitator no `exact`).
  A demo consome ~0,11 USDC de teste por rodada.
- **LLM: zero** — tudo código determinístico.

## Riscos, ditos com franqueza

- **O passaporte pode virar teatro** se a política do vendedor for frouxa — por isso
  os limiares são constantes nomeadas e o teste do gate inclui a RECUSA, não só o
  aceite.
- **Prova de posse com janela de 60s** é proteção de brinquedo contra replay do
  header; suficiente para o gate, declarada como tal. Produção pediria desafio do
  vendedor (nonce dele), registrado como evolução — não construir antes de existir
  vendedor real (mesma lógica do D-17).
- **`payer_ref` de trilho não-EVM** (invoice, ap2) não tem chave para assinar nem
  chain para conferir — o passaporte v0 é `rail = x402` e diz isso no payload, em vez
  de fingir generalidade que não foi testada.
