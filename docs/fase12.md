# Fase 12 — o produto inteiro: o app + o lançamento OSS (doc de design)

> ✅ **GATE 12a VERDE + 12b PRONTO-LOCAL em 23/08/2026** — o app existe:
> `uv run mesa-app` → cinco telas servidas ao vivo do livro (blotter, tca, risco,
> laboratório, livros), 60–180ms por tela, visual do design, dado 100% real com
> testnet/sintético rotulados. Read-only ESTRUTURAL provado por teste (INSERT/
> UPDATE/DELETE recusados pela sessão). 8 testes novos (números da tela ⇔ queries
> independentes); screenshots das 5 telas conferidos no headless Chrome. OSS: CI
> GitHub Actions pronto (mesmos comandos do saude.py + Postgres de serviço),
> README com o exemplo-do-zero, wheel constrói com templates e entry point.
> Achado da fase: `localhost` no Windows tentava ::1 e queimava 5s por conexão —
> trocado por 127.0.0.1 explícito (10,3s → 0,08s por tela).
> **Falta apenas o que é do Beny:** nome do produto, repo público, PyPI — junto
> com as publicações adiadas (decisão 23/08).

*Escrito em 23/08/2026, antes de qualquer código, pelo método do programa (D-31).
Pedido do Beny (23/08): "quero também que monte o app mesmo... um site... quero o
produto inteiro inteiro". Fontes: `design/produto/` (as 5 telas desenhadas),
PLANO.md (Fase 12), DECISOES.md (D-16, D-35 nova), e os motores REAIS que as fases
1–11 deixaram prontos. Custo: zero (tudo local).*

## O que é esta fase, em linguagem direta

Até aqui o produto existiu em pedaços que funcionam: o livro (F1), a árvore (F2), as
compras reais (F3), a prova de integridade (F4), as checagens (F5), o multi-trilho
(F6), o backtest (F7), duas telas estáticas (F8), o passaporte (F10) e o fiscal
(F11). A Fase 12 monta **o produto que se USA**: um app local — a **mesa** — com as
cinco telas do design servidas ao vivo do banco, e **o produto que se INSTALA**: o
pacote OSS com CI, README e exemplo reproduzível do zero.

**A tese do app em uma frase:** cada tela é só uma LENTE sobre o livro — o app não
tem lógica de negócio própria; ele chama os mesmos motores que os gates já provaram.

## D-35 — a decisão de forma (registrada no DECISOES.md)

A Fase 8 decidiu "v0 sem servidor" (página estática gerada). O Beny pediu o app de
verdade — a decisão evolui, sem jogar nada fora:

- **O app é um servidor local** (FastAPI + Jinja2, server-rendered, sem build de
  frontend, sem SPA): `uv run mesa-app` → `http://127.0.0.1:8400`. HTML gerado no
  servidor casa com "scripts > notebooks" e mantém o pacote instalável por qualquer um.
- **Read-only ESTRUTURAL, não disciplinar**: a conexão do app abre a sessão Postgres
  com `default_transaction_read_only=on`. O app **não consegue** escrever no livro
  nem que queira — o mesmo princípio do invariante de arquitetura (observador que
  não pode afetar) aplicado à própria tela. Um teste do gate prova que escrita falha.
- A tela estática da Fase 8 continua existindo como artefato exportável (o
  "relatório que se manda por e-mail"); o app é o produto vivo.

## As cinco telas (design de `design/produto/`) e o motor real de cada uma

| Aba | O que mostra | Motor que JÁ existe |
|---|---|---|
| **01 blotter** | gasto do mês vs orçamento, por trilho; entregue-não-recebido, cobertura de verificação, recusas da política; gasto diário; a tabela de compras com estados; gaveta com a cadeia de eventos de cada compra | `telas.py` (derivar_estado, eventos_da_compra, agregar) — F8 |
| **02 tca** | desperdício (mesmo recurso, mesmo byte), dedup entre agentes, custo por unidade de trabalho, preço pago vs distribuição | `telas.py` (marcar_desperdicio) + queries do livro — F8 |
| **03 risco** | orçamento por árvore (D-02, a soma que bate em qualquer altura), cobertura de verificação, fila/histórico de aprovações D-14, **passaporte do pagador por carteira** (novo — F10 não existia quando o design foi feito; desvio documentado) | `telas.py` (arvore_orcamento) + `aprovacao.py` + `passaporte.py` |
| **04 laboratório** | as políticas de gasto avaliadas point-in-time: "teria custado", "teria bloqueado", amostra do bloqueado, com proxies ROTULADOS (D-12) | `laboratorio.py` — F7 |
| **05 livros** | reconciliação de três pontas com vereditos nomeados; janela de fechamento (períodos + carimbos RFC3161/OTS); fatura consolidada por contraparte; trilho invoice; **fiscal BR** (competência da F11: total, PTAX, veredito do limiar); trilha de auditoria (corrente de hash + como verificar sem confiar na gente) | `reconcile.py` + `integridade`/`period_close` + `trilho_invoice.py` + `decripto.py`/`ptax.py` |

