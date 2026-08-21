# Fase 4 — o recibo verificável (doc de design)

> ✅ **GATE 4 VERDE em 21/08/2026** — o verificador offline (`verificador/verificar.py`,
> sem imports do mesa) validou o período fechado (376 elos, raiz carimbada por RFC3161
> **e** OpenTimestamps 4/4 calendários) e **detectou 1 bit adulterado na linha exata**
> (`gate4_teste.py`: seq 188 acusada como seq 188). Corrente com 385 elos íntegros;
> escrita nova entra na corrente em tempo real. Primeira implementação pública da
> extensão oficial `offer-and-receipt` emitida e verificada sobre venda real; MPP real
> e AP2 sintético ingeridos SEM migration.
> *Correção de desenho registrada:* recibos oficiais são assinados pelo VENDEDOR — a
> emissão foi sobre a venda em que somos o vendedor, não sobre as compras do censo
> (onde o achado é: 0/15 vendedores emitem a extensão).

*Escrito em 21/08/2026, antes de qualquer código, pelo método do programa (D-31).
Fontes: PLANO.md (seção Fase 4), DECISOES.md (D-06, D-27, D-30), e os dados REAIS que o
censo da Fase 3 acabou de gravar (inclusive headers MPP capturados de produção).
Esta fase não gasta um centavo — carimbos de tempo são serviços gratuitos.*

## O que é esta fase, em linguagem direta

Hoje o livro é confiável porque **nós** dizemos que ele é: as tabelas são append-only por
disciplina de código, e quem quiser checar precisa confiar no nosso banco. A Fase 4 vira
esse jogo: **o livro passa a provar a si mesmo**. Qualquer terceiro — um auditor, um
cliente, um cético — pega um período fechado do livro e verifica com um script pequeno,
**sem confiar na gente**, três coisas:

1. **Nada foi alterado** — cada linha carrega o hash da anterior (corrente de hashes);
   mudar 1 bit de uma linha antiga quebra a corrente inteira dali pra frente.
2. **Nada foi alterado DEPOIS** — no fim de cada período, a raiz de Merkle do período
   recebe **dois carimbos de tempo independentes** (um servidor RFC3161 e o
   OpenTimestamps, que ancora no Bitcoin). Dois relógios de terceiros provando "este
   livro já existia neste estado antes das X horas".
3. **Cada compra aconteceu mesmo** — o recibo de cada pagamento é verificável offline
   (assinatura EIP-712/EIP-191 recuperável + tx hash conferível na chain).

É o ativo de longo prazo do projeto: a posição de árbitro neutro só se sustenta se o
árbitro não puder trapacear nem que queira.

## Por que agora (e não depois)

- O livro acabou de ganhar as **primeiras compras reais** (censo, Fase 3). É o momento de
  congelar a integridade ANTES do histórico crescer — backfill de corrente de hash em
  livro pequeno é trivial, em livro grande é projeto.
- O censo nos deu **material real de ingestão**: headers MPP (`WWW-Authenticate: Payment`)
  capturados de produção, e 13 liquidações on-chain nossas para emitir recibos de verdade.
- A extensão oficial `extension-offer-and-receipt` do x402 está **aprovada com ZERO
  implementações** (D-27) — quem shipar primeiro ocupa. Esta fase shipa.

## Os componentes (todos no repo `mesa/`)

1. **Eventos em vez de colunas mutáveis** — fecha a exceção do D-06. Hoje `authz.state`
   sofre UPDATE (única mutação do v0) e `settlement.confirmations/finality` idem. Entram
   `authz_event` e `settlement_event` (append-only): estado vira "último evento", reorg
   vira **evento normal** (não surpresa). As colunas antigas continuam preenchidas por
   compatibilidade até a Fase 6, mas a VERDADE passa a ser a sequência de eventos.
2. **Corrente de hash por linha** — tabela `ledger_hash` (seq global, tabela, id da linha,
   hash da linha canônica RFC 8785, hash do elo anterior, hash do elo). Toda escrita no
   livro ganha o elo na MESMA transação. O livro existente (Fases 1–3) entra por
   **backfill determinístico** (ordem de timestamp; documentado no próprio elo genesis).
