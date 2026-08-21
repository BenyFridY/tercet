# Canonicalização do livro (Fase 4, T1) — as regras exatas, decididas ANTES do código

*Este doc é normativo: `src/mesa/integridade.py` implementa exatamente isto, e o
verificador offline reimplementa exatamente isto sem importar o mesa. Qualquer mudança
aqui depois do primeiro fechamento de período é BREAKING e precisa de decisão registrada.*

## A linha canônica

O hash de uma linha do livro é:

```
row_hash = sha256( rfc8785( {"tabela": <nome>, "linha": {<campos>}} ) )
```

onde `rfc8785` é a serialização JSON Canonicalization Scheme (RFC 8785, lib `rfc8785`),
codificada em UTF-8.

## Codificação de tipos (Postgres → JSON)

| Tipo | Regra | Exemplo |
|---|---|---|
| `uuid` | string minúscula com hífens | `"0d9f…"` |
| `bytea` | `"0x"` + hex minúsculo | `"0x8f3a…"` |
| `timestamptz` | ISO-8601 em UTC com microssegundos SEMPRE (`isoformat(timespec="microseconds")`), sufixo `+00:00` | `"2026-08-21T15:02:11.000000+00:00"` |
| `jsonb` | embutido como JSON (o RFC 8785 canonicaliza por dentro) | `{...}` |
| `bigint`/`int`/`smallint` | número JSON inteiro | `10000` |
| `numeric` | **string** decimal (nunca float — RFC 8785 + float é a pegadinha nº 1) | `"1.5"` |
| `boolean` | `true`/`false` | |
| `text` | string como está | |
| `NULL` | `null` — o campo SEMPRE aparece (conjunto de chaves fixo por tabela) | |

## Campos por tabela — e a exclusão dos mutáveis

Entram TODOS os campos da tabela, **exceto os mutáveis do v0** (a verdade deles passa a
ser a sequência de eventos da migration 0002):

- `authz`: **exclui `state`** (mutável pela exceção registrada do D-06; verdade = `authz_event`)
- `settlement`: **exclui `confirmations` e `finality`** (verdade = `settlement_event`)
- demais tabelas (`span`, `request`, `quote`, `settlement_leg`, `verification`,
  `authz_event`, `settlement_event`): todos os campos.

`row_id` no elo: o valor da chave primária como string; chaves compostas juntam com `|`
na ordem da declaração da PK (`span`: `trace_id|span_id`; `settlement_leg`:
`settlement_id|authorization_id`).

## A corrente

```
link_hash[n] = sha256( link_hash[n-1] || row_hash[n] )      (|| = concatenação de bytes)
```

- **Genesis (seq 0):** `prev = 32 bytes zero`; `row_hash = sha256(texto UTF-8 do doc de
  genesis)` — o doc de genesis registra a data, a regra de ordem do backfill e o hash
  deste arquivo de canonicalização. Fica gravado em `ledger_hash.row_id='genesis'`.
- `seq` é inteiro sem buracos; escrita concorrente que colidir no `seq` (PK) tenta de
  novo (até 3×) — single-writer é o caso normal do v0.

## Ordem do backfill (decisão irreversível, gravada no genesis)

As linhas pré-existentes (Fases 1–3) entram na corrente na ordem:

1. tabela, na sequência fixa: `span` → `request` → `quote` → `authz` → `settlement` →
   `settlement_leg` → `verification`;
2. dentro da tabela: pelo timestamp natural quando existe (`span.started_utc`,
   `request.ts_utc`, `settlement.block_ts_utc`) e, empatado ou sem timestamp, pela
   string do `row_id` em ordem lexicográfica.

A ordem é arbitrária ONDE não há timestamp — o que importa é que é determinística e está
declarada aqui e no genesis. Elos de backfill têm `ts_utc` = hora do backfill (não da
linha original; a linha original guarda o próprio tempo).

## A raiz de Merkle do período

- Folhas: os `link_hash` do período, em ordem de `seq`.
- Nível acima: `sha256(esq || dir)`; nº ímpar de nós duplica o último; 1 folha ⇒ raiz = folha.
- **Período = faixa contígua de `seq`** *(ajuste de 21/08, ANTES do 1º fechamento —
  a definição original por "dia UTC do ts do elo" quebrava se o dia fechasse no meio)*:
  o fechamento pega TODOS os elos ainda não fechados (`first_seq` = último `last_seq`+1,
  ou 0 no primeiro; `last_seq` = seq máximo atual) e é ROTULADO pelo dia UTC do
  fechamento. No máximo um fechamento por dia (PK). Período fechado NUNCA reabre —
  elo posterior cai no fechamento seguinte.
