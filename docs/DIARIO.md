# Diário de bordo — mesa

> **Para que serve este arquivo:** cada tarefa concluída ganha uma entrada em linguagem direta —
> o que era, o que foi feito, o que ficou provado, onde está o código — e o topo sempre diz
> **o que vem agora**. A especificação formal das 12 fases está no PLANO
> (`Documents\x402\PLANO.md`); aqui é a narrativa, para acompanhar o ritmo sem reler tudo.
> Atualizado a cada tarefa. Última atualização: **23/08/2026**.

## O projeto em 30 segundos

Agentes de IA compram coisas (dados, APIs, serviços) pagando sozinhos via x402. **Ninguém registra
isso direito**: o que foi comprado, quem autorizou, quanto custou de verdade, se o dinheiro saiu
mesmo, se a entrega veio. A mesa é esse registro — o **livro** — com três pontas que precisam
bater: o que o agente pediu, o que ele autorizou pagar, e o que a blockchain diz que liquidou.
Toda diferença entre as três pontas vira um **veredito** nomeado (entregue-sem-cobrar,
pago-sem-entrega, replay…). Nunca tocamos em chave ou dinheiro — só observamos e provamos.

---

## ⏭️ AGORA: as 12 fases de CÓDIGO estão completas — o que resta é seu

**O programa fechou o código em 23/08. Nome BATIDO: tercet (24/08). REPO PÚBLICO
NO AR (24/08): https://github.com/BenyFridY/tercet** — criado a pedido do Beny,
após varredura de segredos na história inteira (limpa), com LICENSE MIT, capa e
badges. O que ainda falta, por decisão sua: (1) v0.1 no PyPI (o pacote renomeia
`mesa` → `tercet` nesse dia, por sed); (2) as publicações congeladas
(`notes/publicar/` + branch em `C:\dev\x402-fork`; re-certificar no dia:
`docs/passo-a-passo-publicacao.md`); (3) site → GitHub Pages quando quiser.
Enquanto isso: `uv run mesa-app` → http://127.0.0.1:8400 — o produto inteiro, no navegador —
e `claude mcp add mesa -- uv run mesa-mcp` — o livro respondendo DENTRO do seu agente (F13).

---

## Fase 14c ✅ LEGENDA CLICÁVEL + REPO PÚBLICO NO AR (pedido do Beny, 24/08)

**"Deixe um modo de quando você pressiona aparecer o que é"** — feito: botão
**? LEGENDA** no topo de toda tela + **pressionar qualquer pílula abre a gaveta
de legenda já no item certo** (estados, redes, byte-repetido, append-only,
carimbos, e a distinção estado ≠ veredito). E **"vamos criar o repo"** — criado:
**https://github.com/BenyFridY/tercet** (público, MIT, capa SVG própria, badges,
topics). Antes do push: varredura de segredos na HISTÓRIA inteira do git — as 3
ocorrências de padrão eram o nosso próprio scanner e uma chave FALSA de teste
(`sk-ant-teste-123` do teste que prova que SecretStr não vaza). CI do GitHub
Actions rodou de verdade pela primeira vez. Posts/PyPI continuam adiados por
decisão dele. 132 testes.

---

## Fase 14b ✅ BLOTTER NO PADRÃO DOS GRANDES (pedido do Beny, 24/08)

