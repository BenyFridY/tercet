# CARF (OECD) — visão demo 2026

Gerado do livro real em 2026-08-24T01:28:47+00:00.

**O que é:** a visão de conformidade — o que um RCASP reportaria sobre estas
transações a partir de 2027. A mesa NÃO é RCASP; isto NÃO é um reporte. O
documento nasce **OECD11 (New Test Data)** com Warning de DEMONSTRAÇÃO;
identidades SINTÉTICAS; transações REAIS do livro.

- `CryptoTransferOut` · `TransferType CARF603` (compra de bens/serviços,
  guia jul/2025) · **13 transações** · Amount **USD
  0.27** (2 casas, regra do guia) · NumberofUnits 0.272000
  (USDC) · AltValuation CARF1004 (USDC→USD 1:1, estimativa
  DECLARADA — D-12).
- Conferido contra SQL independente: bateu.

## Ressalvas ditas com todas as letras
- Fonte primária: OECD "CARF XML Schema (July 2025) — User Guide for Tax
  Administrations". O **XSD oficial não é público** (CARFXML_v1.5.xsd é
  distribuído às administrações): a validação aqui é o validador próprio codado
  do guia — o mesmo padrão do validador do leiaute da Fase 11. Quando o XSD
  aparecer, pluga `lxml.XMLSchema` (watchlist).
- URIs de namespace por convenção OECD — A CONFIRMAR contra o XSD.
- A tabela BR (DeCripto, TipoTransferenciaSaida) é derivada da família de enums
  CARF, mas a numeração não é 1:1 com jul/2025 (compra = CARF603; 604 é
  collateral).