**Regras de honestidade da interface (as mesmas do programa):**
- Dado REAL sempre; testnet e sintético SEMPRE rotulados na própria tela (D-12).
- Inferência marcada como inferência ("isso foi x402" deduzido = dito).
- "Atualizado até o bloco N" — o app nunca finge tempo real.
- Nenhum número digitado: tudo derivado do banco na hora do request.

## O pacote OSS (GATE 12b — pronto LOCAL; publicar é ação do Beny, no fim)

- **CI** GitHub Actions: ruff + mypy strict + pytest com Postgres de serviço
  (migrations aplicam do zero) — o arquivo fica pronto no repo, roda no dia em que o
  repo for público.
- **README de produto**: o exemplo reproduzível do zero — carteiras de teste, faucet,
  10 pagamentos na testnet, coletor, reconciliação na CLI, `mesa-app` no navegador.
  O critério é o GATE 12 do PLANO: um terceiro roda só com o README.
- **Empacotamento**: `pyproject` já é hatchling; entra o entry point `mesa-app` e os
  metadados de publicação. **Nome no PyPI é decisão do Beny** (`mesa` está TOMADO no
  PyPI — framework de agent-based modeling); o pacote fica pronto com o nome de
  trabalho e troca-se com um sed no dia.

## O que é seu (Beny) vs o que faço sozinho

**Faço sozinho (esta fase):** o app inteiro, os testes, os screenshots, o CI, o
README, o empacotamento local.

**Fica PRONTO esperando você (no fim do programa, decisão de 23/08):**
1. **O nome do produto** (item aberto do PLANO — e o gancho do PyPI acima).
2. Tornar o repo público + criar o repo no GitHub.
3. Conta/token do PyPI e o `uv publish`.
4. As publicações congeladas (gates 5b/9b) — pacote em `notes/publicar/`.

## As etapas

| # | Etapa | Pronto quando |
|---|---|---|
| T1 | Este doc + D-35 | você está lendo |
| T2 | Esqueleto: FastAPI+Jinja2, conexão read-only, base visual do design | `mesa-app` sobe; teste prova que a conexão do app NÃO escreve |
| T3 | Telas 01–02 (blotter, tca) | números batem com queries independentes em teste |
| T4 | Telas 03–04 (risco, laboratório) | idem; aprovações D-14 e passaportes reais na tela |
| T5 | Tela 05 (livros) | vereditos = reconciliação; período fechado com carimbos na tela |
| T6 | **GATE 12a** | 5 telas 200 com dado real conferido por teste; escrita recusada; screenshots headless conferidos |
| T7 | **GATE 12b** | CI verde LOCAL (mesmos comandos), README-exemplo completo, pacote constrói |
| T8 | Registro | DIARIO/PLANO/DECISOES atualizados; commit |

> **GATE 12 (do PLANO):** um terceiro, só com o README, roda o exemplo do zero até a
> tabela de reconciliação — sem pedir ajuda. *(O ato de publicar repo/PyPI é do
> Beny, junto com as publicações adiadas.)*

## Riscos, ditos com franqueza

- **Design de 1420px fixo** era prancha, não página: o app usa o MESMO vocabulário
  visual (dark #0B0D0F, Space Grotesk/JetBrains Mono, verde #28A87F, cards de vidro)
  em layout fluido — fidelidade de linguagem, não de pixel.
- **Dados pequenos**: o livro tem ~100 compras; telas como "preço vs distribuição"
  ficam com n baixo. A tela DIZ o n em vez de esconder (auditoria, não ranking — D-21).
- **Fase 7 no request**: o backtest roda em milissegundos no livro atual; se crescer,
  vira cache — não antes (não construir preventivamente).
