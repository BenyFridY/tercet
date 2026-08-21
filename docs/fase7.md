# Fase 7 — o Laboratório: backtest de política de gasto (doc de design)

> ✅ **GATE 7 VERDE em 21/08/2026** — 5 políticas avaliadas point-in-time contra as 15
> decisões REAIS do censo (`scripts/fase7/laboratorio_resultado.json`). Baseline: 87%
> de entrega [62–96%] a US$ 0,0209/entrega. Achado positivo: `micro` entrega 90% a
> **US$ 0,0013/entrega** (16× mais barato). Os 2 NEGATIVOS do gate: `verified-only`
> (a política "mais segura" compra ZERO hoje — 0/15 publicam vínculo) e `premium`
> ("caro = confiável": 50% de entrega, a compra mais cara da rodada foi uma das que
> falhou; n=2, IC [9%–91%] — sem evidência a favor, anedota contra). Todos os proxies
> e premissas rotulados (D-12); IC de Wilson nomeado; motor puro com point-in-time
> garantido POR TIPO (a política não tem como ver o desfecho).

*Escrito em 21/08/2026, antes do código, pelo método (D-31). Fontes: PLANO (Fase 7),
D-12 (proxy rotulado), D-15 (custo completo). Custo da fase: **zero** — o Laboratório
só LÊ o livro; nenhuma compra nova, nenhum LLM.*

## O que é, em linguagem simples

O livro guarda cada decisão de compra que o agente enfrentou: o que foi ofertado, por
quanto, o que ele pagou, o que chegou. O Laboratório usa isso pra responder a pergunta
que toda mesa faz: **"e se a política de gasto fosse outra?"** — e se o teto fosse
menor? e se só comprasse de vendedor verificado? e se caro = confiável?

É backtest, com as MESMAS regras anti-autoengano do seu trabalho quant:

- **Point-in-time por construção:** a política só enxerga o que o comprador enxergava
  NA HORA de assinar (preço cotado, vendedor, estado do vínculo, orçamento restante).
  O desfecho (entregou? cobrou?) entra DEPOIS, só para dar nota. No código isso é
  tipo, não disciplina: a função-política recebe um objeto que NÃO TEM o desfecho.
- **Ordem real:** as decisões são reavaliadas na sequência em que aconteceram
  (walk-forward dentro da rodada). Walk-forward entre rodadas exige rodada 2 — dito
  no relatório, não escondido.
- **IC honesto:** com n=15 (e recortes de n=2!), intervalo de confiança é LARGO.
  O relatório imprime o intervalo (Wilson, método nomeado) e diz em bom português
  quando a resposta honesta é "sem evidência".
- **Proxies rotulados (D-12):** "valor" aqui é *entrega estruturalmente válida*
  (HTTP 200 + corpo), o label vem de `delivered`/`span.outcome` — o CONTEÚDO não é
  avaliado (LLM não tem replay determinístico). Rótulo no relatório.
- **Premissa de independência, rotulada:** o desfecho observado de cada fonte vale
  para o contrafactual ("se a política X tivesse comprado desta fonte, receberia o
  que nós recebemos") — o vendedor não sabia qual política usávamos. E o estado do
  vínculo foi medido em 21/08 (pós-rodada); premissa: estável no dia.

## As políticas da rodada 1 (todas contra os 15 pontos REAIS do censo)

| Política | Regra (point-in-time) | Por que testar |
|---|---|---|
| `real-rodada1` | teto US$ 1/compra, US$ 20/rodada, aceita não-verificado | a que rodou de verdade — baseline |
| `micro` | só compras ≤ US$ 0,01 | "o barato resolve?" |
| `verified-only` | só vendedor com vínculo N2+ | a que PARECE mais segura |
| `premium` | só compras ≥ US$ 0,10 | a intuição "caro = confiável" |
| `orcamento-5c` | teto de US$ 0,05 na rodada, ordem de chegada | escassez de verdade |

**Resultado negativo esperado (o gate exige ≥1 documentado):** `verified-only` parece
a política prudente e compra ZERO (0/15 vendedores publicam vínculo hoje) — segurança
que custa 100% das entregas. E `premium` compra as 2 mais caras (US$ 0,20 e 0,50) —
das quais UMA falhou: a intuição "caro = confiável" sai com taxa de entrega pior que
o baseline e IC gigante (n=2): sem evidência a favor, evidência anedótica contra.

## Componentes

1. **`src/mesa/laboratorio.py`** — motor puro: `PontoDeDecisao` (congelado, SEM
   desfecho), `Desfecho` (separado), políticas nomeadas, `backtest()` que percorre em
   ordem, `wilson()` para o IC. Zero SQL aqui — o motor é testável em memória.
2. **`scripts/fase7/laboratorio_run.py`** — carrega os 15 pontos reais do livro
   (compra do censo: valor assinado, hash do recurso, ordem temporal; desfecho:
   delivered + liquidação via legs), roda as 5 políticas, imprime a tabela
   comparativa, grava `laboratorio_resultado.json` com TODOS os rótulos (proxies,
   premissas, método do IC) — o relatório com IC honesto do gate.
3. **Testes** — motor: point-in-time por tipo, orçamento walk-forward, Wilson,
   e o caso "política compra nada" (não pode dividir por zero, tem que reportar).

> **GATE 7:** política alternativa avaliada contra o histórico real, relatório com IC
> honesto, ≥1 resultado negativo documentado.

## Riscos, ditos com franqueza

- **n=15 é pequeno.** O Laboratório não vai "descobrir alfa" — vai provar que a
  MÁQUINA de avaliar política existe e é honesta. O valor cresce com cada rodada nova
  do censo (o motor fica pronto; o dado acumula).
- **Recortes minúsculos (n=2)** produzem IC quase [0,1] — o relatório diz isso em
  texto, não deixa o leitor inferir precisão que não existe.