Pesquisa comparativa pedida por ele: como OpenRouter (Activity), Stripe (home de
payments) e os apps de spend desenham isso. Padrões extraídos: poucos números
calmos com comparação de período; fila de atenção com nome de gente ("disputes /
needs response"); tabela enxuta e paginada com drill-in; seletor de período em
tudo. O que mudou no blotter: (1) **seletor de período TUDO/30D/7D recomputado no
SERVIDOR** — cards, gráfico e tabela contam a MESMA janela, nunca número misto;
(2) o card de vereditos virou **"Precisa de atenção"** em linguagem de gente
("entregou-e-não-cobrou ou pagou-e-não-recebeu"), clicável → filtra a tabela;
(3) **trilhos zerados saem do card** (viram "sem movimento: mpp · ap2");
(4) **gráfico com DUAS curvas na mesma escala** — verde = dinheiro real, apagada =
tudo (testnet incluída, rotulada) — misturar era desonesto com o olho; (5)
**paginação: 25 linhas + "mostrar todas"** (a tabela despejava 91). A gaveta de
eventos já era paridade com o drill-in da Stripe. 131 testes.

---

## Fase 14 ✅ O MARTELO + O PRODUTO BONITINHO (24/08 — GATE 14 VERDE)

**O nome está BATIDO: tercet** ("nome tá ok" do Beny, 24/08). O que vestiu a marca
agora: o app (título, wordmark e o símbolo das três linhas no topo), o servidor MCP
(`tercet-livro`), o README e o rodapé do site ("name approved — the package renames
at first public release"). O pacote Python segue `mesa` até o dia do PyPI (decisão
da Fase 12, troca por sed). **Utilidades novas:** a aba 06 operações ganhou os dois
motores da F13 — gerar o export contábil e a visão CARF pela tela, lista fechada,
zero dinheiro — e a aba 05 livros virou o índice dos artefatos gerados (decripto +
contabil + carf). **GATE 14 provado:** os dois exports disparados por POST na
interface, rc=0, log ao vivo; livros listando; marca conferida por screenshot; MCP
demonstrado AO VIVO na conversa (gasto/vereditos/compras/passaportes/fiscal
respondendo do banco). **Dois achados honestos do gate:** (1) o Docker reiniciou e
derrubou o mesa-pg no meio da demo — o MCP disse "connection timeout" em vez de
inventar número (comportamento certo); (2) no Windows o print() dos motores nascia
cp1252 e um "ê" derrubava o job — o runner agora passa PYTHONIOENCODING=utf-8 a
todos os filhos. Suíte: **130 testes**.

---

## Fase 13 / itens 2+3 ✅ EXPORT CONTÁBIL + CARF ("pode seguir" do Beny — GATES 13b/13c VERDES)

Os dois renderizadores da análise internacional, no mesmo dia (doc:
`docs/fase13-export.md`). **Item 2 — contábil universal** (`mesa/contabil.py`):
o diário de partidas dobradas da competência — micro-pagamentos agregados com
honestidade (um lançamento/mês; $0,001 em 2 casas viraria $0,00) e o detalhe
compra-a-compra (6 casas + tx hash) como ponte de auditoria; sai em universal +
QuickBooks (leiaute do artigo oficial Intuit) + Xero (com ressalva de conferir o
template); débito==crédito provado; conferência independente no fuso de SP dentro
do Postgres; adulteração acusada nomeando o campo. `contabil/2026-08/`: 13 compras
→ USD 0,27. **Item 3 — CARF** (`mesa/carf.py`): o guia OFICIAL da OECD (XML Schema
jul/2025, 48 págs) baixado e lido; a visão "o que um RCASP reportaria de você" —
CryptoTransferOut CARF603, 13 transações, USD 0,27 + 0,272000 unidades, CARF1004;
o documento NASCE OECD11 (New Test Data — o tpAmb=2 do CARF) com Warning de
demonstração; validador próprio codado do guia (o XSD oficial não é público —
watchlist) limpo no verdadeiro e mordendo 3 sabotagens. **Achado registrado**: a
numeração BR↔OECD não é 1:1 — compra de bens/serviços é CARF603 na versão jul/2025
(604 é collateral); `alcance-internacional.md` corrigido. Suíte: **128 testes**.

---

## Fase 13 / item 1 ✅ O MCP DO PRODUTO (pedido do Beny, 23/08 — GATE 13a VERDE)

**"Arrume o MCP por favor então"** — feito no mesmo dia, pelo método (doc antes do
código: `docs/fase13-mcp.md`). A Fase 2 tinha MCP como trilho de COMPRA (agente
pagando tool calls); agora existe a direção oposta: **`uv run mesa-mcp`** — o livro
como 7 ferramentas de leitura para qualquer assistente (`claude mcp add mesa -- uv
run mesa-mcp`): status_do_livro, gasto, compras, compra, vereditos, passaportes,
fiscal. As regras de sempre, agora como D-37: sessão read-only estrutural (INSERT
recusado, teste prova), lista FECHADA (teste prova), honestidade na resposta
(testnet rotulada, "atualizado até o bloco N"). O gate rodou como um agente rodaria:
cliente MCP real por stdio em processo separado — lista confere, o `gasto` que
atravessou o transporte bateu com SQL independente (US$ 0,272 mainnet). 119 testes.
Itens 2 e 3 da Fase 13 (export contábil universal, carf-xml) aguardam "vai".

---

## Análise · alcance internacional (pedido do Beny, 23/08)

Beny: "não sei se meu objetivo é apenas BR — não vai ser CVM — escolher outro país?".
Análise completa em **`docs/alcance-internacional.md`**. Resumo: não escolher país,
escolher o PADRÃO — o DeCripto é a versão BR do CARF (OECD), em vigor desde 01/01/2026
em 46 jurisdições (~67 comprometidas; trocas em 2027; EUA em 2028). O produto já é 90%
sem-país; a proposta de Fase 13: export contábil universal (journal entries) →
`fiscal/carf-xml` → e o **MCP do produto** (o livro como ferramentas read-only para o
agente). CVM: correto, fora do jogo — e o invariante D-32 nos deixa fora do perímetro
de licença (não somos VASP/CASP/broker) em praticamente toda jurisdição.

---

## Fase 12E · TROCA DE MARCA a pedido do Beny (23/08): Razão → **tercet**

Beny pediu "mude nome e símbolo" — e no mesmo recado disse que o objetivo talvez não
seja só BR. Os dois pedidos se encontram: *Razão* tem ã, não viaja; o nome novo precisa
funcionar no ecossistema x402 (majoritariamente americano). **tercet** = estrofe de
TRÊS versos que pertencem um ao outro — aqui, cada compra é um: request, autorização,
liquidação. E a *terza rima* de Dante encadeia os tercetos (nenhum sai sem quebrar o
poema) — exatamente a nossa corrente de hash. Filtro duplo refeito em 23/08: `tercet`
LIVRE no PyPI (404); busca web não achou empresa tercet em software/AI/fintech.
Checados e descartados: cotejo/symbolon/countersign/pacioli/laudo (PyPI tomado).
Vivos como alternativa: partita, confere, terza, chirograph, bookmatch. **Símbolo
novo**: três linhas horizontais — a terceira fecha em check verde (a última linha
confere). Aplicado em site + logo.svg; código continua `mesa` até o martelo final.

---

## Fase 12D · NOME + LOGO propostos: ~~**Razão**~~ (substituído pela 12E a pedido do Beny)

Feedback do Beny no site: os números do censo no topo não prendem — viraram a faixa de
prova "we eat with our own fork" na seção de confiança; o topo agora é VALOR (see it /
catch it / prove it / close it). E ele pediu nome + logo. Proposta aplicada no preview:
**Razão** — *livro-razão* é literalmente o general ledger em PT, e *razão* = evidência
sobre promessa; o rodapé do site conta o duplo sentido. Vetados por colisão real:
Lastro (proptech BR, Series A $15M), Apura (cybersec BR), Lavra (lavra.dev, AI dev).
`razao` LIVRE no PyPI; sem colisão tech achada. Alternativas vivas se ele não gostar:
rubrica, escriba, batimento, apuro. **Logo**: as três pontas (request/autorização/
liquidação) convergindo no ponto verde único — a reconciliação como marca
(`site/assets/logo.svg`). O CÓDIGO continua `mesa` até o martelo; o rodapé do site diz
isso com todas as letras.

---

## Fase 12C ✅ SITE ≠ APP (correção do Beny, 23/08 — GATE 12c VERDE)

**"São 2 coisas distintas"** — e agora são: (1) o **APP operável de ponta a ponta**:
aba 06 operações dispara os motores como jobs com log na tela (demo testnet completa,
coletores, passaportes, DeCripto), lista FECHADA (nome inventado = 404), compra pela
tela é SEMPRE testnet (D-36); filtros no blotter. Prova do gate: a demo disparada por
POST na interface comprou 3×, o coletor casou e o blotter mostrou — e as 2 compras de
uma tentativa com bug viraram órfãos que o próprio livro acusou. (2) o **SITE do
produto** (`site/index.html`, EN, autocontido, pronto p/ GitHub Pages): hero com a
fita do livro digitando as linhas REAIS do censo, números medidos (15/15 · 13/15 ·
US$0,272 · 0/15), as 6 telas reais rotuladas, "estruturalmente incapaz" como seção de
confiança, fiscal BR em português, quickstart. Preview privado publicado para revisão.
111 testes; tudo verde.

---

## Fase 12 ✅ CÓDIGO FECHADO (GATE 12a VERDE + 12b pronto-local, 23/08)

**O produto inteiro existe e se USA: `uv run mesa-app`.** As cinco telas do design
(`design/produto/`) servidas ao vivo do banco — nenhuma tela tem lógica própria; cada
uma é uma lente sobre os motores que os gates das fases 1–11 já provaram (doc:
`docs/fase12.md`; código: `src/mesa/app/`; decisão de forma: D-35).

- **01 blotter**: gasto real vs teste (rotulado), por trilho, série diária, a tabela
  de compras com estado DERIVADO e a gaveta com a cadeia de eventos de cada compra.
- **02 tca**: desperdício real (US$ 0,33 — mesmo recurso, mesmo byte), dedup entre
  agentes, custo por entrega por fonte com faixa de preço e n dito.
- **03 risco**: orçamento por árvore (D-02, soma que bate por construção), aprovações
  D-14, e o **passaporte da Fase 10 re-verificado offline a cada request** (caos
  RECUSADO, censo ACEITO, mcp RECUSADO — com os motivos na tela).
- **04 laboratório**: o backtest da Fase 7 point-in-time (15 decisões reais do censo,
  mainnet apenas), IC de Wilson e os rótulos D-12 como parte do resultado.
- **05 livros**: reconciliação de três pontas (vereditos nomeados), período fechado
  com carimbos RFC3161+OTS, fatura consolidada por contraparte, trilho invoice, e o
  fiscal da Fase 11 recomputado ao vivo (R$ 1,42, abaixo do limiar — rotulado).
- **Read-only ESTRUTURAL (D-35)**: a sessão Postgres do app é
  `default_transaction_read_only=on` — INSERT/UPDATE/DELETE FALHAM, e o teste prova.
  O observador que não pode afetar, agora também na interface.
- **Achado de engenharia**: `localhost` no Windows tentava IPv6 (::1) e queimava o
  connect_timeout inteiro — 10,3s por tela. Com `127.0.0.1` explícito: 60–180ms.
- **OSS pronto-local (12b)**: CI GitHub Actions (ruff+mypy+pytest+build com Postgres
  de serviço zerado — o que também prova livro VAZIO nas telas), README com o
  exemplo-do-zero para terceiro (GATE 12), wheel com templates + entry point.
- 8 testes novos (110 no total), screenshots das 5 telas conferidos, saude.py VERDE.

---

## Fase 11 ✅ FECHADA (GATE 11 VERDE 23/08)

**O motor fiscal existe: o livro virou a DeCripto pronta.** A pesquisa do dia foi na
fonte primária — o manual OFICIAL do leiaute (v1.01, Ago/2026, ADE Copes nº 02/2025)
baixado de gov.br e lido página a página; a **primeira DeCripto da história vence
31/08/2026**, e nós construímos o motor na semana da estreia (doc: `docs/fase11.md`;
código: `src/mesa/decripto.py` + `ptax.py`; saída: `fiscal/decripto/2026-08/`).

- **O comprador x402 tem endereço certo no leiaute**: cap. 6 (PF sem prestador —
  autocustódia), **Registro 0450** (operação IV, TipoTransferenciaSaida 4 =
  "aquisição de bens ou serviços", CARF604). E o achado da fase: o **Registro 0980**
  aceita informar só **hash da transação + explorador** para negócio executado
  atomicamente por contrato inteligente — o pagamento x402 é o caso literal, e o
  livro tem cada hash com recibo. A frase do D-29 virou leiaute oficial.
- **Gerado do livro real, nada digitado**: 13 operações liquidadas na Base mainnet
  em ago/2026 → **R$ 1,42** pelo PTAX venda de 21/08 (R$ 5,1625), point-in-time em
  `fx_ptax` (migration 0004), com a regra da data de SP (22h SP = dia seguinte UTC)
  e retrocesso em dia sem cotação — testado com a BCB de verdade.
- **O leiaute é lei**: schema codificado do manual (campos, tipos, tamanhos,
  decimais, tabelas internas); validador puro REPROVA um campo fora do leiaute
  nomeando o campo; o gate adultera o arquivo e exige o VERMELHO; conferência
  independente refaz a competência com o fuso convertido pelo Postgres.
- **Honestidade em campo próprio**: veredito "ABAIXO DO LIMIAR de R$ 35 mil —
  demonstração rotulada"; USDC→USD 1:1 declarado; contraparte TipoNI 8 + domínio
  (o que o livro sabe); taxas vazias (gas é do facilitator); testnet excluída na query.
- **Bônus NFS-e**: DPS sintética (rotulada, tpAmb=2) gerada com os bindings oficiais
  da nfelib e validada contra o **XSD oficial** — a ponte recibo→NFS-e demonstrada.
- Pendências com gatilho: parecer art. 9º (antes de vender a PSAV) · resposta à
  consulta do BCB (não abriu; watchlist). 17 testes novos; suíte 102 verde; custo zero.

---

## Fase 10 ✅ FECHADA (GATE 10 VERDE 23/08)

**O passaporte do pagador existe — e é honesto a ponto de reprovar a carteira do
próprio dono.** O histórico do livro virou um documento portátil e assinado
(`mesa-passaporte/v0`) que o comprador apresenta e o vendedor valida OFFLINE, sem
confiar na gente, e muda os termos (doc: `docs/fase10.md`; código:
`src/mesa/passaporte.py`, vendedor e demo em `scripts/fase10/`, verificador
independente em `verificador/verificar_passaporte.py`).

- **As 4 alegações do D-08** saem do livro como função pura: taxa de liquidação
  (dois inteiros, nunca float), nonce nunca reusado, nenhuma entrega consumida sem
  pagar (validade morta sem liquidar; pendente vivo NÃO é calote), reconciliação
  fechada (liquidação sem par atribuída ao payer pelo `AuthorizationUsed` on-chain).
- **Assinado pela chave do PRÓPRIO payer** (RFC 8785 → sha256 → EIP-191): ninguém
  veste histórico alheio, e a prova de posse fresca (60s, por rota) derrota o ladrão
  de arquivo. As ressalvas D-12 (denominador auto-reportado, janela visível) viajam
  DENTRO do payload assinado — removê-las quebra a assinatura.
- **O ciclo do gate, com dado real:** caos RECUSADO (`nonce-reusado` do replay da
  Fase 1 + 5 órfãos), mcp RECUSADO (achado da fase: 1 compra de teste da T4 fora da
  instrumentação apareceu na chain — a carteira que parecia limpa no banco não é
  limpa contra a chain), **censo ACEITO** (mainnet: 13/15, zero reuso, zero órfão) e
  comprou o `/lote` de 0,10 na testnet — recusas ANTES de cobrar, compra no livro,
  coletor casou tudo por (authorizer, nonce).
- **Verificador independente** (não importa o mesa): nível 1 offline; nível 2 conferiu
  as 13 liquidações na Base mainnet e a varredura não achou liquidação escondida;
  métrica adulterada (esconder as 2 não-liquidadas) → VERMELHO.
- Custo real: **zero** (testnet; ~1,00 USDC de teste). 15 testes puros novos
  (`tests/test_passaporte.py`); suíte inteira verde.

---

## Fase 9(a) ✅ PACOTE PRONTO (21/08)

**O relatório público do censo existe e está pronto para postar** — em inglês
(o público é o ecossistema x402), gerado 100% das fontes (nenhum número digitado):

- `relatorio/x402-buyer-census-round1.md` — os 4 números com IC, a tabela por
  fonte com o recibo Basescan de CADA compra, 6 achados (o mais forte: as 2
  falhas nunca cobraram — a expiração do EIP-3009 protegeu o dinheiro; e 0/15
  provam o vínculo payTo, o gancho da nossa proposta de extensão), metodologia
  aberta e os limites ditos (n=15, auditoria-não-ranking).
- `relatorio/post.md` — a versão de 8 linhas para o X (falta só o link).
- `relatorio/dados/` — os 3 JSONs brutos para replicação.

**Passos seus (GATE 9b):** 1) postar a issue de conformance (notes/) PRIMEIRO;
2) subir o relatório como gist/repo público; 3) o post curto no X com o link;
4) esperar a menção orgânica (o gate dá 2 semanas). Regenerar depois de qualquer
mudança: `uv run python scripts/fase9/relatorio_build.py`.

