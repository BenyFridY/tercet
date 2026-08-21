# Diário de bordo — mesa

> **Para que serve este arquivo:** cada tarefa concluída ganha uma entrada em linguagem direta —
> o que era, o que foi feito, o que ficou provado, onde está o código — e o topo sempre diz
> **o que vem agora**. A especificação formal das 12 fases está no PLANO
> (`Documents\x402\PLANO.md`); aqui é a narrativa, para acompanhar o ritmo sem reler tudo.
> Atualizado a cada tarefa. Última atualização: **21/08/2026**.

## O projeto em 30 segundos

Agentes de IA compram coisas (dados, APIs, serviços) pagando sozinhos via x402. **Ninguém registra
isso direito**: o que foi comprado, quem autorizou, quanto custou de verdade, se o dinheiro saiu
mesmo, se a entrega veio. A mesa é esse registro — o **livro** — com três pontas que precisam
bater: o que o agente pediu, o que ele autorizou pagar, e o que a blockchain diz que liquidou.
Toda diferença entre as três pontas vira um **veredito** nomeado (entregue-sem-cobrar,
pago-sem-entrega, replay…). Nunca tocamos em chave ou dinheiro — só observamos e provamos.

---

## ⏭️ AGORA: Fase 5 — engenharia ✅ COMPLETA (21/08); GATE 5(b) espera as SUAS submissões

**O que fechou hoje (GATE 5a ✅):** os 3 golpes contra agente — payTo trocado, token
sósia, decimais mentidos — são recusados por funções PURAS e OFFLINE
(`mesa/checagens.py`, registro pinado lido dos contratos 1×), com motivo nomeado e
teste reproduzível sem rede. Integradas no seletor do censo e no `make_client`.
O **vínculo reverso** N2 (`/.well-known/x402-payto` assinado pela chave do payTo) está
implementado (nosso vendedor publica; verificador offline) e a sonda no censo deu o
dado da proposta: **0/15 vendedores publicam vínculo** — evidência no livro.

**🔑 GATE 5(b) — as 5 submissões SUAS (textos todos prontos em `notes/`):**
1. Issue do relatório de conformance no coinbase/x402 (`x402-mcp-conformance-report.md`) — POSTAR PRIMEIRO;
2. PR do conserto do SDK Python (`sdk-python-fix-pr.md` — NC-1 confirmado vivo no main `dd927a2`; linka a issue 1);
3. Proposta da extensão payTo-binding (`x402-extension-payto-binding.md`);
4. Security Consideration no draft de DNS discovery (`x402-dns-discovery-security-consideration.md`);
5. Comentário no OTel #443 (`otel-443-comment-draft.md` — D-28, já estava na fila).

**Git:** commits `057a30b` (fases 1–4) e `e7a3311` (abertura da 5) na `main`.

**Fase 4 (fechada hoje):** o livro agora prova a si mesmo — corrente de hash com 385
elos íntegros, período fechado com carimbo duplo (freeTSA + OpenTimestamps 4/4), e um
verificador offline independente que pegou 1 bit adulterado na linha exata. De quebra:
**primeira implementação pública** da extensão oficial `offer-and-receipt`, e o schema
provou o agnosticismo — MPP real e AP2 ingeridos sem migration.

**Vigilância — atualização 21/08 (revisão de sanidade):**
- ✅ **Fase 3 ENCERRADA:** as 2 autorizações pendentes (stableenrich US$ 0,002,
  dripstack US$ 0,50) **EXPIRARAM sem liquidação** — validBefore no passado, não podem
  mais ser usadas on-chain. Registrado como `authz_event(kind='failed')` append-only
  (`scripts/fase3/expirar_pendentes.py`). O achado do censo virou definitivo: as 2
  fontes que falharam não cobraram e NÃO PODEM mais cobrar. Rodada 1 = FINAL.
- Fase 4 (segue): upgrade da prova OTS quando o Bitcoin ancorar (`kind='ots-upgrade'`),
  e fechamento diário do período (`fechar_periodo.py`).

**Também na fila (ações suas, 5 min cada):** postar o relatório de conformance no
coinbase/x402 e o comentário no OTel #443 — os dois textos prontos em `notes/`.

---

## Fase 4 — o recibo verificável ✅ GATE 4 VERDE (21/08)

