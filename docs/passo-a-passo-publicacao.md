# Passo a passo — o que falta é publicação (≈ 1h manual, ou "posta" + 5 min)

> **ATUALIZAÇÃO 21/08 à noite:** o Beny pediu que o Claude poste da conta dele.
> O `gh` está logado como **BenyFridY** (pessoal). Os corpos FINAIS, byte a byte,
> estão em `notes/publicar/` — o que for aprovado é o que sai. Cada afirmação
> técnica foi re-verificada contra o mundo de hoje (upstream @ dd927a2, recibo
> conferido na chain, OTel #443 aberto). O branch do PR já está commitado em
> `C:\dev\x402-fork` (fix/mcp-2.0-compat, 3 arquivos, +2 testes de regressão
> passando). O X continua sendo só seu (sem acesso). Correção achada na
> verificação: o draft de DNS **expirou** (2026-05-10) — o C2 virou e-mail ao
> autor oferecendo a seção para uma -01 (prioridade baixa).

*Escrito em 21/08/2026. Tudo que era código/dado/texto está PRONTO nos commits.
O que resta são ações externas (posts, PR, e-mail) — que por regra do projeto são
suas, da sua conta. A ordem abaixo importa (o item 1 é citado pelos outros).
Ao final de cada bloco, me mande os LINKS — eu atualizo os gates e o relatório.*

---

## Bloco A — os 3 posts no repo da Coinbase (github.com/coinbase/x402) · ~30 min

### A1. A issue de conformance (5 min) — VAI PRIMEIRO, os outros citam ela
- [ ] Abrir https://github.com/coinbase/x402/issues → **New issue**
- [ ] Título: `x402-over-MCP conformance findings — Python SDK vs TypeScript SDK`
- [ ] Colar o conteúdo de `mesa\notes\x402-mcp-conformance-report.md`
      (SEM o bloco em itálico do topo — aquilo é nota interna nossa)
- [ ] Enviar e **guardar o link da issue**

### A2. O PR de conserto do SDK Python (20 min — ou 5, se eu preparar o patch)
- [ ] Fork de https://github.com/coinbase/x402 (botão Fork)
- [ ] No terminal:
      ```
      git clone https://github.com/SEU_USUARIO/x402 C:\dev\x402-fork
      cd C:\dev\x402-fork
      git checkout -b fix/mcp-2.0-compat
      ```
- [ ] Editar `python/x402/mcp/server.py` e `python/x402/mcp/utils.py` conforme os
      dois blocos de código em `mesa\notes\sdk-python-fix-pr.md` (seção "Proposed
      changes")
- [ ] `git commit` + `git push -u origin fix/mcp-2.0-compat` → abrir o PR com o
      título e corpo do mesmo arquivo, **linkando a issue do A1** onde ele pede
- 💡 **Atalho:** me diga "prepara o patch" que eu clono, aplico as mudanças e
  deixo o branch pronto em `C:\dev\x402-fork` — você só revisa e dá o push.

### A3. A proposta de extensão payTo Binding (5 min)
- [ ] Nova issue no mesmo repo (ou Discussion, se preferir o tom mais leve)
- [ ] Título: `Extension proposal: payTo Binding (domain⇔payout-address binding)`
- [ ] Colar `mesa\notes\x402-extension-payto-binding.md` (sem o itálico do topo)
- [ ] O trunfo do texto: **0/15 vendedores vivos publicam prova de posse do payTo**
      — dado nosso, medido, com recibo. Guardar o link.

## Bloco B — publicar o relatório do censo (GATE 9b) · ~15 min

### B1. O repo público com o relatório + dados
- [ ] No terminal (staging fora do repo privado):
      ```
      mkdir C:\dev\x402-buyer-census
      copy mesa\relatorio\x402-buyer-census-round1.md C:\dev\x402-buyer-census\README.md
      xcopy mesa\relatorio\dados C:\dev\x402-buyer-census\dados\ /E /I
      cd C:\dev\x402-buyer-census
      git init && git add -A && git commit -m "x402 buyer census - round 1"
      gh repo create x402-buyer-census --public --source . --push
      ```
- [ ] (Opcional, recomendado) ANTES do B1: me passe o link do A3 — eu regenero o
      relatório com a proposta LINKADA e você publica a versão final.

### B2. O post no X (5 min)
- [ ] Abrir `mesa\relatorio\post.md`, trocar `[LINK]` pela URL do repo do B1
- [ ] Postar. O gate espera **1 menção orgânica em até 2 semanas** — o relógio
      começa aqui.

## Bloco C — os 2 restantes · ~10 min

### C1. Comentário no OTel #443 (3 min)
- [ ] Abrir o PR #443 do repo open-telemetry (semantic-conventions / genai — o
      link de referência está no seu histórico do D-28)
- [ ] Colar o texto de `mesa\notes\otel-443-comment-draft.md` (só a parte após o `---`)

### C2. E-mail ao autor do draft de DNS discovery (5 min · prioridade BAIXA)
- [ ] O draft EXPIROU no datatracker (2026-05-10) — verificado 21/08 à noite
- [ ] E-mail pronto (destinatário, assunto e corpo) em `notes\publicar\c2-email.md`
      — oferece a seção para uma eventual revisão -01
- [ ] O Claude pode deixar como RASCUNHO no seu Gmail; enviar é seu

## Bloco D — opcionais locais (quando quiser, 5 min cada)

- [ ] `uv run python scripts/fase8/aprovacao_demo.py` num terminal (vendedor de pé
      antes: `uv run uvicorn mesa.http.seller:app --port 8402`) → sua aprovação
      D-14 aparece no blotter com seu nome
- [ ] Exportar o CSV de uso do console da Anthropic (Settings → Usage) → me passar
      o arquivo → reconciliação do trilho fatura fica 100% real (hoje é rotulada
      sintética)

---

## O que me devolver (eu cuido do resto)

| Você me manda | Eu faço |
|---|---|
| link da issue A1 + PR A2 + issue A3 | marco GATE 5(b) ✅ no PLANO; linko a proposta no relatório |
| link do repo B1 + post B2 | marco GATE 9(b) "publicado", começo a vigiar a menção orgânica |
| CSV da Anthropic | reconciliação invoice 100% real no livro |
