# Fase 11 — o fiscal: recibo → obrigação (doc de design)

> ✅ **GATE 11 VERDE em 23/08/2026** — a DeCripto da competência ago/2026 gerada
> 100% do livro (`scripts/fase11/decripto_build.py`, tudo por assert): **13
> operações reais da Base mainnet → R$ 1,42** pelo PTAX de 21/08 (R$ 5,1625,
> point-in-time em `fx_ptax`); arquivo 0450 validado contra o leiaute codificado do
> manual v1.01 + demonstração 0980 (hash + explorador); validador MORDE (código
> adulterado e campo extra → VERMELHO); conferência independente com o fuso
> convertido pelo Postgres; veredito honesto "ABAIXO DO LIMIAR — demonstração".
> Bônus: DPS da NFS-e sintética validada contra o XSD oficial da nfelib
> (`nfse_dps_demo.py`). 17 testes puros novos; custo zero. O parecer do art. 9º
> segue como gatilho externo (antes de qualquer venda a PSAV) e a consulta do BCB
> ainda não abriu (watchlist).

*Escrito em 23/08/2026, antes de qualquer código, pelo método do programa (D-31).
Fontes primárias, todas conferidas HOJE: IN RFB nº 2.291/2025 (14/11/2025) · Manual de
Orientação do Leiaute da DeCripto **v1.01 (Ago/2026)**, ADE Copes nº 02/2025 — PDF
oficial baixado de gov.br e lido página a página · agenda tributária de ago/2026
(1ª entrega da DeCripto: **31/08/2026**, competência jul/2026). Esta fase não gasta
um centavo e não publica nada.*

## O que é esta fase, em linguagem direta

O livro sabe tudo o que a Receita vai perguntar sobre compra com criptoativo: data,
valor, quantidade, contraparte, hash da transação. A Fase 11 constrói o **motor que
transforma o livro na obrigação pronta**: pega as compras liquidadas do mês, converte
para reais pelo PTAX **da data certa** (regra de São Paulo), classifica cada operação
no registro certo do leiaute oficial, e escreve o arquivo da **DeCripto** exatamente
como o validador da Receita espera — com um validador nosso que reprova o arquivo se
um único campo sair do leiaute.

É a opção de receita do projeto (a rampa "onde ninguém de fora do Brasil vai") ficando
**pronta para o gatilho** — sem esperar o gatilho.

**O que preciso de você: nada agora.** (O parecer jurídico do art. 9º e a resposta à
consulta do BCB são gatilhos externos — ver o fim do doc.)

## O que a pesquisa de hoje cravou (fonte primária, não notícia)

1. **A DeCripto é real e está em vigor**: IN RFB 2.291/2025, vigência 01/07/2026,
   substitui a IN 1.888/2019. **Primeira entrega: 31/08/2026** (competência jul/2026)
   — nós estamos construindo o motor NO MÊS da primeira entrega da história.
2. **O leiaute é texto pipe-delimitado** (UTF-8, campos separados por `|`, CRLF no fim
   da linha, datas `ddmmaaaa`, decimais com vírgula), hierárquico por registro — não é
   XML nem JSON. Manual v1.01 traz exemplo oficial preenchido de cada registro.
3. **Existem TRÊS leiautes** no manual: cap. 4 (PSAV/exchange — NUNCA seremos, D-32),
   cap. 5 (PF/PJ via exchange estrangeira) e **cap. 6 (PF/PJ SEM prestador — 
   autocustódia)**. O comprador x402 é exatamente o cap. 6.
4. **A operação do comprador x402 tem registro próprio**: pagar serviço com USDC da
   própria carteira = **Registro 0450** (transferência de saída), código de operação
   **IV**, `TipoTransferenciaSaida = 4` ("aquisição de bens ou serviços", CARF604).
   O registro 0550 só existe para aquisições **acima de US$ 50.000** — micro-compra
   de agente não entra lá.
