# Alcance internacional — análise (pedido do Beny, 23/08/2026)

*Pergunta dele, na íntegra do espírito: "meu objetivo não sei se é apenas BR — já que
não vai ser CVM, escolher outro país sei lá — queria ajuda para analisar e entender."*

Resposta curta: **não escolha outro país; escolha o padrão.** O produto já é 90%
sem-país; a parte fiscal foi construída de propósito como módulo; e o formato que o
Brasil nos obrigou a implementar (DeCripto) é a versão brasileira de um padrão da
OECD que ~67 jurisdições vão exigir. O caminho internacional não é reescrever — é
adicionar renderizadores.

---

## 1 · O que já é global hoje, sem mudar uma linha

- **Os trilhos são globais**: x402 (Coinbase, EUA), Base, USDC. Nenhum deles tem CEP.
- **O núcleo não tem jurisdição**: livro append-only, corrente de hash, reconciliação
  de três pontas, passaporte do pagador, carimbos RFC 3161/OTS — nada disso é "BR".
- **O site já é em inglês** (decisão da Fase 9: o público é o ecossistema x402) e o
  nome novo (**tercet**) viaja — foi um dos motivos da troca; *Razão* tinha ã.
- A ÚNICA parte com bandeira é a Fase 11 (DeCripto + PTAX + NFS-e) — e ela já nasceu
  como módulo plugado no livro, não entranhada nele.

## 2 · CVM: por que a intuição dele está certa — e o que importa no lugar

Não vendemos valor mobiliário, não intermediamos investimento, não fazemos oferta —
**CVM fora do jogo mesmo no Brasil**. Os reguladores que tocam ESTE espaço são outros:

| Regulador | Alcança quem | Nos alcança? |
|---|---|---|
| Fisco (RFB, IRS, HMRC…) | quem transaciona cripto | o **usuário** — e é aí que o produto AJUDA (é feature, não custo) |
| BCB / AML / FATF (VASP/CASP) | quem **custodia, troca ou transfere** por conta de terceiros | **não** — invariante D-32: nunca custódia, nunca chave, read-only estrutural (D-35) |
| MiCA (UE) | CASPs | **não**, pelo mesmo invariante |
| "Broker" (EUA, 1099-DA) | quem efetua/intermedia a venda | **não** — não estamos no caminho do pagamento |

O invariante que nasceu como princípio de segurança ("auditor que segura dinheiro não
é auditor") é também a **estratégia regulatória**: ficamos fora do perímetro de
licença em praticamente toda jurisdição. Isso já estava registrado no DECISOES
(adendo de 23/08: o alcance regulatório segue o CLIENTE, não o CEP do fundador; se um
dia o produto mover dinheiro, o caminho é parceria com custodiante licenciado).

## 3 · A resposta à pergunta "que país?" — o padrão CARF (OECD)

Fatos verificados em 23/08/2026:

- O **CARF** (Crypto-Asset Reporting Framework, OECD) entrou em vigor em
  **01/01/2026**: 46 jurisdições já coletando para o período 2026, com primeiras
  trocas internacionais em 2027 — **Brasil incluso**, junto com Alemanha, França,
  Reino Unido, Japão, Coreia, Canadá, Suíça…; mais 29 jurisdições para o período
  2027; **EUA na leva de 2028**. Total: ~67 comprometidas.
- Na UE, o veículo é a **DAC8**, também valendo desde 01/01/2026.
- O **DeCripto É o CARF brasileiro**: o código de operação da nossa linha 0450
  ("aquisição de bens e serviços", código 604) vem literalmente da tabela CARF. A
  Fase 11 não implementou "um recurso BR" — implementou **o primeiro renderizador**
  de um padrão de ~67 países, no país com o prazo mais cedo e o manual mais concreto.

A arquitetura que a Fase 11 deixou é exatamente a certa para o mundo:
**registro canônico no livro → renderizador por jurisdição.** Módulos possíveis:

| Módulo | Cobre | Esforço | Status |
|---|---|---|---|
| `fiscal/br-decripto` | Brasil (IN 2.291, prazo real 31/08/2026) | — | ✅ feito (Fase 11) |
| export contábil universal (journal entries CSV/QBO p/ QuickBooks, Xero, NetSuite) | **todo** comprador do mundo | baixo | proposta |
| `fiscal/carf-xml` (o schema XML da OECD) | as ~67 jurisdições de uma vez | médio | proposta (quando o schema final estabilizar) |
| `fiscal/us` (apoio a ganho/perda em disposição de USDC) | EUA | médio | proposta |

## 4 · Onde estão os compradores (o mercado, não a regulação)

- x402 é da Coinbase; Base é dos EUA; os agentes que compram hoje são o ecossistema
  dev **americano/global** — o nosso próprio censo mostrou: 15 vendedores vivos,
  nenhum com qualquer exigência BR.
- Nos EUA não existe "arquivo mensal para o governo" do comprador. O que a empresa
  americana precisa: **livros que fecham** (o subledger que liga ao ERP), suporte a
  auditoria, e rastro para ganho/perda quando gasta USDC (gasto em cripto é
  disposição de propriedade para o IRS — nosso livro já guarda tudo que esse cálculo
  pede: data, valor, tx hash). Ou seja: para o maior mercado, o artefato de valor é o
  **export contábil**, não o arquivo de governo.
- O Brasil vira **vitrine, não limite**: é o fisco mais exigente do mundo em cripto
  (reporte MENSAL, limiar R$ 35k, IN 2.291). O nosso arquivo de 31/08/2026 — gerado
  do livro real, validado contra o manual oficial — é o argumento: *"se o livro passa
  na Receita todo mês, a sua jurisdição é fácil."*

## 5 · Recomendação (vira Fase 13 se o Beny quiser)

1. **Mercado global-first já** — nada a mudar: site em inglês, nome que viaja, USD.
2. **Fiscal como plugins**: manter `br-decripto`; próximo passo de MAIOR valor por
   esforço é o **export contábil universal** (serve qualquer comprador, zero
   jurisdição); `carf-xml` na sequência cobre ~67 países de uma tacada.
3. **Não perseguir licença nenhuma** — o invariante é o diferencial (a seção
   "structurally incapable" do site é isso virando marketing honesto).
4. **BR continua**: entregar o arquivo de 31/08 (real, nosso) e transformá-lo em
   estudo de caso público quando as publicações saírem.

*Fontes: OECD/Government of Jersey (contagem 46/29/1, jun/2026); Comissão Europeia
(DAC8); KPMG (joint statement das jurisdições); IN RFB 2.291/2025 + Manual DeCripto
v1.01 (primários, baixados na Fase 11).*
