# Fase 14 — o martelo no nome + o produto "bonitinho" (doc de design)

> ✅ **GATE 14 VERDE em 24/08/2026** — (a) `contabil` e `carf` disparados por POST
> na interface, rc=0, log ao vivo, e a aba 05 listando os artefatos; (b) app
> vestindo tercet (título, wordmark, símbolo) conferido por screenshot; (c) 130
> testes + mypy strict + ruff; (d) MCP demonstrado ao vivo na conversa do Beny.
> Achado extra: o runner de jobs força PYTHONIOENCODING=utf-8 nos subprocessos
> (sem isso, cp1252 derrubava qualquer motor que imprimisse acento no Windows).

*Escrito em 24/08/2026, antes do código (D-31). Pedido do Beny: "nome tá ok,
publicação olhamos mais pra frente; o que falta, tem fase 14? quero ver MCP
funcionando, quero ver app também, tudo bonitinho, utilidades, features".*

## O martelo: **tercet** APROVADO (24/08/2026)

O que muda AGORA (superfícies visíveis) e o que espera o dia da publicação:

| Onde | Agora (Fase 14) | No dia da publicação |
|---|---|---|
| Site | já era tercet; rodapé passa a dizer "nome aprovado" | GitHub Pages |
| App (telas) | wordmark + símbolo tercet no topo | — |
| MCP | nome do servidor → `tercet-livro` | registro `claude mcp add tercet` |
| Pacote Python | continua `mesa` (decisão da Fase 12: troca por sed no dia, com o PyPI) | `tercet` no PyPI |

## As utilidades (features) desta fase

1. **Aba 06 operações ganha os motores da Fase 13** (lista FECHADA, D-36, zero
   dinheiro): `contabil` (gera o diário da competência) e `carf` (gera a visão
   OECD do ano) — o usuário gera os exports pela tela, com log ao vivo.
2. **Tela 05 livros vira o índice dos artefatos**: além do DeCripto, lista os
   exports contábeis e CARF gerados (`contabil/`, `fiscal/carf/`).
3. **Demonstração ao vivo** (o "quero ver"): as ferramentas MCP chamadas de
   verdade na conversa + o app de pé para clicar.

## GATE 14

> (a) as duas operações novas rodam PELA TELA e os artefatos aparecem listados na
> aba livros; (b) marca tercet nas telas conferida por screenshot; (c) suíte
> inteira + mypy strict verdes; (d) MCP demonstrado ao vivo na conversa do Beny.

## O que fica honesto e dito

- Achado operacional de 24/08: o Docker Desktop reiniciou e derrubou o mesa-pg no
  meio da demo do MCP — o servidor respondeu "connection timeout" em vez de mentir;
  container de volta, respostas voltaram. Registrado porque é o comportamento
  certo: sem banco, sem número.