3. **Fechamento de período** — `period_close`: janela diária UTC; raiz de Merkle de todos
   os elos da janela; carimbo RFC3161 (freeTSA) + prova OpenTimestamps da MESMA raiz.
   Período fechado NUNCA reabre — correção entra como evento novo no período seguinte.
4. **O verificador offline puro** — `verificador/` (pasta própria, dependências mínimas:
   hashlib + json canônico + eth-account): recebe um dump JSON do período + a raiz + os
   carimbos, e responde VERDE ou VERMELHO. ~100 linhas legíveis — o ponto é um terceiro
   LER e confiar no script, não em nós.
5. **Os três formatos de recibo (D-27: ingerir e emitir, nunca formato próprio)**
   - **Emitir**: `extension-offer-and-receipt` oficial do x402 — nosso `mesa-recibo-v0`
     (Fase 2) migra pra ele; primeiros recibos emitidos sobre as 13 compras REAIS do censo.
   - **Ingerir**: MPP `Payment-Receipt`/`WWW-Authenticate: Payment` (amostras reais já
     capturadas no censo) e AP2 mandates (amostra sintética do spec) → viram `authz` /
     `rail_evidence` no livro sem migration (o agnosticismo de trilho pagando).

## Schema (esta fase TEM migrations — as primeiras desde a 0001)

`0002_eventos.sql` (authz_event, settlement_event) e `0003_integridade.sql`
(ledger_hash, period_close). Regra mantida: nada de ALTER destrutivo; as tabelas novas
são append-only por construção. O que NÃO muda: request/quote/authz/settlement/span.

## As etapas

| # | Etapa | O quê | Pronto quando |
|---|---|---|---|
| T1 ✅ 21/08 | Fundação | deps + migrations 0002/0003 + `docs/canonicalizacao.md` (normativo, ANTES do código) | verde; migrations idempotentes |
| T2 ✅ 21/08 | A corrente | elo em toda escrita nova (db.py + coletor, mesma transação) + backfill das Fases 1–3 (375 linhas) com autoverificação | teste puro: 1 bit → quebra no elo certo (`test_integridade.py`) |
| T3 ✅ 21/08 | O fechamento | período 2026-08-21 (seq 0..375, contém o censo) fechado; raiz carimbada por freeTSA (4621B DER, cert embutido) + OTS 4/4 calendários (via LIB — o CLI quebra no Windows) | 2 carimbos independentes gravados |
| T4 ✅ 21/08 | O verificador | `verificador/verificar.py` (sem imports do mesa) + `exportar_periodo.py` + `gate4_teste.py` | **GATE 4 ✅**: dump limpo VERDE; 1 bit virado → VERMELHO na seq exata |
| T5 ✅ 21/08 | Os 3 formatos | `recibo_x402.py` (extensão oficial, EIP-712, 1ª implementação) emitido+verificado sobre venda real NOSSA; MPP real (desafio Tempo do censo) e AP2 sintético rotulado ingeridos | zero migrations novas; achado: 0/15 vendedores do censo emitem a extensão |

> **GATE 4:** um TERCEIRO verifica um período fechado com um script de ~100 linhas, sem
> confiar na gente — e detecta 1 bit alterado.

## Custos declarados

- **Dinheiro: zero.** freeTSA e OpenTimestamps são gratuitos; nenhuma compra nova.
- **LLM: zero** — é tudo código determinístico.
- A vigilância da Fase 3 (2 autorizações pendentes) continua em paralelo, grátis.

## Riscos, ditos com franqueza

- **Canonicalização é onde mora o bug**: JSON canônico (RFC 8785) tem pegadinhas
  (floats, unicode). Mitigação: valores monetários já são inteiros no livro (invariante),
  e o doc de canonicalização vem ANTES do código na T1.
- **Backfill é decisão irreversível**: a ordem escolhida vira genesis para sempre.
  Por isso ela é documentada dentro do próprio elo genesis.
- **OpenTimestamps confirma em ~horas** (ancora no Bitcoin) — o carimbo RFC3161 é
  instantâneo e segura o gate; a prova OTS completa-se sozinha depois.
- **AP2 sem amostra real**: mandates entram por amostra sintética do spec, rotulada como
  sintética (D-12 — proxy rotulado como proxy).
