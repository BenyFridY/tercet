-- 0001_init.sql — o livro (v0). Schema do PLANO.md com as correções de 19/08.
-- Append-only POR CONSTRUÇÃO: o código só faz INSERT nas tabelas do livro.
-- Exceção registrada (D-06): authz.state é a única coluna mutável do v0.
-- Tabelas operacionais (meta_migration, collector_cursor) não são o livro.

-- 0. A árvore de atribuição (D-02). Compra nunca guarda time/tarefa como coluna:
--    pendura num span, e a atribuição soma a árvore.
CREATE TABLE span (
  trace_id        text NOT NULL,      -- ID OpenTelemetry (32 hex), não inventado aqui
  span_id         text NOT NULL,      -- 16 hex
  parent_span_id  text,               -- NULL na raiz
  name            text NOT NULL,
  agent_ref       text,
  attributes      jsonb,
  started_utc     timestamptz NOT NULL,
  ended_utc       timestamptz,
  outcome         text,               -- success | failure | retry | unknown (label do TCA)
  PRIMARY KEY (trace_id, span_id)
);

-- 1. O que aconteceu no transporte. Agnóstico de trilho E de transporte.
CREATE TABLE request (
  id                       uuid PRIMARY KEY,
  ts_utc                   timestamptz NOT NULL,
  rail                     text        NOT NULL,  -- x402 | mpp | card | invoice | pix
  resource_key_hash        bytea       NOT NULL,  -- D-11: sha256 do canônico; URL em claro NUNCA
  method                   text        NOT NULL,
  status_http              int,                   -- NULL quando transport != http (D-01)
  body_sha256              bytea,                 -- só hash. NUNCA o corpo.
  body_bytes               int,
  content_type             text,
  etag                     text,
  last_modified_utc        timestamptz,
  delivered                boolean     NOT NULL,
  delivered_before_settle  boolean,               -- o footgun nº 1, medido como coluna
  trace_id                 text        NOT NULL,
  span_id                  text        NOT NULL,
  transport                text        NOT NULL,  -- http | mcp | function
  tool_name                text,
  origin                   text        NOT NULL,  -- direct | delegated
  origin_ref               text,
  origin_receipt_sig       bytea,
  FOREIGN KEY (trace_id, span_id) REFERENCES span(trace_id, span_id)
);
CREATE INDEX request_span_idx ON request (trace_id, span_id);

-- 2. O que o vendedor pediu. A cotação NUNCA é sobrescrita.
CREATE TABLE quote (
  id                   uuid PRIMARY KEY,
  request_id           uuid     NOT NULL REFERENCES request(id),
  amount_minor         bigint   NOT NULL,  -- inteiro, unidade mínima. Nunca float.
  decimals             smallint NOT NULL,  -- nota: o wire V2 não carrega decimals; gravamos o
                                           -- canônico validado no contrato (D-07)
  asset_network_caip2  text     NOT NULL,  -- FDS 1 = eip155:84532 (Base Sepolia)
  asset_contract       text     NOT NULL,  -- endereço. NUNCA o símbolo.
  pay_to               text     NOT NULL,
  scheme               text     NOT NULL,  -- exact | upto | ...
  work_unit            text,               -- NULL = vendedor não declarou
  work_qty             numeric
);
CREATE INDEX quote_request_idx ON quote (request_id);

-- 3. A autorização. GENÉRICA — o agnosticismo de trilho vive aqui.
--    'authz' porque AUTHORIZATION é palavra reservada no Postgres.
CREATE TABLE authz (
  id                    uuid   PRIMARY KEY,
  quote_id              uuid   NOT NULL REFERENCES quote(id),
  rail                  text   NOT NULL,
  payer_ref             text   NOT NULL,  -- endereço EVM | customer_id | token. Opaco.
  authorized_max_minor  bigint NOT NULL,
  valid_from_utc        timestamptz,
  valid_until_utc       timestamptz,
  scope_hash            bytea,
  principal_ref         text,
  principal_evidence    jsonb,
  rail_evidence         jsonb  NOT NULL,  -- x402: {authorization{from,to,value,nonce,...}, signature}
  state                 text   NOT NULL   -- quoted|authorized|verified|settled|failed|orphan
);
CREATE INDEX authz_quote_idx ON authz (quote_id);
CREATE INDEX authz_x402_key
  ON authz (((rail_evidence -> 'authorization') ->> 'from'),
            ((rail_evidence -> 'authorization') ->> 'nonce'))
  WHERE rail = 'x402';

-- 4. Um evento de liquidação. MUITOS pagamentos podem cair aqui. (Preenchida pelo COLETOR — T4.)
CREATE TABLE settlement (
  id                  uuid   PRIMARY KEY,
  rail                text   NOT NULL,
  external_ref        text   NOT NULL,  -- tx_hash | payment_intent | capture_id
  network_caip2       text,
  block_number        bigint,
  block_ts_utc        timestamptz,
  confirmations       int,
  finality            text   NOT NULL,  -- pending | final | reorged (reorged é caminho normal)
  facilitator_ref     text,
  total_amount_minor  bigint NOT NULL,
  fee_amount_minor    bigint,
  fee_asset_contract  text,
  UNIQUE (rail, network_caip2, external_ref)  -- idempotência do coletor: rodar 2x = mesmas linhas
);

-- 5. A ponte muitos-para-um. A TABELA QUE SALVA O PROJETO.
CREATE TABLE settlement_leg (
  settlement_id        uuid   NOT NULL REFERENCES settlement(id),
  authorization_id     uuid   NOT NULL REFERENCES authz(id),
  settled_amount_minor bigint NOT NULL,  -- NUNCA sobrescreve quote.amount_minor
  PRIMARY KEY (settlement_id, authorization_id)
);

-- 6. Verificação: evidência, não booleano.
CREATE TABLE verification (
  id              uuid  PRIMARY KEY,
  subject_type    text  NOT NULL,  -- pay_to | agent_identity | delivery | facilitator
  subject_ref     text  NOT NULL,
  method          text  NOT NULL,
  result          text  NOT NULL,  -- verified | failed | unknown
  evidence        jsonb NOT NULL,
  verified_at_utc timestamptz NOT NULL,
  expires_at_utc  timestamptz     -- verificação decai
);

-- Operacional (fora do livro): cursor do coletor (T4).
CREATE TABLE collector_cursor (
  name        text   PRIMARY KEY,
  last_block  bigint NOT NULL,
  updated_utc timestamptz NOT NULL
);