### T1–T5 ✅ 21/08 — a fase inteira em um dia (tudo grátis)

- **O que era:** o livro deixar de ser confiável "porque nós dizemos" e passar a provar
  a si mesmo, com um terceiro verificando sem confiar na gente.
- **Como ficou:** regras de canonicalização escritas ANTES do código
  (`docs/canonicalizacao.md`, normativo — RFC 8785, tipos pinados, mutáveis excluídos);
  migrations 0002 (eventos: fecha a exceção do D-06) e 0003 (corrente + fechamento);
  elo de hash em TODA escrita nova na mesma transação; backfill determinístico das
  Fases 1–3 (375 linhas) com a ordem gravada no genesis; período `2026-08-21` fechado
  (seq 0..375 — contém o censo) com raiz de Merkle carimbada por **freeTSA** (RFC3161,
  cert embutido no token) e **OpenTimestamps** (4/4 calendários);
  `verificador/verificar.py` (não importa o mesa — o terceiro confia no que LÊ) validou
  o dump e o `gate4_teste.py` provou: 1 bit virado na seq 188 → VERMELHO acusando a
  seq 188.
- **T5, os 3 formatos (D-27):** emitimos a extensão OFICIAL `offer-and-receipt`
  (EIP-712, signer==payTo) sobre uma venda real NOSSA já liquidada — **primeira
  implementação pública da extensão** (aprovada com zero implementações). Ingerimos um
  desafio **MPP real** capturado ao vivo do censo (método tempo, chain 4217) como
  rail='mpp' e um mandate **AP2 sintético rotulado** (D-12) como rail='ap2' — os dois
  SEM migration: o agnosticismo de trilho deixou de ser promessa.
- **Correção de desenho (registrada):** o doc da fase previa emitir recibos sobre as 13
  compras do censo; o spec diz que quem assina é o VENDEDOR — corrigido para a venda em
  que somos o vendedor. O achado do censo ficou: **0/15 vendedores emitem a extensão.**
- **Percalços do dia:** o CLI `ots` quebra no Windows (bitcoin.rpc → ctypes/OpenSSL) —
  carimbamos pela LIB com o mesmo fluxo; o messageImprint do RFC3161 é o **hash** do
  dado carimbado (não o dado) — verificador corrigido; deriva de canônico entre fases
  ("GET url" vs url crua) detectada e tratada no matching.
- **Onde:** `src/mesa/integridade.py`, `carimbo.py`, `recibo_x402.py`;
  `scripts/fase4/` (backfill, fechar_periodo, ots_stamp, exportar_periodo, gate4_teste,
  formatos_run); `verificador/verificar.py`; 33 testes verdes.

---

## Fase 3 — o censo comprador ✅ GATE 3 VERDE (21/08)

### T4–T5 ✅ 21/08 — a rodada paga e o fechamento (as primeiras compras reais do livro)

- **O que era:** comprar 1× de cada fonte aprovada na sondagem, com dinheiro real na Base
  mainnet, e fechar os 4 números com recibo on-chain.
- **Aprovações:** desenho+orçamento OK; Beny financiou US$ 10 (Coinbase → Base,
  self-custody); "vai" explícito dado. Nada rodou antes disso.
- **Como protegeu o dinheiro:** os tetos moram NO SELETOR do SDK (a função que escolhe a
  cotação roda ANTES de assinar — cotação fora dos limites = compra abortada, fail-closed);
  `--vai` obrigatório no script (sem ele é ensaio); cada compra gravada no livro assim que
  o span dela fecha (processo morrer no meio perde no máximo a compra em voo).
- **O que aconteceu:** 15 compras assinadas, US$ 0,774 autorizado. **13 entregaram (200 +
  corpo). As 2 que falharam NÃO cobraram** — stableenrich devolveu 400 (nosso corpo de
  exemplo `{}` era inválido pra ela) e dripstack devolveu OUTRO 402 depois de pago
  (re-cobrança — achado!). Coletor mainnet (modo pagador): 13 `AuthorizationUsed` da nossa
  carteira, 13/13 casados com o livro na 1ª rodada. Entregou ⇔ cobrou em 15/15 casos.