**Próxima fase de código: Fase 10 (o passaporte do pagador single-buyer, D-08)** —
atestação assinada sobre o nosso próprio livro, conferível contra a chain.

---

## Fase 8 ✅ FECHADA (GATE 8 VERDE 21/08)

**As telas saíram do papel — com dado 100% real.** Uma página HTML autocontida
(`scripts/fase8/mesa-telas.html`, gerada do livro por `telas_build.py`; abrir no
navegador) com o visual do design de produto:

- **Blotter:** as 85 linhas do livro — por agente, por tarefa, com o recibo
  on-chain LINKADO (13 compras do censo → basescan), estado DERIVADO (nunca
  digitado), TESTNET sempre rotulado, filtros e a cadeia de eventos por compra.
- **TCA com desperdício de verdade:** US$ 0,23 em 24 compras repetidas byte a
  byte — o brinquedo do caos foi comprado 21× com UM conteúdo (regra: mesmo
  recurso + mesmo hash do corpo; conteúdo dinâmico legítimo não conta).
- **Orçamento por árvore (D-02):** a tarefa `censo.rodada1` com a soma dos filhos
  batendo com o total — a invariante da Fase 2, agora visível.
- **Aprovação vinculada (D-14):** acima do teto o humano decide, e o "sim" vale
  SÓ para a cotação exata (hash) — testado; entra no livro em `authz.principal_*`.
  Demo interativa: `scripts/fase8/aprovacao_demo.py` (testnet, 2 min).
