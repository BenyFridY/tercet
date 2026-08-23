# Fase 9 — o relatório público do censo: a distribuição (doc de design)

> **(a) ✅ PACOTE PRONTO em 21/08/2026** — `relatorio/x402-buyer-census-round1.md`
> (EN, gerado das fontes por `scripts/fase9/relatorio_build.py`, asserts verdes:
> nenhum número digitado à mão) + `relatorio/post.md` + `relatorio/dados/` (3 JSONs
> brutos). **(b) ⏳ publicação = ação do Beny** — o GATE 9 (publicado + replicável
> + 1 menção orgânica em 2 semanas) fecha com o post. Canais sugeridos no fim
> deste doc; a issue de conformance (notes/) vai PRIMEIRO, o relatório a cita.

*Escrito em 21/08/2026, antes do código, pelo método (D-31). Fontes: PLANO (Fase 9),
D-10 (metodologia publicada), D-12 (proxy rotulado), D-15 (custo completo), D-21
(auditoria, não ranking). Custo da fase: **zero** — o relatório só LÊ o que as
Fases 3–7 produziram.*

## O que é, em linguagem simples

As Fases 3–7 produziram números que ninguém no ecossistema tem, porque ter exige
PAGAR: quem entrega e quem fica com o dinheiro entre os vendedores x402 vivos —
com o recibo on-chain de cada compra. Coletar e não publicar é deixar a
distribuição na mesa. A Fase 9 empacota isso num relatório público replicável.

## Decisões de forma

1. **Língua: inglês.** O público é o ecossistema x402 (Coinbase, vendedores,
   devs) — o mesmo dos 5 posts prontos em `notes/`. O doc de design fica em PT
   (método), o produto em EN (audiência).
2. **Formato: Markdown + dados brutos juntos**, em `relatorio/` — publicável como
   gist/repo/post sem retrabalho. Nada de PDF: replicável se copia.
3. **GERADO, nunca digitado**: `scripts/fase9/relatorio_build.py` monta o texto a
   partir de `censo_fechamento.json` (que nasceu do livro + chain),
   `sondagem_resultado.json` (deriva de preço, MPP), `laboratorio_resultado.json`
   (ICs) e do PRÓPRIO livro (vínculo 0/15 via tabela `verification`). Se um número
   do relatório divergir da fonte, o builder QUEBRA (asserts) — o mesmo padrão do
   gate da Fase 8.
4. **Auditoria, não ranking (D-21):** fatos por fonte, empate publicado como
   empate; nenhuma nota de qualidade — com <5 comparáveis por categoria, ranking
   fino seria mentira estatística.
5. **Honestidades obrigatórias no texto:** n=15 com IC de Wilson; "delivered" é
   proxy estrutural rotulado (D-12 — conteúdo não avaliado); a falha da
   stableenrich pode ser NOSSA (corpo de exemplo genérico levou 400) — vai
   sinalizada; conversão ETH→USD não é feita (sem oráculo — gas em ETH).
6. **Publicar é ação do Beny** (regra do projeto): o pacote sai pronto
   (relatório + post curto + dados), os canais sugeridos ficam no fim do doc.
   O GATE 9 (publicado + replicável + 1 menção orgânica em 2 semanas) só fecha
   com a publicação — esta fase entrega o "(a) pacote pronto".

## O que o relatório contém

- **Os 4 números** com recibo: 15/15 respondem · 15/15 cotam válido · 13/15
  entregam · 13/15 cobraram (= exatamente as que entregaram).
- **Tabela por fonte**: anunciado vs cotado (deriva!), pago, entregou, cobrou,
  link do tx no Basescan.
- **Achados**: (1) deriva de preço + o caso dripstack (cotou 2,5× o anunciado e
  re-pediu 402 DEPOIS de pago — e mesmo assim não cobrou: a autorização expirou);
  (2) as falhas não ficaram com o dinheiro — expiração EIP-3009 como proteção do
  comprador; (3) 0/15 provam o vínculo domínio⇔endereço (a política "só
  verificados" compra NADA hoje — gancho da nossa proposta de extensão);
  (4) MPP nos mesmos endpoints; (5) gas do facilitator observado (comprador paga
  só o preço); (6) micro-compras entregam a 16× menos custo/entrega (IC largo,
  dito); (7) custo por entrega US$ 0,0209.
- **Replicabilidade**: carteira pagadora pública (0x637f…B2DC) — qualquer um
  re-deriva a rodada SÓ da chain; dados brutos anexos; dump de período carimbado
  (RFC3161 + OTS) + verificador independente citados.
- **Limites e disclosure**: 1 rodada, 1 dia, capital próprio, valores mínimos,
  sem afiliação com nenhuma fonte.

## Saídas

| Arquivo | O que é |
|---|---|
| `relatorio/x402-buyer-census-round1.md` | o relatório (EN, gerado) |
| `relatorio/post.md` | versão curta p/ post (EN, gerada) |
| `relatorio/dados/*.json` | dados brutos copiados na geração (fechamento, sondagem, laboratório) |

> **GATE 9:** publicado, replicável por terceiro, e ≥1 menção orgânica do
> ecossistema em 2 semanas. Esta fase fecha o "(a)"; o "(b)" é do Beny.

## Canais sugeridos (decisão do Beny)

1. GitHub: gist ou repo `x402-buyer-census` (dados + MD — replicável de verdade).
2. X: o `post.md`, linkando o gist. 3. Discord do x402 / discussão no repo da
Coinbase — junto com os 5 posts já prontos (a issue de conformance PRIMEIRO, que
o relatório cita).