- **Custo real on-chain: US$ 0,272** (não 0,774 — autorizado ≠ liquidado; a diferença é
  exatamente o que o livro existe pra distinguir). Saldo confere: 10 − 0,272 = 9,728 ✓.
- **Nuance registrada:** as 2 autorizações não-liquidadas continuam VIVAS até o
  validBefore — "pendente", nunca "não cobrou e acabou". Vigilância nos próximos dias.
- **Onde:** `scripts/fase3/rodada.py` (T4), `scripts/fase3/fechamento.py` (T5),
  `censo_fechamento.json` (os 4 números por fonte, com tx hash de cada liquidação).

### T1–T3 ✅ 21/08 — fundação, descoberta e sondagem (tudo grátis, nada gasto)

- **T1 (fundação):** carteira EXCLUSIVA do censo criada (`0x637f…B2DC`, chave fora do
  OneDrive); config de rede dupla (a testnet continua intacta — 22 testes verdes); coletor
  ganhou o **modo comprador** (`mesa.collector main_pagador`): na mainnet filtramos
  `AuthorizationUsed` pela NOSSA carteira como authorizer — não precisamos saber o payTo de
  cada vendedor. Smoke na mainnet VERDE (`scripts/fase3/coletor_smoke.py`): chain id 8453,
  USDC canônico conferido NO CONTRATO (decimals=6, symbol=USDC), e uma tx conhecida de
  terceiros reencontrada pelo filtro de authorizer. Bônus: ~1.128 `AuthorizationUsed` em
  8 minutos de Base — tráfego EIP-3009 real existe em volume.
- **T2 (descoberta):** `scripts/fase3/descoberta.py` → `candidatos.json` versionado.
  O Bazaar da Coinbase tem **3.000+ recursos e 604 domínios únicos** (maior que nossa
  estimativa; corte de paginação LOGADO, nunca silencioso). Seleção com filtros
  pré-comprometidos (USDC canônico por ENDEREÇO, Base mainnet, exact, ≤ US$ 1) e
  **estratificada por faixa de preço** — só "mais barato primeiro" enchia a lista de demos
  de US$ 0,001; as quotas por faixa trouxeram APIs de verdade (Arkham, screenshots, feeds).
  O índice publica uso real por recurso (`l30DaysTotalCalls`/`UniquePayers`) — capturado
  como contexto. O facilitator x402.org NÃO tem endpoint de discovery (404) — 1 índice só.
- **T3 (sondagem):** `scripts/fase3/sondagem.py` — 15 sondas sem pagar, tudo no livro
  (requests + quotes pendurados em spans reais, `mesa-censo`). **15/15 respondem, 15/15
  cotações válidas, custo estimado da rodada: US$ 0,774.**
- **As lições do dia (método):**
  1. A primeira sonda achou só 1/15 válidas — e o erro era NOSSO: no wire V2 sobre HTTP a
     cotação vem no **header `payment-required` (base64)**, não no corpo (que vem `{}`).
     Desconfiar da régua antes de reprovar o mundo. A sonda agora lê header-primeiro.
  2. Fontes POST-only respondem 405 ao GET — o método certo vem do próprio índice
     (`extensions.bazaar.info.input`). Sondar com o método anunciado.
  3. Repeti o erro da Fase 2 com a FK request→span (gravar o livro DENTRO do span aberto):
     o padrão é sondar capturando IDs e gravar DEPOIS da árvore fechar. Padrão anotado.
- **Achados de censo (já valem antes de pagar):** dripstack.xyz cota **US$ 0,50** com
  US$ 0,20 anunciado no índice (deriva de preço — número que o censo existe pra pegar);
  onesource e dripstack também falam **MPP** (`WWW-Authenticate: Payment`, method
  tempo/stripe) no MESMO endpoint — o trilho rival da watchlist (D-27) em produção,
  convergindo multi-trilho exatamente como o schema apostou.

---

## Fase 2 — a árvore e o agente real ✅ GATE 2 VERDE (21/08)

### T6 ✅ 21/08 — o agente decidiu comprar (e a fase fechou)
- **O que era:** a prova final do gate. Até aqui quem comprava era roteiro nosso; o produto
  promete medir AGENTE — um LLM que decide sozinho se e quando vale pagar.
