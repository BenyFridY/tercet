-- 0002_eventos.sql — Fase 4: estado vira EVENTO (fecha a exceção do D-06).
-- authz.state e settlement.confirmations/finality continuam preenchidos por
-- compatibilidade até a Fase 6, mas a VERDADE passa a ser a sequência de eventos.
-- Ambas append-only por construção (o código só INSERE).

CREATE TABLE authz_event (
  id                uuid PRIMARY KEY,
  authorization_id  uuid NOT NULL REFERENCES authz(id),
  ts_utc            timestamptz NOT NULL,
  kind              text NOT NULL,   -- quoted|authorized|verified|settled|failed|orphan
  detail            jsonb
);
CREATE INDEX authz_event_authz_idx ON authz_event (authorization_id, ts_utc);

CREATE TABLE settlement_event (
  id             uuid PRIMARY KEY,
  settlement_id  uuid NOT NULL REFERENCES settlement(id),
  ts_utc         timestamptz NOT NULL,
  kind           text NOT NULL,      -- observed|confirmed|final|reorged
  block_number   bigint,
  confirmations  int,
  detail         jsonb
);
CREATE INDEX settlement_event_settlement_idx ON settlement_event (settlement_id, ts_utc);
