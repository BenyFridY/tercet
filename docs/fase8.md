# Fase 8 — as telas: o blotter e o TCA (doc de design)

> ✅ **GATE 8 VERDE em 21/08/2026** — `scripts/fase8/mesa-telas.html` (gerada por
> `telas_build.py`, que CONFERE o gate em asserts antes de declarar verde): 85
> linhas reais, por agente e por tarefa, 13 compras do censo com recibo on-chain
> linkado, desperdício US$ 0,23/24 compras repetidas (regra do hash), árvore D-02
> somando por construção, TESTNET sempre rotulado. Aprovação vinculada D-14
> implementada e testada ("sim" para A não autoriza B); demo interativa em
> `aprovacao_demo.py`. Visual conferido em screenshot (headless) nas duas abas.

*Escrito em 21/08/2026, antes do código, pelo método (D-31). Fontes: PLANO (Fase 8),
design/produto/ (5 telas desenhadas em 20/08), D-02 (soma por árvore), D-11 (URL só
como hash NO LIVRO — a tela pode mostrar o domínio, que já é público nos resultados),
D-14 (aprovação vinculada), D-15 (custo completo), D-16 (núcleo). Custo: ~US$ 0,01
de teste (demo da aprovação). Nenhum gasto real.*

## O que é, em linguagem simples

Até aqui o livro responde perguntas via SQL e scripts. A Fase 8 faz as duas telas do
núcleo saírem do papel — **o blotter** (a mesa: cada compra, de que agente, em que
tarefa, com recibo, em que estado) e **o TCA** (quanto custou de verdade e quanto foi
**desperdício**) — alimentadas SÓ com o dado real do livro. Mock é proibido pelo
PLANO ("nunca mock") e é o nosso jeito: se a tela mostra $0,272, é porque o coletor
achou $0,272 na chain.

## A decisão de forma: página GERADA, não app com servidor

O v0 das telas é um **arquivo HTML autocontido gerado por script** a partir do livro
(`scripts/fase8/telas_build.py` → `scripts/fase8/mesa-telas.html`):

- **Por quê:** o gate pede que o blotter RESPONDA a pergunta com dado real — não
  pede servidor. Página gerada = zero infra nova pra vigiar, roda offline, dá pra
  anexar no e-mail, e regenerar é rodar um script ("scripts > notebooks").
- A interação que importa (trocar de aba, filtrar por agente, clicar na linha e ver
  a cadeia de eventos) é JS puro embutido com os dados JSON dentro da página.
- O visual segue `design/produto/Main.dc.html` e `TCA.dc.html` (tokens: fundo
  #0B0D0F, Space Grotesk + JetBrains Mono, verde #28A87F, cards translúcidos) — o
  design "sai do papel" literalmente.
- App com servidor (FastAPI/etc.) fica para quando houver segundo usuário — decisão
  registrada, não esquecida.

## O que cada tela responde (com o dado que EXISTE hoje)

**Blotter** — "o que meus agentes compraram este mês?":
- Uma linha por request do livro: hora UTC, recurso (hash curto + domínio quando
  conhecido dos resultados públicos do censo), agente (`span.agent_ref` real:
  mesa-censo, driver-t3, driver-t4, agente-t6…), tarefa (span raiz da árvore),
  trilho, valor, **recibo** (tx on-chain quando liquidado), estado.
- Estados DERIVADOS do livro, nunca digitados: `liquidado`, `pago-sem-entrega`
  (caos da Fase 1 — o kill-after-settle), `entregue-sem-cobrar` (as 2 do censo que
  expiraram), `autorizado-pendente`, `sem-pagamento` (sondas/grátis), `dedup ×N`.
- **Dinheiro de teste vs real SEMPRE rotulado** (badge TESTNET na Sepolia): somar
  USDC de mentira com USDC de verdade numa tela seria mentir com números.
- **Orçamento por árvore (D-02):** a tarefa `censo.rodada1` mostra a soma dos 15
  filhos batendo com o gasto da rodada — a mesma invariante dos testes da Fase 2,
  agora visível.

**TCA** — "quanto custou de verdade e quanto foi desperdício?":
- Custo por entrega por fonte (o número da Fase 7), custo total D-15 (preço; gas é
  do facilitator no x402 — mostrado como informação, não somado ao nosso custo).
- **Desperdício, dois detectores (as colunas existem desde a migration 0001):**
  1. **Dedup por `resource_key_hash`:** o mesmo recurso comprado N vezes;
  2. **Frescor por `body_sha256`:** das N compras, quantas trouxeram conteúdo JÁ
     VISTO (byte a byte igual) — pagou de novo pelo mesmo byte.
  Dado real: um recurso foi entregue **21× com 1 conteúdo distinto** (o brinquedo
  do caos) — 20 compras não trouxeram byte novo. Desperdício rotulado com a régua
  dita: "igual byte a byte"; conteúdo dinâmico legítimo (ex.: fato do dia que muda)
  NÃO é desperdício e a régua separa isso pelo hash.

## Aprovação vinculada (D-14) — o fluxo, não só a tela

Acima de um teto, o agente NÃO assina sozinho: pede aprovação do humano — e a
aprovação é **vinculada à cotação exata** (hash de payTo + valor + ativo + rede +
recurso), não um "sim" genérico que valeria para qualquer compra depois.

- `src/mesa/aprovacao.py`: `escopo_da_cotacao()` (o hash), `AprovacaoVinculada`
  (quem, quando, escopo), verificação de que a aprovação bate com a cotação.
- No seletor: política `teto_aprovacao_minor` — acima disso, chama um callback
  humano (o padrão `input_required`/elicitation do MCP, D-30; no v0 o callback é o
  terminal). Sem aprovação → recusa `precisa-aprovacao` (fail-closed, D-05: pedir
  aprovação não bloqueia o resto da rodada).
- A aprovação entra NO LIVRO: `authz.principal_ref` + `principal_evidence` (as
  colunas existiam vazias desde a 0001, esperando por isso).
- Demo real: compra testnet acima do teto SÓ passa com aprovação no terminal;
  teste prova que aprovação da cotação A **não** autoriza a cotação B.

> **GATE 8:** o blotter responde "o que meus agentes compraram este mês, por
> agente, por tarefa, com recibo — e quanto foi desperdício?" com dado real.

## Riscos e limites, ditos

- **n pequeno e dados de dogfood:** as telas de hoje mostram ~85 requests. A tela
  não finge escala — os números são os do livro.
- **Domínio em claro NA TELA:** D-11 protege o LIVRO (hash). Os domínios do censo
  já são públicos em `sondagem_resultado.json` (commitado); a tela usa esse mapa
  público hash→domínio. Recurso sem mapa aparece como hash curto.
- **Página estática:** dado congela no build (carimbo "gerado em" na tela);
  regenerar é 1 comando. Não é tempo real e diz isso na cara.
