# Fase 13 / item 1 — o MCP do produto: o livro como ferramentas (doc de design)

> ✅ **GATE 13a VERDE em 23/08/2026** — `mesa-mcp` existe: servidor stdio com a
> lista FECHADA de 7 ferramentas de leitura. Provado por cliente MCP REAL em
> processo separado (`scripts/fase13/gate13_demo.py`): lista confere, o `gasto`
> que atravessou o transporte bateu com SQL independente (US$ 0,272 mainnet),
> vereditos e corrente respondendo. Read-only estrutural provado por teste
> (INSERT/UPDATE/DELETE recusados). 8 testes novos → 119 no total; ruff + mypy
> strict limpos; entry point no pacote. Instalação num agente:
> `claude mcp add mesa -- uv run mesa-mcp`.

*Escrito em 23/08/2026, antes do código, pelo método do programa (D-31). Pedido do
Beny: "quero saber se criamos MCP para isso? essas ferramentas para ajudar" →
"arrume o MCP por favor então". Contexto: `docs/alcance-internacional.md` (a Fase 13
proposta: MCP do produto + export contábil + carf-xml — este doc cobre o primeiro).*

## O que é, em linguagem direta

A Fase 2 já usou MCP como **trilho de compra** (`mesa/mcp/buyer.py` e `seller.py`:
um agente PAGANDO tool calls via x402). O que não existia era o contrário: **o
produto virado para o agente** — um servidor MCP em que qualquer assistente (Claude
Code, Claude Desktop, outro agente) pergunta ao livro em conversa:

> "quanto meus agentes gastaram este mês?" · "tem veredito aberto?" · "esse pagador
> merece confiança?" · "como está a competência fiscal?"

A tese é a mesma do app (fase 12): **cada ferramenta é uma LENTE sobre o livro** —
zero lógica de negócio nova; os mesmos motores que os gates já provaram, servidos
por outro transporte.

## D-37 — a decisão de forma (vai para o DECISOES.md)

- **Read-only ESTRUTURAL, igual ao app (D-35):** o servidor MCP usa a MESMA
  `conectar_leitura()` (sessão Postgres `default_transaction_read_only=on`). Não
  existe caminho de escrita para o agente nem que a ferramenta queira.
- **Lista FECHADA de ferramentas** (o princípio do D-36 nas operações): só leitura,
  nomes fixos, teste prova que a lista é exatamente a esperada — nenhuma ferramenta
  de escrita exposta, nunca chave, nunca segredo na resposta.
- **Transporte stdio, local** (`uv run mesa-mcp`): o mesmo postulado do app
  (127.0.0.1, nada exposto na rede). Instalação num agente:
  `claude mcp add mesa -- uv run mesa-mcp`.
- **As regras de honestidade viajam na resposta:** testnet rotulada, valores em
  micro-USD ditos como tal, e `status_do_livro` diz até que bloco o livro enxerga —
  o MCP nunca finge tempo real.

## As ferramentas (v0 — 7, todas leitura)

| Ferramenta | Responde | Motor que JÁ existe |
|---|---|---|
| `status_do_livro` | até onde o livro está atualizado (cursores, corrente de hash) | `app.dados.status_livro` |
| `gasto` | resumo: real vs testnet vs invoice, por trilho/agente/dia, desperdício | `telas.agregar` + `marcar_desperdicio` |
| `compras` | a lista filtrável (estado/rede/trilho/agente/texto, com limite) | `telas.carregar_linhas` |
| `compra` | a cadeia de eventos de UMA compra (a gaveta do blotter) | `telas.eventos_da_compra` |
| `vereditos` | reconciliação de 3 pontas agora: contagens + explicação | `reconcile` |
| `passaportes` | os passaportes emitidos, re-verificados offline NA CHAMADA | `passaporte` via `app.dados.contexto_risco` |
| `fiscal` | competência: nº de saídas mainnet, total R$, veredito do limiar | `decripto` + PTAX persistido (nunca busca rede) |

## GATE 13a — pronto quando

1. Um cliente MCP **real** (stdio, processo separado — como um agente subiria o
   servidor) lista as ferramentas e a lista é EXATAMENTE a fechada.
2. O `gasto` devolvido pelo transporte **bate com query SQL independente** (mesmo
   critério do gate 12a: nenhum número digitado).
3. Teste prova que a conexão do servidor **não consegue escrever** (INSERT falha).
4. Suíte inteira verde + ruff + mypy strict; entry point `mesa-mcp` no pacote.

## Riscos, ditos com franqueza

- **Livro pequeno**: as respostas carregam TODAS as linhas e filtram em Python —
  igual ao app; se o livro crescer, vira SQL com WHERE (não construir antes).
- **`passaportes` depende dos artefatos do checkout** (`scripts/fase10/saida/`);
  num install de PyPI a resposta diz "nenhum passaporte no diretório" — estado
  válido, não erro.
- **stdio no Windows**: o SDK 2.0 cuida do subprocess; o gate roda exatamente esse
  caminho para não ficar em teoria.
