-- 0004_fiscal.sql — Fase 11: PTAX point-in-time.
-- fx_ptax é dado de REFERÊNCIA externo (refetchável do BCB), não é o livro:
-- fica FORA da corrente de hash de propósito (docs/fase11.md). Append-only por
-- convenção — a cotação de fechamento de uma data nunca muda depois de publicada.

CREATE TABLE fx_ptax (
  data_cotacao  date PRIMARY KEY,          -- a data da cotação (dia útil, calendário BR)
  compra        numeric(12,6) NOT NULL,
  venda         numeric(12,6) NOT NULL,    -- a que o motor fiscal usa (venda, fechamento)
  fonte         text NOT NULL,             -- ex.: 'bcb-ptax-CotacaoDolarDia'
  fetched_utc   timestamptz NOT NULL
);
