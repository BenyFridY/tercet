# mesa (nome de trabalho)

O livro da compra feita por agente: registra o que os agentes compraram (requisição → cotação →
autorização), casa com a liquidação on-chain e **explica toda diferença**. Nunca toca chave, saldo
ou fluxo de dinheiro — observa e produz evidência (Res. BCB 520, art. 9º).

## O app — as cinco telas, ao vivo do livro (Fase 12, D-35)

```powershell
uv run mesa-app        # -> http://127.0.0.1:8400
```

**01 blotter** (o que compraram, com estado derivado e a cadeia de eventos de cada compra) ·
**02 tca** (desperdício, dedup entre agentes, custo por entrega) · **03 risco** (orçamento por
árvore D-02, aprovações D-14, passaporte do pagador D-08) · **04 laboratório** (backtest de
política de gasto, point-in-time, IC honesto) · **05 livros** (reconciliação de três pontas,
períodos carimbados, fatura por contraparte, fiscal BR).

O app é **somente leitura por construção**: a sessão Postgres abre com
`default_transaction_read_only=on` — ele não consegue escrever no livro nem que queira, e
`tests/test_app.py` prova isso. Dado real sempre; testnet e sintético rotulados NA tela.

## O MCP — o livro como ferramentas para agentes (Fase 13, D-37)

```powershell
claude mcp add mesa -- uv run mesa-mcp    # e pergunte: "quanto meus agentes gastaram?"
```

Sete ferramentas de LEITURA (lista fechada, provada por teste): `status_do_livro`, `gasto`,
`compras` (com filtros), `compra` (a gaveta de eventos), `vereditos`, `passaportes`, `fiscal`.
Mesma garantia do app: a sessão é read-only estrutural — o servidor MCP não tem caminho de
escrita; `tests/test_mcp_livro.py` prova. Transporte stdio, local.

## Os exports — contábil universal e CARF (Fase 13)

```powershell
uv run python scripts/fase13/contabil_build.py   # -> contabil/<aaaa-mm>/ (universal, QBO, Xero + detalhe com tx hash)
uv run python scripts/fase13/carf_build.py       # -> fiscal/carf/<ano>/ (visão OECD, nasce OECD11/test data)
```

O diário de partidas dobradas da competência (débito==crédito provado; micro-pagamentos
agregados, detalhe de auditoria em 6 casas) e a visão CARF (guia oficial OECD jul/2025) do
que um RCASP reportaria destas transações — demonstração rotulada, identidades sintéticas,
números reais. Detalhes e ressalvas: `docs/fase13-export.md`.

## Exemplo do zero (terceiro, só com este README) — GATE 12