- O gate é conferido por ASSERTS no builder, e o visual foi conferido em
  screenshot nas duas abas. Regenerar a tela = rodar o script de novo.

---

## Revisão de segurança ✅ FECHADA (21/08)

**Pedido do Beny entre fases: "pensa em tudo possível de alguém tentar hackear, arruma."**
Mapeei o sistema com olhos de atacante (5 atacantes: vendedor malicioso, vizinho de
Wi-Fi, RPC mentiroso, índice envenenado, acesso ao disco), escrevi o modelo de
ameaças (`docs/seguranca.md` — doc antes do código, como sempre) e arrumei **10 furos**:

1. **Postgres e Jaeger estavam abertos pro Wi-Fi** (`0.0.0.0`) → recriados em
   `127.0.0.1`, livro intacto (contagens conferidas antes/depois: 428|85|52|48).
2. **Chaves podiam vazar num print** → `SecretStr`: qualquer log mostra `**********`.
3. **Vendedor mandava na validade da nossa assinatura** (`maxTimeoutSeconds` → nota
   promissória de 30 anos) → checagem `validade-excessiva` (teto 1h).
4. **Valor sem piso** (negativo passava nos tetos) → checagem `valor-invalido`.
5. **Resposta paga sem limite de tamanho** (10 GB = processo morto) → leitura em
   stream com teto de 5 MB (smoke com compra testnet REAL sob stream: OK).
6. **URL do índice seguida às cegas** (SSRF: `http://`, IP interno) → guarda de URL.
7. **Header base64 sem teto** → 64 KB antes do decode.
8. **Clientes de teste sem checagens** → seletor SEGURO é o padrão em TODO cliente.
9. **Sem backup do livro** → `scripts/backup_db.py` (dump p/ `backups/`, OneDrive).
10. **Saúde espalhada** → `scripts/saude.py`: UM comando, VERDE/VERMELHO.

Riscos que FICAM, com nome (seguranca.md): 402 gigante dentro do SDK (virou
observação no texto do PR), RPC mentiroso (2º RPC fica p/ Fase 9+), adulteração
same-day (janela ≤24h até o fechamento diário), rebinding de DNS, injeção de prompt
via conteúdo comprado (regra escrita para a Fase 8+). 63 testes (9 novos), histórico
do git varrido (limpo), `saude.py` VERDE de ponta a ponta.

---

## Fase 7 ✅ FECHADA (GATE 7 VERDE 21/08)

**O Laboratório existe e é honesto.** Pegamos as 15 decisões reais do censo e
perguntamos "e se a política de gasto fosse outra?" — com a disciplina do seu mundo
quant: a política só enxerga o que o comprador enxergava na hora (point-in-time POR
TIPO: o objeto de decisão nem TEM o campo do desfecho), ordem real, IC no relatório.

- **Achado positivo:** a política `micro` (só compras ≤ US$ 0,01) pega 9 das 13
  entregas por US$ 0,012 — **16× mais barato por entrega** que o baseline.
- **Negativo 1 (o gate exige):** `verified-only`, a política que PARECE mais segura,
  compra ZERO hoje (ninguém publica vínculo) — segurança que custa 100% das entregas.
