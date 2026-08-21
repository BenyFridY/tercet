# Fase 6 — o custo no painel + o segundo trilho (doc de design)

> ✅ **GATE 6 VERDE em 21/08/2026** — (a) compra testnet real apareceu no Jaeger com
> `purchase.amount=0.010000` e o tx hash da liquidação (verificado pela API, não a
> olho; painel: http://localhost:16686, serviço `mesa-fase6`); (b) uma chamada LLM
> REAL (US$ 0,000858) virou claim `rail='invoice'` e reconciliou contra o extrato
> (sintético rotulado — o CSV real do console substitui) com deriva ZERO, sem
> nenhuma migration. `pix` reservado no vocabulário (D-29). Corrente: 429 elos
> íntegros. Extrator de tx corrigido no caminho (regex genérico pegava o NONCE —
> campos nomeados primeiro).

*Escrito em 21/08/2026, antes do código, pelo método do programa (D-31). Fontes:
PLANO (seção Fase 6), D-28 (vocabulário do OTel #443), D-29 (pix no vocabulário),
D-30 (mapeamento por backend). Custo da fase: **zero**.*

## O que é, em linguagem simples

Duas promessas antigas viram realidade:

1. **O custo de compra aparece no MESMO painel onde se vê o custo de tokens.**
   Hoje, quem opera um agente vê latência e tokens no painel de observabilidade
   (Jaeger, Datadog, LangSmith…), mas o que o agente COMPROU não aparece em lugar
   nenhum. Nossos spans já viajam por OpenTelemetry — a fase pendura neles os
   atributos de custo (`purchase.*`: valor, moeda, trilho, referência da liquidação)
   e exporta para um painel de verdade. Quem olhar o trace da tarefa vê: este passo
   custou US$ 0,20, pago, confirmado na chain, tx tal.

2. **O livro engole um gasto que NÃO é cripto — sem mudar o schema.** Desde a
   primeira migration o schema jura ser agnóstico de trilho. A prova: o custo REAL
   de LLM do nosso próprio agente (as chamadas à API da Anthropic têm preço
   conhecido por token) entra como trilho `invoice`, e a fatura/extrato de uso
   fecha contra o livro do mesmo jeito que a blockchain fecha o x402.
   A tese "atribuição multi-trilho" deixa de ser slide.

## Por que isso importa pro produto

O risco nº 1 (D-26) são os donos do ponto de instrumentação (Langfuse, Datadog,
LangSmith) adicionarem custo de compra antes de nós. A resposta é sermos o PRIMEIRO
a falar a língua deles: um exportador que qualquer backend OTel entende, alinhado ao
vocabulário que o OTel está padronizando no #443 (`gen_ai.usage.cost.*` — D-28).

## Os componentes

1. **`src/mesa/exportador.py`** — enriquece os spans de compra com atributos
   `purchase.*` (namespace nosso, 1 compra = 1 span):
   `purchase.amount` (decimal string), `purchase.currency` ("USDC"),
   `purchase.rail` ("x402"), `purchase.network` (CAIP-2),
   `purchase.settlement_ref` (o tx hash — a REFERÊNCIA que nenhum concorrente tem),
   `purchase.resource_hash` (D-11: nunca a URL). Alinhamento com o #443 documentado
   em tabela (o que vira `gen_ai.usage.cost.*` quando/se o PR fechar).
2. **Painel local de verdade: Jaeger** (docker, grátis, 1 container). Os spans saem
   por OTLP para o Jaeger AO MESMO TEMPO que continuam indo pro livro (o processor
   do livro não muda). O GATE se verifica pela API do Jaeger, não por screenshot.
3. **Tabela de mapeamento por backend** (doc + código): OTLP genérico (Jaeger,
   Datadog) direto; LangSmith aceita custo em run de tool; Langfuse exige modo
   próprio (D-30). Implementamos o OTLP genérico; os outros ficam mapeados.
4. **O trilho `invoice`** — custo real de LLM do nosso agente:
   - na hora do run, cada resposta da API traz `usage` (tokens); o custo sai da
     tabela de preço pinada (`registro_precos_llm.json` — mesmo espírito do registro
     de ativos: pinado, versionado, com fonte e data);
   - entra no livro como request+quote+authz com `rail='invoice'`,
     `transport='function'`, pendurado no span da chamada — schema INTOCADO;
   - a "liquidação" do trilho invoice é o extrato/fatura do provedor: um CSV entra
     como settlement + legs casando por (dia, modelo) — chave de join do trilho.
     Com o CSV REAL exportado do console da Anthropic (ação sua de 2 min, opcional),
     a reconciliação fecha contra documento externo; sem ele, fecha contra uma
     amostra ROTULADA como sintética (D-12) construída na MESMA forma do console.
5. **`pix` entra no vocabulário de `rail`** (D-29) — constante + doc, preparando a
   consulta pública do BCB (set–out/2026). Sem implementação: só o nome reservado.

## As etapas

| # | Etapa | O quê | Pronto quando |
|---|---|---|---|
| T1 | Atributos | `purchase.*` nos spans de compra (censo + agente) + tabela de alinhamento #443 | teste: span de compra carrega os atributos; suíte verde |
| T2 | O painel | Jaeger local (docker) + export OTLP em paralelo ao livro | **GATE 6a:** consulta à API do Jaeger acha o span da compra com `purchase.settlement_ref` |
| T3 | O 2º trilho | preço LLM pinado + custo real do agente como `rail='invoice'` + ingestor de CSV + reconciliação (dia, modelo) | **GATE 6b:** trilho não-cripto reconcilia SEM migration nova |
| T4 | Fechamento | `pix` no vocabulário; docs; DIARIO; commit | GATE 6 completo |

## Custos declarados

- **Dinheiro: zero.** Jaeger é local e grátis; o custo LLM registrado é o que o
  agente JÁ gastou (e gastará em runs normais) — nada roda só para gastar.
- **Ação sua (opcional, 2 min):** exportar o CSV de uso do console da Anthropic
  para a reconciliação fechar contra documento 100% externo. Sem ele a fase fecha
  com amostra rotulada.

## Riscos, ditos com franqueza

1. **Preço de LLM muda** (o intro pricing do sonnet-5 acaba 31/08) — por isso o
   preço é PINADO com data e fonte, nunca hardcoded solto; reconciliação contra o
   CSV real é o que pega deriva de preço (mesmo achado do censo, outro trilho).
2. **Docker precisa estar de pé** para o Jaeger (mesmo runbook do Postgres).
3. **#443 ainda aberto** — nosso namespace `purchase.*` é nosso; a tabela de
   alinhamento existe para migrar barato se o vocabulário oficial fechar diferente.