Pré-requisitos: [uv](https://docs.astral.sh/uv/), Docker, Python 3.11+.

```powershell
# 1. dependências + banco (Postgres 17 em 127.0.0.1:5433 — só a sua máquina)
uv sync
docker run -d --name mesa-pg -e POSTGRES_USER=mesa -e POSTGRES_PASSWORD=mesa `
  -e POSTGRES_DB=mesa -p 127.0.0.1:5433:5432 `
  -v mesa-pgdata:/var/lib/postgresql/data postgres:17
uv run python scripts/check_db.py            # aplica as migrations num banco zerado

# 2. carteiras de TESTE (grava .env local; nunca commitado) + USDC de mentira
uv run python scripts/setup_wallets.py
#    -> cole o endereço do comprador em https://faucet.circle.com (USDC / Base Sepolia)
uv run python scripts/check_balance.py       # confere o saldo lido on-chain

# 3. um vendedor de brinquedo + 10 pagamentos x402 REAIS na testnet
uv run uvicorn mesa.http.seller:app --port 8402     # terminal 1
uv run python scripts/fase1/buyer.py 10             # terminal 2 (grava o livro)

# 4. a chain é a fonte de verdade: coletar e reconciliar
uv run python -m mesa.collector              # casa (authorizer, nonce) com o livro
uv run python -m mesa.cli                    # a tabela de vereditos, órfãos em vermelho

# 5. o produto
uv run mesa-app                              # -> http://127.0.0.1:8400
```

Custa **zero dinheiro real**: USDC de faucet, e no scheme `exact` o facilitator paga o gas.

- **Docs do projeto** (tese, decisões D-01–D-33, programa de 12 fases): um nível acima,
  na raiz `x402\` (README → PLANO → DECISOES). Este repo vive DENTRO da raiz desde 20/08.
- **O que já aconteceu, o que provou e o que vem agora:** [docs/DIARIO.md](docs/DIARIO.md) ←
  comece por aqui para se situar.
- **Segredos** (chaves privadas, `ANTHROPIC_API_KEY`): **`C:\dev\mesa.env`** — fora da pasta
  sincronizada pelo OneDrive, de propósito (chave em pasta de sync = chave na nuvem).

## Mapa do repo

| Caminho | O que é |
|---|---|
| `src/mesa/config.py` | Constantes (USDC, rede, chain id) + `Settings` lidas do `.env` |
| `src/mesa/db.py` | Acesso ao livro — **insert-only por construção** (invariante D-06) |
| `src/mesa/reconcile.py` | **O coração**: reconciliação de três pontas, função pura (vira biblioteca) |
| `src/mesa/collector.py` | Coletor on-chain: `Transfer` + `AuthorizationUsed` por txHash; idempotente, cursor persistido |
| `src/mesa/cli.py` | `uv run python -m mesa.cli` — a tabela de vereditos, órfãos em vermelho |
| `src/mesa/http/` | Trilho HTTP (Fase 1): `seller.py` (endpoint de brinquedo + caos) e `buyer.py` (comprador instrumentado) |
| `src/mesa/mcp/` | Trilho MCP (Fase 2, D-01): `seller.py` (ferramenta paga) e `buyer.py` (adapter + captura) |
| `migrations/` | SQL puro numerado — schema agnóstico de trilho e transporte |
| `scripts/` | Utilitários de ambiente (carteiras, saldo, banco) + `fase1/`, `fase2/` — as provas executáveis de cada fase |
| `tests/` | O gate como teste pytest: dado sujo → classificação esperada |
| `docs/` | `DIARIO.md` (narrativa por tarefa) + doc de design de cada fase (`fase2.md`, …) |
| `notes/` | Rascunhos p/ fora (ex.: comentário no OTel #443) |

## Subir o ambiente

```powershell
uv sync
docker run -d --name mesa-pg -e POSTGRES_USER=mesa -e POSTGRES_PASSWORD=mesa `
  -e POSTGRES_DB=mesa -p 127.0.0.1:5433:5432 `
  -v mesa-pgdata:/var/lib/postgresql/data postgres:17
# 127.0.0.1 obrigatório: sem ele o livro fica aberto pra qualquer máquina no mesmo
# Wi-Fi (docs/seguranca.md, furo 1). scripts/saude.py confere isso sempre.
uv run python scripts/setup_wallets.py   # gera as EOAs -> .env (NUNCA commitado)
uv run python scripts/check_db.py        # Postgres de pé + migrations
uv run python scripts/check_balance.py   # saldo USDC lido on-chain
uv run python scripts/saude.py           # UM comando: ruff+mypy+pytest+verificador+portas+segredos
uv run python scripts/backup_db.py       # dump do livro -> backups/ (rotina, ~5s)
```

Faucet: https://faucet.circle.com → USDC → Base Sepolia (20 USDC / 2h por endereço).
Chave da Anthropic (só p/ o agente da T6): linha `ANTHROPIC_API_KEY=...` em `C:\dev\mesa.env`.

## Rodar as provas de cada fase

```powershell
# Fase 1 — o livro fecha com dado sujo (GATE 1 ✅ 19/08)
uv run uvicorn mesa.http.seller:app --port 8402     # terminal 1: vendedor HTTP
uv run python scripts/fase1/chaos_run.py            # terminal 2: caos + reconciliação + asserts

# Fase 2 — MCP (T2 ✅ 20/08)
uv run python -m mesa.mcp.seller                    # terminal 1: vendedor MCP (porta 8403)
uv run python scripts/fase2/mcp_once.py             # terminal 2: 1 tool call pago + livro

# Fase 8 — as telas (GATE 8 ✅ 21/08): gerar do livro e abrir no navegador
uv run python scripts/fase8/telas_build.py           # -> scripts/fase8/mesa-telas.html
uv run python scripts/fase8/aprovacao_demo.py        # demo D-14 (interativa, testnet)

# Fase 9 — relatório público do censo (pacote ✅ 21/08; publicar = Beny)
uv run python scripts/fase9/relatorio_build.py       # -> relatorio/*.md + dados/

# A qualquer momento: varrer a chain e reconciliar
uv run python -m mesa.collector                      # testnet (vendedor)
uv run python -m mesa.collector --pagador            # mainnet (censo)
uv run python -m mesa.cli
```

## Qualidade (o "pronto" tem definição)

```powershell
uv run python scripts/saude.py    # UM comando: ruff+mypy+pytest+verificador+portas+segredos
```

Modelo de ameaças e o que fica de fora, com nome: [docs/seguranca.md](docs/seguranca.md).