5. **O achado de produto — Registro 0980 ("Componibilidade Contratual Atômica")**:
   o parágrafo único do art. 9º da IN permite, para negócio executado
   indivisivelmente por contrato inteligente, informar **apenas o hash da transação +
   URL do explorador**. O pagamento x402 (EIP-3009 submetido pelo facilitator) é
   literalmente isso — e o livro guarda cada hash com recibo. A frase do D-29 ("o
   livro gera a DeCripto quase de graça") virou leiaute oficial.
6. **O limiar de obrigação PF é R$ 35 mil/mês** movimentado fora de exchange nacional.
   Nosso agosto real (US$ ~0,37 na mainnet) está ~5 ordens de grandeza abaixo:
   a DeCripto desta fase é **o motor rodando de verdade, rotulado como simulação de
   competência** — não uma entrega devida. O motor calcula e IMPRIME essa conclusão.

## As decisões de classificação (revisáveis com contador — a regra vem dele)

| Questão | Decisão v0 | Por quê / ressalva |
|---|---|---|
| Valor em reais de USDC | quantidade × **PTAX venda de fechamento** da data de SP (USDC→USD 1:1 como aproximação DECLARADA) | PTAX é point-in-time, oficial e auditável; o exemplo oficial do próprio manual valora USDC por câmbio USD. Peg risk anotado; `AvaliacaoAlternativaValor = 4` ("estimativa razoável") |
| Data da operação | `block_ts_utc` → data em **America/Sao_Paulo** | a regra do PLANO (pagamento 22h SP = 01h UTC do dia seguinte; data UTC erraria toda compra noturna) |
| Dia sem PTAX (fim de semana/feriado) | última cotação **anterior** disponível | point-in-time: só dado que existia na data. Rotulado no arquivo de resumo |
| Contraparte x402 (payTo + domínio, sem NIF) | `TipoNI = 8` (Plataforma Descentralizada) + `Plataforma` = domínio do vendedor; país BR (regra literal do manual p/ TipoNI 8) | é o que o livro SABE. Quando a verification table tiver identidade real (escada N1–N4), o campo migra sozinho |
| Taxas em reais | vazio (campo facultativo) | no `exact`, o **facilitator paga o gas** (D-15/D-18) — o pagador não incorre taxa. Dizer 0 seria inventar |
| Testnet | **EXCLUÍDA por construção** (filtro `network_caip2 = eip155:8453`) | USDC de faucet não é criptoativo com valor; misturar seria o erro clássico |
| 0450 vs 0980 | arquivo principal com 0450 por operação + arquivo de demonstração 0980 por hash | 0980 é a alternativa legal para o conjunto atômico; emitimos os dois para documentar o caminho |

## Os componentes

1. **`migrations/0004_fiscal.sql`** — tabela `fx_ptax` (data, compra, venda, fonte,
   fetched_utc), append-only por convenção. **Fora da corrente de hash**, de
   propósito: é dado de REFERÊNCIA externo e refetchável do BCB, não é o livro.
2. **`src/mesa/ptax.py`** — `python-bcb` (D-30): busca a cotação de fechamento, aplica
   a regra da data de SP, cai para o dia útil anterior quando não há cotação, e
   persiste em `fx_ptax` para regeneração determinística.
3. **`src/mesa/decripto.py`** — o leiaute do cap. 6 **codificado do manual** (schema
   por registro: campos, tipos N/C, tamanho máx, decimais, valores válidos, tabelas
   internas OperacaoCodigo/TipoNI/TipoTransferenciaSaida/TipoAvaliacaoAlternativa);
   `montar` (puro, sobre linhas do livro); `render` (pipe/CRLF/UTF-8); `validar`
   (puro — reprova arquivo com 1 campo fora do leiaute); limiar R$ 35 mil como
   função com saída honesta ("obrigada" vs "abaixo do limiar").
4. **`scripts/fase11/decripto_build.py`** — gera `fiscal/decripto/2026-08/` com o
   arquivo 0450, o arquivo-demonstração 0980, e um resumo em PT com os números
   CONFERIDOS do livro por assert (estilo relatorio_build da Fase 9).
5. **NFS-e (mínimo honesto)** — a ponte recibo→DPS via `nfelib` para a NOSSA venda,
   rotulada **sintética** (a única venda real do livro é testnet): gera a DPS e
   valida contra o XSD oficial embarcado na lib. Emissão real só existe com CNPJ +
   Emissor Nacional (gatilho: Simples obrigatório em 01/11/2026).

## As etapas

| # | Etapa | O quê | Pronto quando |
|---|---|---|---|
| T0 ✅ 23/08 | Pesquisa | manual v1.01 oficial lido página a página; cronograma confirmado (1ª entrega 31/08) | este doc cita registro e campo exatos |
| T1 | Este doc | design antes do código | você está lendo |
| T2 | PTAX | migration 0004 + `ptax.py` + testes da regra de data | cotação de 21/08 (sexta) buscada e persistida; sábado cai p/ sexta em teste puro |
| T3 | O leiaute | `decripto.py`: schema + montar + render + validar | teste puro: arquivo bom VERDE; 1 campo adulterado (tamanho, tabela, decimal, pipe) → VERMELHO nomeando o campo |
| T4 | GATE 11 | `decripto_build.py` gera a competência ago/2026 do livro REAL + NFS-e sintética | **GATE ✅**: arquivo validado contra o leiaute; cada 0450 bate com uma liquidação mainnet do livro (assert); resumo diz "abaixo do limiar" com o número |

> **GATE 11:** uma DeCripto simulada do mês, 100% gerada do livro, validada contra o
> leiaute — e o parecer do art. 9º inc. II encomendado antes de qualquer venda a PSAV.
> *(A segunda metade é gatilho externo — ver abaixo.)*

## Custos declarados

- **Dinheiro: zero.** PTAX e leiaute são públicos; nenhuma compra nova.
- **LLM: zero** — código determinístico.
- Novas deps: `python-bcb` (PTAX) e `nfelib` (DPS) — ambas MIT/ativas (D-30).

## O que NÃO entra (e onde fica registrado)

- **Resposta à consulta pública do BCB** (D-29): a consulta **ainda não abriu**
  (esperada set–out/2026). Fica na watchlist semanal; quando abrir, é texto para o
  Beny revisar — e pela decisão de 23/08, publicação junta com o resto no fim.
- **Parecer jurídico do art. 9º inc. II**: gatilho = primeira venda a PSAV. Ação do
  Beny, custo real, só quando houver cliente com nome. Registrado, não executado.
- **Transmissão real ao e-CAC**: exige certificado digital e obrigação real
  (R$ 35 mil+). O motor para na fronteira: arquivo pronto e validado.
- **IOF/ganho de capital**: USDC comprado e gasto ≈ sem ganho; a apuração de ganho
  entra quando houver ativo volátil no livro (não inventar módulo sem caso).

## Riscos, ditos com franqueza

- **Leiaute novo no mundo real**: a 1ª entrega da história é NESTE mês; o validador
  oficial (Coleta Nacional) pode divergir do manual em detalhe. Mitigação: nosso
  validador aplica o manual v1.01 à letra e o arquivo é regenerável em segundos.
- **USDC→USD 1:1** é aproximação; num depeg o valor em reais estaria errado.
  Declarado no resumo gerado. Solução futura: cotação de USDC de fonte nomeada
  (`AvaliacaoAlternativaValor = 2`).
- **Identidade de contraparte** é o elo fraco (TipoNI 8 genérico) — exatamente o furo
  que a nossa proposta payTo-binding ataca do outro lado. Os dois lados do projeto
  se encontram aqui.