- **Negativo 2:** `premium` ("caro = confiável") entrega 50% vs 87% do baseline — a
  compra mais cara da rodada foi justamente uma das que falhou. n=2, IC [9%–91%]:
  leitura honesta é "sem evidência".
- Onde: `mesa/laboratorio.py` (motor puro), `scripts/fase7/laboratorio_run.py`
  (relatório com rótulos D-12), 5 testes novos.

---

## Fase 6 ✅ FECHADA (GATE 6 VERDE 21/08)

**O que ficou provado hoje, em palavras simples:**
1. **O que o agente compra agora aparece no painel** (Jaeger local, o mesmo tipo de
   painel onde se vê tokens/latência): compramos 1× na testnet e o span chegou lá com
   `purchase.amount=0.010000` e o comprovante (tx hash) do lado — conferido pela API,
   não a olho. Painel no navegador: http://localhost:16686 (serviço `mesa-fase6`).
2. **O livro engoliu um gasto que NÃO é cripto:** uma chamada LLM real (custou
   US$ 0,000858) entrou como trilho `invoice` e fechou contra o extrato com deriva
   zero — SEM nenhuma migration. O agnosticismo de trilho virou fato. A chave de join
   deste trilho é (dia, modelo); a do x402 é (authorizer, nonce) — cada trilho tem a sua.
3. `pix` reservado no vocabulário (D-29, esperando a consulta do BCB).

**Ação sua opcional (2 min, quando quiser):** exportar o CSV de uso do console da
Anthropic (console.anthropic.com → Usage) e me mandar o caminho — eu reconcilio o
livro contra o documento 100% real (hoje foi contra extrato sintético ROTULADO).

**Percalço do dia (registrado):** meu extrator de tx pegava o primeiro hex de 64
chars da resposta — que era o NONCE, não a transação. Corrigido: campos nomeados
primeiro. Lição: parecido não é igual; regex genérico em dado financeiro é bug.

---

## Fase 5 — engenharia ✅ COMPLETA (21/08); GATE 5(b) espera as SUAS submissões

**O que fechou hoje (GATE 5a ✅):** os 3 golpes contra agente — payTo trocado, token
sósia, decimais mentidos — são recusados por funções PURAS e OFFLINE
(`mesa/checagens.py`, registro pinado lido dos contratos 1×), com motivo nomeado e
teste reproduzível sem rede. Integradas no seletor do censo e no `make_client`.
O **vínculo reverso** N2 (`/.well-known/x402-payto` assinado pela chave do payTo) está
implementado (nosso vendedor publica; verificador offline) e a sonda no censo deu o
dado da proposta: **0/15 vendedores publicam vínculo** — evidência no livro.

**🔑 GATE 5(b) — as 5 submissões SUAS (textos todos prontos em `notes/`):**
1. Issue do relatório de conformance no coinbase/x402 (`x402-mcp-conformance-report.md`) — POSTAR PRIMEIRO;
2. PR do conserto do SDK Python (`sdk-python-fix-pr.md` — NC-1 confirmado vivo no main `dd927a2`; linka a issue 1);
3. Proposta da extensão payTo-binding (`x402-extension-payto-binding.md`);
4. Security Consideration no draft de DNS discovery (`x402-dns-discovery-security-consideration.md`);
5. Comentário no OTel #443 (`otel-443-comment-draft.md` — D-28, já estava na fila).

**Git:** commits `057a30b` (fases 1–4) e `e7a3311` (abertura da 5) na `main`.

**Fase 4 (fechada hoje):** o livro agora prova a si mesmo — corrente de hash com 385
elos íntegros, período fechado com carimbo duplo (freeTSA + OpenTimestamps 4/4), e um
verificador offline independente que pegou 1 bit adulterado na linha exata. De quebra:
**primeira implementação pública** da extensão oficial `offer-and-receipt`, e o schema
provou o agnosticismo — MPP real e AP2 ingeridos sem migration.

**Vigilância — atualização 21/08 (revisão de sanidade):**
- ✅ **Fase 3 ENCERRADA:** as 2 autorizações pendentes (stableenrich US$ 0,002,
  dripstack US$ 0,50) **EXPIRARAM sem liquidação** — validBefore no passado, não podem
  mais ser usadas on-chain. Registrado como `authz_event(kind='failed')` append-only
  (`scripts/fase3/expirar_pendentes.py`). O achado do censo virou definitivo: as 2
  fontes que falharam não cobraram e NÃO PODEM mais cobrar. Rodada 1 = FINAL.
- Fase 4 (segue): upgrade da prova OTS quando o Bitcoin ancorar (`kind='ots-upgrade'`),
  e fechamento diário do período (`fechar_periodo.py`).

**Também na fila (ações suas, 5 min cada):** postar o relatório de conformance no
coinbase/x402 e o comentário no OTel #443 — os dois textos prontos em `notes/`.

---

## Fase 4 — o recibo verificável ✅ GATE 4 VERDE (21/08)

### T1–T5 ✅ 21/08 — a fase inteira em um dia (tudo grátis)

- **O que era:** o livro deixar de ser confiável "porque nós dizemos" e passar a provar
  a si mesmo, com um terceiro verificando sem confiar na gente.
- **Como ficou:** regras de canonicalização escritas ANTES do código
  (`docs/canonicalizacao.md`, normativo — RFC 8785, tipos pinados, mutáveis excluídos);
  migrations 0002 (eventos: fecha a exceção do D-06) e 0003 (corrente + fechamento);
  elo de hash em TODA escrita nova na mesma transação; backfill determinístico das
  Fases 1–3 (375 linhas) com a ordem gravada no genesis; período `2026-08-21` fechado
  (seq 0..375 — contém o censo) com raiz de Merkle carimbada por **freeTSA** (RFC3161,
  cert embutido no token) e **OpenTimestamps** (4/4 calendários);
  `verificador/verificar.py` (não importa o mesa — o terceiro confia no que LÊ) validou
  o dump e o `gate4_teste.py` provou: 1 bit virado na seq 188 → VERMELHO acusando a
  seq 188.
- **T5, os 3 formatos (D-27):** emitimos a extensão OFICIAL `offer-and-receipt`
  (EIP-712, signer==payTo) sobre uma venda real NOSSA já liquidada — **primeira
  implementação pública da extensão** (aprovada com zero implementações). Ingerimos um
  desafio **MPP real** capturado ao vivo do censo (método tempo, chain 4217) como
  rail='mpp' e um mandate **AP2 sintético rotulado** (D-12) como rail='ap2' — os dois
  SEM migration: o agnosticismo de trilho deixou de ser promessa.
