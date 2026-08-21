# Fase 2 — a árvore e o agente real (doc de design)

> ✅ **GATE 2 VERDE em 21/08/2026** — todas as 6 tarefas concluídas; prova final:
> `scripts/fase2/agente_run.py` (o agente decidiu, o livro registrou, a aninhada não
> desapareceu, a soma bateu, a chain confirmou 2/2 na primeira tentativa do coletor).

*Escrito em 20/08/2026, antes de qualquer código, pelo método do programa (D-31). Fontes: PLANO.md (seção Fase 2), DECISOES.md (D-01, D-02, D-13, D-24, D-30), fonte do SDK x402 v2.20.0 instalado.*

## Objetivo e gate

Provar que o livro mede o que promete quando o comprador é um **agente de verdade** operando na **camada de ferramenta** (D-01), com atribuição por **árvore** (D-02) — e que compra **aninhada** (um servidor MCP comprando em nosso nome) não desaparece.

> **GATE 2:** a soma por agente, por passo e por tarefa bate exatamente; a compra aninhada não desaparece; as compras reais do censo aparecem no livro como qualquer outra. **Sub-gate SEP-2007:** a suite de conformance roda contra ≥2 implementações existentes e acha ≥1 não-conformidade real, reportada com reprodução.

## O que a leitura do SDK mudou no desenho (20/08)

O pacote `x402` v2.20.0 tem **suporte MCP nativo** (`x402.mcp`) — não construímos wrapper próprio:

- **Servidor:** `create_payment_wrapper(resource_server, PaymentWrapperConfig(accepts, hooks))` decora o handler da ferramenta; hooks `on_before_execution` / `on_after_execution` / `on_after_settlement` são o ponto de captura do lado vendedor.
- **Cliente:** `wrap_mcp_client_with_payment(mcp_client, payment_client, auto_payment)`; o resultado carrega `_meta["x402/payment-response"]` — **o recibo do pagamento MCP já vem propagado pelo próprio SDK**.
- **Consequência para o D-30:** o caminho primário é o nativo do SDK (mesma família dos lifecycle hooks que a Fase 1 já usa). FastMCP 3.x `on_call_tool` vira plano B, não plano A. `openinference-instrumentation-mcp` continua para a integridade da árvore entre processos.

**Achado pré-conformance (verificar contra o texto do SEP na execução):** `x402/mcp/types.py:13` define `MCP_PAYMENT_REQUIRED_CODE = 402`; o SEP-2007 especifica `-32402`. Se confirmado, é a primeira não-conformidade real do sub-gate — no SDK oficial da própria foundation.

## Componentes (todos no repo `mesa/` na raiz do projeto)

1. **`src/mesa/mcp/seller.py`** — servidor MCP (transporte HTTP streamable, porta 8403) com uma ferramenta paga. Preço 0,01 USDC, `exact`, Base Sepolia — o mesmo ambiente D-18. *(Nota de execução, 20/08: o payment wrapper oficial do SDK está quebrado contra o mcp 2.0 — usamos as primitivas verify/settle direto; ver T5.)*
2. **Compra aninhada (D-13):** para atender a ferramenta, o servidor MCP **compra upstream** do seller HTTP da Fase 1, com **carteira própria** (terceira EOA). O recibo da compra upstream é anexado ao tool result em `_meta["mesa/upstream-receipts"]` (lista), assinado pela chave do servidor (eth-account sobre JSON canônico; o formato formal é a Fase 4 — aqui é v0 suficiente para `origin_receipt_sig`).
3. **`src/mesa/mcp/buyer.py`** — cliente MCP embrulhado com pagamento + captura: grava `request` (`transport='mcp'`, `tool_name`, `origin`), `quote`, `authz` pelos hooks do cliente x402; a compra delegada do item 2 entra como `origin='delegated'`, `origin_ref` = identidade do servidor, `origin_receipt_sig` = assinatura do recibo propagado.
4. **`src/mesa/otel_book.py`** — spans REAIS no lugar do span hardcoded da Fase 1: `SpanProcessor` custom que, no fim de cada span, insere em `span` (append-only, IDs do OTel intocados). `openinference-instrumentation-mcp` propaga o contexto cliente→servidor para a árvore não quebrar entre processos.
5. **`src/mesa/agente.py` — o agente real, construído do ZERO dentro do repo (D-33).** Loop de tool-calling com o SDK oficial da Anthropic (Tool Runner, `client.beta.messages.tool_runner`), modelo `claude-sonnet-5`, adaptive thinking. As ferramentas do agente são **wrappers locais sobre o nosso cliente MCP instrumentado** (item 3) — nunca o conector MCP server-side da API, porque a assinatura do pagamento acontece na máquina do comprador (D-05). Tarefa do agente: uma pergunta de pesquisa que exige decidir **se e quando comprar** o dado da ferramenta paga (a decisão de compra é do agente, não do script — é isso que faz dele um agente e não um driver). Nenhum projeto anterior do Beny entra aqui — nem código, nem dado (D-33). Requer `ANTHROPIC_API_KEY` no `.env`.
6. **`conformance/`** — suite SEP-2007: harness pytest + mock facilitator; cenários: código de erro payment-required, challenge, retry com prova, chaves `_meta`, replay de payload. Alvos: (a) SDK Python x402 v2.20.0 (candidata já achada), (b) implementação TS de referência do repo oficial (via subprocess node). Não-conformidade confirmada → issue com reprodução no repo da foundation.
7. **Dogfood do censo (pequeno):** 2–3 fontes x402 vivas, compras reais em mainnet, orçamento **US$ 20–50 de dinheiro real — só roda com OK explícito, na hora**. Entram no livro como qualquer compra (`eip155:8453`).

