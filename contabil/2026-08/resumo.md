# Export contábil — 2026-08

Gerado do livro real em 2026-08-24T01:28:46+00:00.

- **13 compras** x402 liquidadas na mainnet (competência pela data
  de São Paulo — a mesma régua da Fase 11).
- Total exato **USD 0.272** → lançamento de **USD 0.27**
  (2 casas, ROUND_HALF_UP; a diferença está declarada na narrativa).
- Débito `Despesas:Compras de agentes (x402)` × crédito `Ativos digitais:USDC`.
- Conferido contra SQL independente (fuso recomputado no Postgres): bateu.

## Ressalvas ditas com todas as letras
- Regime de CAIXA (só liquidado); só mainnet; sem ganho/perda de disposição
  (USDC ao valor de face) — recortes do v0, doc `docs/fase13-export.md`.
- `journal-qbo.csv`: leiaute do artigo oficial da Intuit.
- `journal-xero.csv`: leiaute de fontes secundárias convergentes — **conferir com
  o template baixado de dentro do Xero antes de importar**; TaxRate padrão
  "Tax Exempt" (ajuste à região da organização).
- `detalhe-compras.csv` é a ponte de auditoria: soma exatamente o total (6 casas)
  e liga cada valor ao tx hash.
