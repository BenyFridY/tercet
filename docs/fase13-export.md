# Fase 13 / itens 2 e 3 — export contábil universal + CARF (doc de design)

> ✅ **GATE 13b VERDE em 23/08/2026** — `contabil/2026-08/` gerado do livro real:
> 13 compras mainnet → lançamento USD 0,27 (exato 0,272000; ROUND_HALF_UP
> declarado), débito==crédito provado, detalhe soma no exato e liga cada valor ao
> tx hash; conferência independente (fuso de SP recomputado no Postgres) bateu;
> adulteração acusada nomeando o campo. Motor: `src/mesa/contabil.py`.
>
> ✅ **GATE 13c VERDE em 23/08/2026** — `fiscal/carf/2026/carf-demo-test-data.xml`
> gerado do livro real: CryptoTransferOut CARF603 · 13 transações · USD 0,27 (2
> casas) · 0,272000 unidades (6 casas) · CARF1004; nasce **OECD11 + Warning de
> DEMONSTRAÇÃO**; validador do guia jul/2025 limpo no verdadeiro e acusando 3
> sabotagens. Motor: `src/mesa/carf.py`. Suíte: **128 testes**, mypy strict, ruff.

*Escrito em 23/08/2026, antes do código, pelo método (D-31). "Pode seguir" do Beny
sobre a proposta de `docs/alcance-internacional.md`. Fontes primárias desta fase:
o guia OFICIAL "CARF XML Schema (July 2025) — User Guide for Tax Administrations"
(OECD, 48 págs, baixado de oecd.org e lido); artigo oficial da Intuit sobre
importação de lançamentos no QuickBooks Online. O template do Xero vem de fontes
secundárias convergentes (o oficial só baixa dentro do produto) — dito com todas
as letras no resumo gerado.*

## Item 2 — export contábil universal (partidas dobradas do livro)

**Para quem:** o comprador em QUALQUER jurisdição. Nos EUA (o maior mercado) não
existe arquivo mensal de governo — o que a empresa precisa é o lançamento de diário
que fecha com a contabilidade dela (QuickBooks/Xero/NetSuite/ERP).

**O modelo contábil, dito com franqueza (v0):**
- **Regime de caixa**: só compra LIQUIDADA entra (entregue-sem-cobrar não vira
  passivo no v0 — está no livro e nos vereditos, não no diário).
- **Só mainnet**: testnet nunca é contabilidade.
- **Sem ganho/perda de disposição**: USDC entra pelo valor de face (1:1 USD). A
  base de custo é problema do módulo fiscal de cada país; o livro guarda tudo que
  o cálculo exigirá (data, valor, tx).
- **Competência pela data de São Paulo** — a MESMA régua da Fase 11 (uma régua só
  para "agosto" em todo o produto; documentado, trocável).
- **Agregação por competência**: micro-pagamentos de $0,001 viram $0,00 nas 2 casas
  decimais dos sistemas contábeis. Por isso o diário importável tem **UM lançamento
  por competência** (débito despesa × crédito USDC, total arredondado ROUND_HALF_UP
  em 2 casas) e o **detalhe compra-a-compra** (com 6 casas e tx hash) sai num CSV
  irmão — a ponte de auditoria que liga o lançamento à evidência.

**Formatos gerados por competência** (`contabil/<aaaa-mm>/`):
| Arquivo | Formato | Fonte do leiaute |
|---|---|---|
| `journal-universal.csv` | canônico nosso (documentado no cabeçalho) | — |
| `journal-qbo.csv` | Journal No. / Journal Date / Account Name / Description / Debits / Credits | artigo oficial Intuit |
| `journal-xero.csv` | Narration / Date / Description / AccountCode / TaxRate / Amount (sinal: + débito, − crédito) | secundárias convergentes — CONFERIR no produto |
| `detalhe-compras.csv` | uma linha por compra: data SP, domínio, agente, USD exato (6c), tx | o livro |
| `resumo.md` | o que foi gerado, as ressalvas, a conferência | — |

**Invariantes que `validar()` morde:** débito == crédito (por lançamento e no
total); valor > 0 (competência abaixo de $0,005 → erro nomeado, não silêncio);
data dentro da competência; soma do detalhe (6c) == total exato do lançamento.

## Item 3 — CARF: a visão OECD das nossas transações

**O enquadramento honesto:** o CARF é reportado por **RCASPs** (provedores) às
administrações; nós NÃO somos RCASP e não reportamos nada. O que o módulo gera é a
**visão de conformidade**: "o que um RCASP reportaria de você" — reconciliação
antecipada com o que o fisco vai receber de terceiros a partir de 2027. Dados de
transação REAIS do livro; identidades SINTÉTICAS rotuladas; e o documento nasce
marcado **OECD11 = New TEST Data** (o guia reserva OECD10–13 para teste — o
`tpAmb=2` do CARF), com `Warning` dizendo DEMONSTRAÇÃO.

**Mapeamento (do guia, à letra):** a compra x402 é `CryptoTransferOut` com
`TransferType = CARF603` ("Purchase of goods or services", abaixo do limiar de
retail payment), agregada por período: `NumberofTransactions` (inteiro), `Amount`
(valor justo em fiat, **2 casas**, `currCode` ISO 4217), `NumberofUnits` (**até 6
casas**), `AltValuation = CARF1004` (estimativa razoável — USDC→USD 1:1 declarada,
a MESMA ressalva da Fase 11). `MessageSpec` completo: MessageType=CARF,
MessageTypeIndic=CARF701, ReportingPeriod=último dia do ano, MessageRefID começando
com país-remetente + ano + país-destinatário (regra do guia).

**Achado da fase (registrado):** a tabela BR do DeCripto (TipoTransferenciaSaida)
é derivada da família de enums CARF — mas a numeração NÃO é 1:1 com a versão
jul/2025 da OECD, onde compra de bens/serviços é **CARF603** (604 é collateral).
O doc `alcance-internacional.md` foi corrigido nesse detalhe.

**XSD oficial:** `CARFXML_v1.5.xsd` + `OecdCARFTypes_v1.0.xsd` + `IsoCARFTypes_v1.0.xsd`
existem (Annex B do guia), mas são distribuídos às administrações — não há download
público (procurado em 23/08: oecd.org bloqueia, nenhum espelho legítimo). Então o
v0 valida com **validador próprio codado do guia** (o mesmo padrão da Fase 11, cujo
validador do leiaute pipe também é nosso) e a URI de namespace fica declarada como
convenção OECD a CONFIRMAR. No dia em que o zip aparecer: pluga `lxml.XMLSchema`
como a NFS-e (item de watchlist).

## GATEs

> **GATE 13b (contabil):** os 4 CSVs gerados do livro real; débito==crédito provado;
> total == SQL independente (fuso de SP recomputado no Postgres); detalhe soma no
> exato; adulteração → `validar` acusa nomeando o campo. Suíte + mypy strict verdes.

> **GATE 13c (carf):** XML gerado do livro real (transações reais, identidade
> sintética, OECD11 + Warning); agregado bate com SQL independente; validador
> morde adulteração (enum inventado, decimais errados, MessageRefID fora do
> padrão); tudo rotulado. Suíte + mypy strict verdes.