## Schema

**Nenhuma migration nova prevista.** `transport`, `tool_name`, `origin`, `origin_ref`, `origin_receipt_sig` existem desde a 0001; spans reais usam a tabela `span` como está. Se algo faltar, é sinal de erro de design — parar e registrar em DECISOES antes de migrar.

## Custos declarados (regra transversal do programa)

- Testnet: ~3–5 USDC de faucet (grátis), gas zero (`exact`, facilitator paga). Terceira EOA (servidor MCP) precisa de faucet próprio.
- Real: US$ 20–50 do dogfood — **gatilho manual do Beny**, nada gasta sozinho.

## Tarefas e critérios de pronto

| # | Tarefa | Pronto quando |
|---|---|---|
| T1 ✅ 20/08 | Deps (`mcp==2.0.0`, `openinference-instrumentation-mcp==2.0.6`, `opentelemetry-sdk==1.44.0`) + esqueleto verde | ruff/mypy strict/pytest verdes com os imports novos |
| T2 ✅ 20/08 | Ferramenta MCP paga ponta a ponta na testnet — tx `0xd087c6…4eb5ef`; coletor casou 1/1 por (authorizer, nonce); reconciliação ok=17 | 1 tool call paga; `_meta["x402/payment-response"]` presente; tx no Basescan; tripla no livro com `transport='mcp'` |
| T3 ✅ 20/08 | Árvore OTel real gravada no livro — `mesa/otel.py` + `mesa/arvore.py`; tarefa de 5 passos + spans nativos do SDK; 2 compras reais nos passos certos; ok=21 no coletor | run com ≥3 spans reais; compra pendurada no span certo; soma por altura bate (teste pytest) |
| T4 ✅ 20/08 | Compra aninhada com recibo propagado — `mesa/recibo.py` (EIP-191 sobre JSON canônico, verificado antes de gravar); 3ª carteira; ok=25 | 2 compras no livro (direta + `delegated`); coletor casa as DUAS liquidações on-chain; delegada não desaparece (teste) |
| T5 ✅ 20/08 | Conformance x402-sobre-MCP (re-ancorada no spec vivo — D-34: SEP-2007 dormente) — `conformance/`: 8 passam + 4 NCs em xfail(strict); Python 2.20.0 quebrado vs MCP 2.x, TS 2.23.0 conforme; relatório em notes/ | sub-gate: ≥1 não-conformidade real em ≥2 implementações testadas, com reprodução |
| T6 ✅ 21/08 | Agente próprio real (D-33) — `mesa/agente.py` (Tool Runner + claude-sonnet-5, 2 ferramentas): tentou a grátis, DECIDIU comprar 1×, resposta cita custo; árvore 6 spans, soma 20000 no topo; coletor 2/2 settled na 1ª tentativa | GATE 2 completo (asserts em `agente_run.py`) ✅ |

## Riscos e incógnitas

1. Compatibilidade `x402.mcp` ⇄ SDK `mcp` 2.0 (o wrapper espera "MCP client (from MCP SDK)" — validar na T1/T2 antes de tudo).
2. `openinference-instrumentation-mcp` pode não cobrir a API v2 do SDK `mcp` — plano B: propagar `traceparent` manualmente em `_meta` (a árvore não pode depender de lib de terceiro para existir).
3. O texto exato do SEP-2007 (código de erro, nomes de campo) precisa ser relido da fonte na T5 — a candidata 402 vs -32402 só vale com o texto ao lado.
4. O agente (T6) depende de `ANTHROPIC_API_KEY` no `.env` — o Beny fornece; nada roda sem ela.