- **Correção de desenho (registrada):** o doc da fase previa emitir recibos sobre as 13
  compras do censo; o spec diz que quem assina é o VENDEDOR — corrigido para a venda em
  que somos o vendedor. O achado do censo ficou: **0/15 vendedores emitem a extensão.**
- **Percalços do dia:** o CLI `ots` quebra no Windows (bitcoin.rpc → ctypes/OpenSSL) —
  carimbamos pela LIB com o mesmo fluxo; o messageImprint do RFC3161 é o **hash** do
  dado carimbado (não o dado) — verificador corrigido; deriva de canônico entre fases
  ("GET url" vs url crua) detectada e tratada no matching.
- **Onde:** `src/mesa/integridade.py`, `carimbo.py`, `recibo_x402.py`;
  `scripts/fase4/` (backfill, fechar_periodo, ots_stamp, exportar_periodo, gate4_teste,
  formatos_run); `verificador/verificar.py`; 33 testes verdes.

---

## Fase 3 — o censo comprador ✅ GATE 3 VERDE (21/08)

### T4–T5 ✅ 21/08 — a rodada paga e o fechamento (as primeiras compras reais do livro)

- **O que era:** comprar 1× de cada fonte aprovada na sondagem, com dinheiro real na Base
  mainnet, e fechar os 4 números com recibo on-chain.
- **Aprovações:** desenho+orçamento OK; Beny financiou US$ 10 (Coinbase → Base,
  self-custody); "vai" explícito dado. Nada rodou antes disso.
- **Como protegeu o dinheiro:** os tetos moram NO SELETOR do SDK (a função que escolhe a
  cotação roda ANTES de assinar — cotação fora dos limites = compra abortada, fail-closed);
  `--vai` obrigatório no script (sem ele é ensaio); cada compra gravada no livro assim que
  o span dela fecha (processo morrer no meio perde no máximo a compra em voo).
- **O que aconteceu:** 15 compras assinadas, US$ 0,774 autorizado. **13 entregaram (200 +
  corpo). As 2 que falharam NÃO cobraram** — stableenrich devolveu 400 (nosso corpo de
  exemplo `{}` era inválido pra ela) e dripstack devolveu OUTRO 402 depois de pago
  (re-cobrança — achado!). Coletor mainnet (modo pagador): 13 `AuthorizationUsed` da nossa
  carteira, 13/13 casados com o livro na 1ª rodada. Entregou ⇔ cobrou em 15/15 casos.
- **Custo real on-chain: US$ 0,272** (não 0,774 — autorizado ≠ liquidado; a diferença é
  exatamente o que o livro existe pra distinguir). Saldo confere: 10 − 0,272 = 9,728 ✓.
- **Nuance registrada:** as 2 autorizações não-liquidadas continuam VIVAS até o
  validBefore — "pendente", nunca "não cobrou e acabou". Vigilância nos próximos dias.
- **Onde:** `scripts/fase3/rodada.py` (T4), `scripts/fase3/fechamento.py` (T5),
  `censo_fechamento.json` (os 4 números por fonte, com tx hash de cada liquidação).

### T1–T3 ✅ 21/08 — fundação, descoberta e sondagem (tudo grátis, nada gasto)

- **T1 (fundação):** carteira EXCLUSIVA do censo criada (`0x637f…B2DC`, chave fora do
  OneDrive); config de rede dupla (a testnet continua intacta — 22 testes verdes); coletor
  ganhou o **modo comprador** (`mesa.collector main_pagador`): na mainnet filtramos
  `AuthorizationUsed` pela NOSSA carteira como authorizer — não precisamos saber o payTo de
  cada vendedor. Smoke na mainnet VERDE (`scripts/fase3/coletor_smoke.py`): chain id 8453,
  USDC canônico conferido NO CONTRATO (decimals=6, symbol=USDC), e uma tx conhecida de
  terceiros reencontrada pelo filtro de authorizer. Bônus: ~1.128 `AuthorizationUsed` em
  8 minutos de Base — tráfego EIP-3009 real existe em volume.
- **T2 (descoberta):** `scripts/fase3/descoberta.py` → `candidatos.json` versionado.
  O Bazaar da Coinbase tem **3.000+ recursos e 604 domínios únicos** (maior que nossa
  estimativa; corte de paginação LOGADO, nunca silencioso). Seleção com filtros
  pré-comprometidos (USDC canônico por ENDEREÇO, Base mainnet, exact, ≤ US$ 1) e
  **estratificada por faixa de preço** — só "mais barato primeiro" enchia a lista de demos
  de US$ 0,001; as quotas por faixa trouxeram APIs de verdade (Arkham, screenshots, feeds).
  O índice publica uso real por recurso (`l30DaysTotalCalls`/`UniquePayers`) — capturado
  como contexto. O facilitator x402.org NÃO tem endpoint de discovery (404) — 1 índice só.
- **T3 (sondagem):** `scripts/fase3/sondagem.py` — 15 sondas sem pagar, tudo no livro
  (requests + quotes pendurados em spans reais, `mesa-censo`). **15/15 respondem, 15/15
  cotações válidas, custo estimado da rodada: US$ 0,774.**
- **As lições do dia (método):**
  1. A primeira sonda achou só 1/15 válidas — e o erro era NOSSO: no wire V2 sobre HTTP a
     cotação vem no **header `payment-required` (base64)**, não no corpo (que vem `{}`).
     Desconfiar da régua antes de reprovar o mundo. A sonda agora lê header-primeiro.
  2. Fontes POST-only respondem 405 ao GET — o método certo vem do próprio índice
     (`extensions.bazaar.info.input`). Sondar com o método anunciado.
  3. Repeti o erro da Fase 2 com a FK request→span (gravar o livro DENTRO do span aberto):
     o padrão é sondar capturando IDs e gravar DEPOIS da árvore fechar. Padrão anotado.
- **Achados de censo (já valem antes de pagar):** dripstack.xyz cota **US$ 0,50** com
  US$ 0,20 anunciado no índice (deriva de preço — número que o censo existe pra pegar);
  onesource e dripstack também falam **MPP** (`WWW-Authenticate: Payment`, method
  tempo/stripe) no MESMO endpoint — o trilho rival da watchlist (D-27) em produção,
  convergindo multi-trilho exatamente como o schema apostou.

---

## Fase 2 — a árvore e o agente real ✅ GATE 2 VERDE (21/08)