- **O que foi feito:** `src/mesa/agente.py` (D-33 — do zero, dentro do repo): agente Claude
  (`claude-sonnet-5`, Tool Runner oficial da Anthropic) com DUAS ferramentas — notas locais
  gratuitas (que não sabem a resposta) e a fonte paga via MCP (0,01 USDC, preço declarado na
  descrição da ferramenta). A tarefa pede economia: "só use a paga se a grátis não resolver".
- **O que ficou provado:** o agente tentou a grátis primeiro, DECIDIU comprar exatamente 1
  vez, e a resposta final dele narra o raciocínio de custo ("foi necessário fazer 1 única
  chamada à fonte paga — custo: 0,01 USDC"). No livro: árvore íntegra de 6 spans, a compra
  no span exato da decisão (`ferramenta.fonte-paga`), a compra DELEGADA do servidor presente
  (aninhada não desapareceu), soma batendo em toda altura, e o coletor casou as 2 liquidações
  na chain na 1ª tentativa. **GATE 2 fechado com asserts** (`scripts/fase2/agente_run.py`).
- **Custo do run:** centavos de API + 0,02 USDC testnet.

### T5 ✅ 20/08 — a suíte de conformance (e a descoberta que corrigiu o mapa)
- **O que era:** escrever a suíte de testes de conformidade de pagamento-em-MCP que ninguém
  escreveu, rodando contra ≥2 implementações reais, com ≥1 não-conformidade documentada.
- **A descoberta antes do código:** reler as fontes revelou que o **SEP-2007 está DORMENTE**
  (PR fechado em 24/06/2026, sem sponsor — o "-32402" dos nossos docs vinha de texto morto).
  O texto vivo é o **spec de transporte MCP da própria x402 Foundation**. Suíte re-ancorada
  nele; docs corrigidos (D-34). Ler a fonte antes de acusar salvou o relatório inteiro.
- **O que a suíte achou:** **Python SDK 2.20.0 quebrado contra o MCP SDK 2.x** — NC-1: o
  wrapper de servidor importa módulo que não existe mais; NC-2: o cliente não reconhece o
  "pague primeiro" no formato novo e trata ferramenta paga como grátis (nunca paga). NC-3
  (nos DOIS SDKs): constante de erro `402` sem base em texto normativo nenhum. E, para
  equilíbrio: **o TypeScript 2.23.0 está conforme** — o Python é que ficou para trás.
- **Como funciona a suíte:** cada não-conformidade confirmada é um teste `xfail(strict)` —
  verde hoje, e QUEBRA no dia em que o SDK consertar (aviso automático). 8 conformidades
  passam + 4 não-conformidades documentadas. Roda offline, sem facilitator.
- **Prova executável:** `uv run pytest conformance` · relatório pronto para issue:
  `notes/x402-mcp-conformance-report.md` — **postar no coinbase/x402 é ação do Beny**.

### T4 ✅ 20/08 — a compra aninhada NÃO desapareceu
- **O que era:** a metade que faltava do GATE 2. Quando a ferramenta que o agente pagou compra
  de TERCEIROS para atender, esse gasto some de toda contabilidade que existe — o agente só vê
  "paguei a ferramenta". O produto promete que gasto delegado não desaparece.
- **O que foi feito:** o servidor MCP ganhou carteira própria (a 3ª, que você abasteceu no
  faucet) e agora COMPRA do vendedor HTTP para responder — dois servidores rodando juntos. O
  recibo da compra upstream volta assinado DENTRO da resposta (`_meta`), num formato v0 nosso
  (`src/mesa/recibo.py`: JSON canônico + assinatura EIP-191; o formato formal é a Fase 4). O
  comprador VERIFICA a assinatura antes de gravar — recibo forjado é recusado (testado) — e a
  compra entra como `origin='delegated'`, com quem comprou (`origin_ref`) e a assinatura
  (`origin_receipt_sig`).
- **O que ficou provado:** DUAS compras no livro penduradas no MESMO passo da árvore (direta +
  delegada); o coletor casou AS DUAS liquidações na chain por (authorizer, nonce) — pagadores
  DIFERENTES (você e o servidor), mesmo recebedor; reconciliação ok: 22→25, zero órfãos novos.
  4 testes novos do recibo (assinar/verificar/adulteração/forja).
- **Aprendizado de método:** o assert original comparava contagens GLOBAIS do livro — quebrou
  porque um probe de debug pagou sem registrar (virou órfão explicado) e o coletor correu mais
  rápido que a chain. Trocado por verificação das DUAS autorizações específicas do run, com
  retry — critério preciso não contamina entre experimentos.
- **Prova executável:** `scripts/fase2/aninhada_run.py` (custo declarado: 0,02 USDC/run).

### 🔧 Manutenção 20/08 — repo na raiz + fix do Docker
- **Repo movido para a raiz do projeto** (pedido do Beny): tudo agora em
  `Documents\x402\mesa\`. Única exceção deliberada: **segredos** em `C:\dev\mesa.env`, FORA da
  pasta sincronizada pelo OneDrive (chave privada em pasta de sync = chave na nuvem).
- **Docker (3 quedas):** causa raiz encontrada — `AutoStart` desligado (o app não subia no
  login; qualquer saída era permanente). Ligado + container com `--restart unless-stopped` +
  `db.connect` agora falha em 5s com runbook na mensagem em vez de pendurar 3 minutos calado.
- **Design enxugado (pedido do Beny):** `design/produto/` ficou só com as 5 telas do COMPRADOR
  (Blotter, TCA, Risco, Laboratório, Livros — as que as fases 7–8 usam), canvas regenerado.
  As 3 telas do vendedor + o checker público (estratégias mortas por D-21/D-23) e a exploração
  visual antiga foram para `arquivo/design/` — nada deletado, tudo recuperável.

### T3 ✅ 20/08 — a árvore de atribuição de verdade
- **O que era:** aposentar o span inventado na mão. A promessa do produto é "quanto custou a
  tarefa X, somando passos e subagentes" — isso exige que as compras pendurem na árvore REAL de
  execução, não num rótulo solto.
- **O que foi feito:** `src/mesa/otel.py` (um `SpanProcessor` que grava cada span encerrado no
  livro — IDs originais do OpenTelemetry, linha completa com começo/fim/desfecho, sem UPDATE) e
  `src/mesa/arvore.py` (a matemática de atribuição como função pura: gasto próprio + descendentes,
  com verificação de integridade — compra em span inexistente, raiz dupla, span órfão). 7 testes
  novos codificam "a soma bate em qualquer altura".
- **O que ficou provado:** uma tarefa real de 5 passos fez DUAS compras MCP pagas em passos
  diferentes; a árvore entrou íntegra no livro, cada compra no passo exato, soma batendo na folha,
  no meio e no topo (0,01 + 0,01 = 0,02). O coletor casou os pagamentos na chain (ok: 17→21).
- **Surpresa boa:** o SDK MCP 2.0 tem OpenTelemetry embutido — os spans internos dele entraram
  sozinhos na nossa árvore, aninhados certinho. Cada compra mostra as DUAS chamadas `tools/call`
  (a que levou "pague primeiro" + a repetida com a prova): a dança do x402 visível na árvore, de
  graça.
- **Incidente (sem perda):** o Docker Desktop caiu pela 3ª vez no projeto — o primeiro run travou
  na conexão com o banco antes de gastar 1 centavo. Runbook conhecido, recuperado em 2 min.
- **Prova executável:** `scripts/fase2/arvore_run.py` (custo declarado: 0,02 USDC de testnet
  por run).

### T2 ✅ 20/08 — a primeira compra por ferramenta MCP, ponta a ponta
- **O que era:** provar a trava D-01 — agente não faz HTTP na mão, chama *ferramentas* (MCP). O
  livro precisa registrar uma compra feita na fronteira de ferramenta igualzinho a uma compra HTTP.
- **O que foi feito:** um **vendedor MCP** (`src/mesa/mcp/seller.py`, porta 8403) com a ferramenta
  paga `consultar` (0,01 USDC), e um **comprador MCP** (`src/mesa/mcp/buyer.py`) que detecta o
  "pague primeiro", assina o pagamento e re-chama com a prova — capturando tudo para o livro pelos
  hooks. O SDK oficial x402 tem suporte MCP nativo, mas **quebrado contra o SDK MCP 2.0** — escrevi
  a ponte (adapter) e usei as primitivas verify/settle direto.
- **O que ficou provado:** tool call pago real na Base Sepolia (tx `0xd087c6…4eb5ef`); resultado
  entregue com o recibo dentro da resposta (`_meta`); livro gravou a tripla com `transport='mcp'`
  e `tool_name='consultar'`; o **coletor casou a liquidação on-chain por (authorizer, nonce)** e a
  reconciliação fechou (ok: 16→17, zero órfãos novos). O livro é agnóstico de transporte NA PRÁTICA.
- **Bônus:** 3 incompatibilidades reais do SDK x402 vs MCP 2.0 anotadas — já cumprem o "achar ≥1
  não-conformidade" do sub-gate da T5.
- **Prova executável:** `scripts/fase2/mcp_once.py`.

### T1 ✅ 20/08 — fundação da fase
- **O que era:** instalar as dependências novas (SDK MCP, OpenTelemetry) sem quebrar nada, e
  validar que elas convivem com o SDK x402.
- **O que ficou provado:** `mcp==2.0.0` + `openinference-instrumentation-mcp==2.0.6` +
  `opentelemetry-sdk==1.44.0` instalados; imports cruzados funcionam; ruff/mypy strict/pytest verdes.
- **Decisões da fase:** design em `docs/fase2.md` · **D-33**: tudo do zero, nenhum projeto anterior
  do Beny entra (o agente da T6 será `src/mesa/agente.py`, Claude Sonnet 5 via SDK da Anthropic).

## Fase 1 — o livro fecha com dado sujo ✅ GATE 1 VERDE (19/08)

*A fase que decidia se o projeto vivia: com erros INJETADOS de propósito, o livro tem que explicar
cada um — se não explica, nada acima presta. Explicou todos, no dia 1 (o critério de kill dava 30).*

### T5 ✅ — caos + reconciliação (o gate em si)
- **O que era:** injetar 6 tipos de erro deliberado (servidor morto pós-liquidação, entrega sem
  cobrança, handler quebrado, replay da mesma autorização, pagamento fantasma fora do livro…) e
  exigir que a reconciliação classifique TODOS, com o resultado previsto ANTES numa tabela-oráculo.
- **O que ficou provado:** 16 ok · 2 entregue-sem-cobrar · 2 pago-sem-entrega · 2
  autorizada-sem-liquidação · 1 replay (pego pela chave E pelo facilitator, defesas independentes)
  · 3 órfãos-chain todos explicados · **0 inexplicados**. Os vereditos bateram com o oráculo.
  11 testes unitários codificam o oráculo (`tests/test_reconcile.py`).
- **Prova executável:** `scripts/fase1/chaos_run.py`.

### T4 ✅ — o coletor idempotente
- **O que era:** varrer a blockchain (transferências USDC para o nosso endereço + o evento
  `AuthorizationUsed` no mesmo recibo de tx) e casar com o livro pela chave forte
  **(authorizer, nonce)** — a mesma dupla que está na autorização assinada E no evento on-chain.
- **O que ficou provado:** rodar duas vezes = exatamente as mesmas linhas (idempotência); 10/10
  pagamentos casados; e 2 pagamentos feitos ANTES de o livro existir apareceram como órfãos-chain
  com explicação — a reconciliação explica até o passado.

### T3 ✅ — o livro + a ingestão do comprador
- **O que era:** o schema (agnóstico de trilho E de transporte: tabela genérica de autorização +
  evidência por trilho em JSONB) e o comprador gravando requisição→cotação→autorização pelos hooks
  oficiais do SDK — sem gambiarras.
- **O que ficou provado:** 10 pagamentos → 10 triplas coerentes; migration aplica em banco zerado;
  URLs nunca em claro (só hash — query string carrega CPF/CNPJ).

### T2 ✅ — o primeiro pagamento real
- **O que ficou provado:** 200 + tx na Base Sepolia com `Transfer` E `AuthorizationUsed` no mesmo
  recibo — a confirmação de que a chave de join existe na prática. O facilitator paga o gas
  (ninguém aqui precisa de ETH).

### T1 ✅ — fundação
- **O que ficou provado:** repo com uv/ruff/mypy strict/pytest, Postgres 17 no Docker (porta 5433),
  2 carteiras geradas com chaves só no `.env`, saldo USDC lido do contrato on-chain.
