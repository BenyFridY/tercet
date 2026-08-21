-- 0003_integridade.sql — Fase 4: a corrente de hash e o fechamento de período.
-- Regras exatas de canonicalização: docs/canonicalizacao.md (normativo).
-- Tudo aqui é append-only por construção; period_close nunca reabre.

CREATE TABLE ledger_hash (
  seq         bigint PRIMARY KEY,      -- 0 = genesis; depois 1,2,3… sem buracos
  table_name  text  NOT NULL,
  row_id      text  NOT NULL,          -- PK da linha; composta junta com '|'
  row_hash    bytea NOT NULL,          -- sha256 do JSON canônico (RFC 8785)
  prev_hash   bytea NOT NULL,          -- link_hash do elo anterior (genesis: 32 zeros)
  link_hash   bytea NOT NULL,          -- sha256(prev_hash || row_hash)
  ts_utc      timestamptz NOT NULL,
  UNIQUE (table_name, row_id)
);

CREATE TABLE period_close (
  period_date  date  PRIMARY KEY,      -- dia UTC do ts_utc dos elos
  first_seq    bigint NOT NULL,
  last_seq     bigint NOT NULL,
  merkle_root  bytea NOT NULL,
  closed_utc   timestamptz NOT NULL
);

-- carimbos como eventos (a prova OTS se completa DEPOIS — vira linha nova, nunca UPDATE)
CREATE TABLE period_stamp (
  id           uuid PRIMARY KEY,
  period_date  date NOT NULL REFERENCES period_close(period_date),
  kind         text NOT NULL,          -- rfc3161 | ots | ots-upgrade
  proof        bytea NOT NULL,
  ts_utc       timestamptz NOT NULL
);
CREATE INDEX period_stamp_period_idx ON period_stamp (period_date, kind);