### T6 ✅ 21/08 — o agente decidiu comprar (e a fase fechou)
- **O que era:** a prova final do gate. Até aqui quem comprava era roteiro nosso; o produto
  promete medir AGENTE — um LLM que decide sozinho se e quando vale pagar.
- **O que foi feito:** `src/mesa/agente.py` (D-33 — do zero, dentro do repo): agente Claude
  (`claude-sonnet-5`, Tool Runner oficial da Anthropic) com DUAS ferramentas — notas locais
  gratuitas (que não sabem a resposta) e a fonte paga via MCP (0,01 USDC, preço declarado na
  descrição da ferramenta). A tarefa pede economia: "só use a paga se a grátis não resolver".
- **O que ficou provado:** o agente tentou a grátis primeiro, DECIDIU comprar exatamente 1
  vez, e a resposta final dele narra o raciocínio de custo ("foi necessário fazer 1 única
  chamada à fonte paga — custo: 0,01 USDC"). No livro: árvore íntegra de 6 spans, a compra
  no span exato da decisão (`ferramenta.fonte-paga`), a compra DELEGADA do servidor presente
  (aninhada não desapareceu), soma batendo em toda altura, e o coletor casou as 2 liquidações
  na chain na 1ª tentativa. **GATE 2 fechado com asserts** (`scripts/fase2/agente_run.py`).
- **Custo do run:** centavos de API + 0,02 USDC testnet.

### T5 ✅ 20/08 — a suíte de conformance (e a descoberta que corrigiu o mapa)
- **O que era:** escrever a suíte de testes de conformidade de pagamento-em-MCP que ninguém
  escreveu, rodando contra ≥2 implementações reais, com ≥1 não-conformidade documentada.
- **A descoberta antes do código:** reler as fontes revelou que o **SEP-2007 está DORMENTE**
  (PR fechado em 24/06/2026, sem sponsor — o "-32402" dos nossos docs vinha de texto morto).
  O texto vivo é o **spec de transporte MCP da própria x402 Foundation**. Suíte re-ancorada
  nele; docs corrigidos (D-34). Ler a fonte antes de acusar salvou o relatório inteiro.
- **O que a suíte achou:** **Python SDK 2.20.0 quebrado contra o MCP SDK 2.x** — NC-1: o
  wrapper de servidor importa módulo que não existe mais; NC-2: o cliente não reconhece o
  "pague primeiro" no formato novo e trata ferramenta paga como grátis (nunca paga). NC-3
  (nos DOIS SDKs): constante de erro `402` sem base em texto normativo nenhum. E, para
  equilíbrio: **o TypeScript 2.23.0 está conforme** — o Python é que ficou para trás.
- **Como funciona a suíte:** cada não-conformidade confirmada é um teste `xfail(strict)` —
  verde hoje, e QUEBRA no dia em que o SDK consertar (aviso automático). 8 conformidades
  passam + 4 não-conformidades documentadas. Roda offline, sem facilitator.
- **Prova executável:** `uv run pytest conformance` · relatório pronto para issue:
  `notes/x402-mcp-conformance-report.md` — **postar no coinbase/x402 é ação do Beny**.

### T4 ✅ 20/08 — a compra aninhada NÃO desapareceu
- **O que era:** a metade que faltava do GATE 2. Quando a ferramenta que o agente pagou compra
  de TERCEIROS para atender, esse gasto some de toda contabilidade que existe — o agente só vê
  "paguei a ferramenta". O produto promete que gasto delegado não desaparece.
- **O que foi feito:** o servidor MCP ganhou carteira própria (a 3ª, que você abasteceu no
  faucet) e agora COMPRA do vendedor HTTP para responder — dois servidores rodando juntos. O
  recibo da compra upstream volta assinado DENTRO da resposta (`_meta`), num formato v0 nosso
  (`src/mesa/recibo.py`: JSON canônico + assinatura EIP-191; o formato formal é a Fase 4). O
  comprador VERIFICA a assinatura antes de gravar — recibo forjado é recusado (testado) — e a
  compra entra como `origin='delegated'`, com quem comprou (`origin_ref`) e a assinatura
  (`origin_receipt_sig`).
- **O que ficou provado:** DUAS compras no livro penduradas no MESMO passo da árvore (direta +
  delegada); o coletor casou AS DUAS liquidações na chain por (authorizer, nonce) — pagadores
  DIFERENTES (você e o servidor), mesmo recebedor; reconciliação ok: 22→25, zero órfãos novos.
  4 testes novos do recibo (assinar/verificar/adulteração/forja).
- **Aprendizado de método:** o assert original comparava contagens GLOBAIS do livro — quebrou
  porque um probe de debug pagou sem registrar (virou órfão explicado) e o coletor correu mais
  rápido que a chain. Trocado por verificação das DUAS autorizações específicas do run, com
  retry — critério preciso não contamina entre experimentos.
- **Prova executável:** `scripts/fase2/aninhada_run.py` (custo declarado: 0,02 USDC/run).

### 🔧 Manutenção 20/08 — repo na raiz + fix do Docker
- **Repo movido para a raiz do projeto** (pedido do Beny): tudo agora em
  `Documents\x402\mesa\`. Única exceção deliberada: **segredos** em `C:\dev\mesa.env`, FORA da
  pasta sincronizada pelo OneDrive (chave privada em pasta de sync = chave na nuvem).
- **Docker (3 quedas):** causa raiz encontrada — `AutoStart` desligado (o app não subia no
  login; qualquer saída era permanente). Ligado + container com `--restart unless-stopped` +
  `db.connect` agora falha em 5s com runbook na mensagem em vez de pendurar 3 minutos calado.
- **Design enxugado (pedido do Beny):** `design/produto/` ficou só com as 5 telas do COMPRADOR
  (Blotter, TCA, Risco, Laboratório, Livros — as que as fases 7–8 usam), canvas regenerado.
  As 3 telas do vendedor + o checker público (estratégias mortas por D-21/D-23) e a exploração
  visual antiga foram para `arquivo/design/` — nada deletado, tudo recuperável.

### T3 ✅ 20/08 — a árvore de atribuição de verdade
- **O que era:** aposentar o span inventado na mão. A promessa do produto é "quanto custou a
  tarefa X, somando passos e subagentes" — isso exige que as compras pendurem na árvore REAL de
  execução, não num rótulo solto.
- **O que foi feito:** `src/mesa/otel.py` (um `SpanProcessor` que grava cada span encerrado no
  livro — IDs originais do OpenTelemetry, linha completa com começo/fim/desfecho, sem UPDATE) e
  `src/mesa/arvore.py` (a matemática de atribuição como função pura: gasto próprio + descendentes,
  com verificação de integridade — compra em span inexistente, raiz dupla, span órfão). 7 testes
  novos codificam "a soma bate em qualquer altura".
- **O que ficou provado:** uma tarefa real de 5 passos fez DUAS compras MCP pagas em passos
  diferentes; a árvore entrou íntegra no livro, cada compra no passo exato, soma batendo na folha,
  no meio e no topo (0,01 + 0,01 = 0,02). O coletor casou os pagamentos na chain (ok: 17→21).
- **Surpresa boa:** o SDK MCP 2.0 tem OpenTelemetry embutido — os spans internos dele entraram
  sozinhos na nossa árvore, aninhados certinho. Cada compra mostra as DUAS chamadas `tools/call`
  (a que levou "pague primeiro" + a repetida com a prova): a dança do x402 visível na árvore, de
  graça.
- **Incidente (sem perda):** o Docker Desktop caiu pela 3ª vez no projeto — o primeiro run travou
  na conexão com o banco antes de gastar 1 centavo. Runbook conhecido, recuperado em 2 min.
- **Prova executável:** `scripts/fase2/arvore_run.py` (custo declarado: 0,02 USDC de testnet
  por run).

### T2 ✅ 20/08 — a primeira compra por ferramenta MCP, ponta a ponta
- **O que era:** provar a trava D-01 — agente não faz HTTP na mão, chama *ferramentas* (MCP). O
  livro precisa registrar uma compra feita na fronteira de ferramenta igualzinho a uma compra HTTP.
- **O que foi feito:** um **vendedor MCP** (`src/mesa/mcp/seller.py`, porta 8403) com a ferramenta
  paga `consultar` (0,01 USDC), e um **comprador MCP** (`src/mesa/mcp/buyer.py`) que detecta o
  "pague primeiro", assina o pagamento e re-chama com a prova — capturando tudo para o livro pelos
  hooks. O SDK oficial x402 tem suporte MCP nativo, mas **quebrado contra o SDK MCP 2.0** — escrevi
  a ponte (adapter) e usei as primitivas verify/settle direto.
- **O que ficou provado:** tool call pago real na Base Sepolia (tx `0xd087c6…4eb5ef`); resultado
  entregue com o recibo dentro da resposta (`_meta`); livro gravou a tripla com `transport='mcp'`
  e `tool_name='consultar'`; o **coletor casou a liquidação on-chain por (authorizer, nonce)** e a
  reconciliação fechou (ok: 16→17, zero órfãos novos). O livro é agnóstico de transporte NA PRÁTICA.
- **Bônus:** 3 incompatibilidades reais do SDK x402 vs MCP 2.0 anotadas — já cumprem o "achar ≥1
  não-conformidade" do sub-gate da T5.
- **Prova executável:** `scripts/fase2/mcp_once.py`.

### T1 ✅ 20/08 — fundação da fase
- **O que era:** instalar as dependências novas (SDK MCP, OpenTelemetry) sem quebrar nada, e
  validar que elas convivem com o SDK x402.
- **O que ficou provado:** `mcp==2.0.0` + `openinference-instrumentation-mcp==2.0.6` +
  `opentelemetry-sdk==1.44.0` instalados; imports cruzados funcionam; ruff/mypy strict/pytest verdes.
- **Decisões da fase:** design em `docs/fase2.md` · **D-33**: tudo do zero, nenhum projeto anterior
  do Beny entra (o agente da T6 será `src/mesa/agente.py`, Claude Sonnet 5 via SDK da Anthropic).

## Fase 1 — o livro fecha com dado sujo ✅ GATE 1 VERDE (19/08)

*A fase que decidia se o projeto vivia: com erros INJETADOS de propósito, o livro tem que explicar
cada um — se não explica, nada acima presta. Explicou todos, no dia 1 (o critério de kill dava 30).*

### T5 ✅ — caos + reconciliação (o gate em si)
- **O que era:** injetar 6 tipos de erro deliberado (servidor morto pós-liquidação, entrega sem
  cobrança, handler quebrado, replay da mesma autorização, pagamento fantasma fora do livro…) e
  exigir que a reconciliação classifique TODOS, com o resultado previsto ANTES numa tabela-oráculo.
- **O que ficou provado:** 16 ok · 2 entregue-sem-cobrar · 2 pago-sem-entrega · 2
  autorizada-sem-liquidação · 1 replay (pego pela chave E pelo facilitator, defesas independentes)
  · 3 órfãos-chain todos explicados · **0 inexplicados**. Os vereditos bateram com o oráculo.
  11 testes unitários codificam o oráculo (`tests/test_reconcile.py`).
- **Prova executável:** `scripts/fase1/chaos_run.py`.

### T4 ✅ — o coletor idempotente
- **O que era:** varrer a blockchain (transferências USDC para o nosso endereço + o evento
  `AuthorizationUsed` no mesmo recibo de tx) e casar com o livro pela chave forte
  **(authorizer, nonce)** — a mesma dupla que está na autorização assinada E no evento on-chain.
- **O que ficou provado:** rodar duas vezes = exatamente as mesmas linhas (idempotência); 10/10
  pagamentos casados; e 2 pagamentos feitos ANTES de o livro existir apareceram como órfãos-chain
  com explicação — a reconciliação explica até o passado.

### T3 ✅ — o livro + a ingestão do comprador
- **O que era:** o schema (agnóstico de trilho E de transporte: tabela genérica de autorização +
  evidência por trilho em JSONB) e o comprador gravando requisição→cotação→autorização pelos hooks
  oficiais do SDK — sem gambiarras.
- **O que ficou provado:** 10 pagamentos → 10 triplas coerentes; migration aplica em banco zerado;
  URLs nunca em claro (só hash — query string carrega CPF/CNPJ).

### T2 ✅ — o primeiro pagamento real
- **O que ficou provado:** 200 + tx na Base Sepolia com `Transfer` E `AuthorizationUsed` no mesmo
  recibo — a confirmação de que a chave de join existe na prática. O facilitator paga o gas
  (ninguém aqui precisa de ETH).

### T1 ✅ — fundação
- **O que ficou provado:** repo com uv/ruff/mypy strict/pytest, Postgres 17 no Docker (porta 5433),
  2 carteiras geradas com chaves só no `.env`, saldo USDC lido do contrato on-chain.
