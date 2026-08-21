# mesa (nome de trabalho)

O livro da compra feita por agente: registra o que os agentes compraram (requisição → cotação →
autorização), casa com a liquidação on-chain e **explica toda diferença**. Nunca toca chave, saldo
ou fluxo de dinheiro — observa e produz evidência (Res. BCB 520, art. 9º).

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

# A qualquer momento: varrer a chain e reconciliar
uv run python -m mesa.collector
uv run python -m mesa.cli
```

## Qualidade (o "pronto" tem definição)

```powershell
uv run ruff check .
uv run mypy src scripts
uv run pytest -q
```
