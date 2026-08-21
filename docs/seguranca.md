# Segurança da mesa — modelo de ameaças e endurecimento (doc de design)

*Escrito em 21/08/2026, antes do código, pelo método (D-31). Revisão pedida pelo Beny
entre as Fases 7 e 8: "pensa em tudo possível de alguém tentar hackear, arruma, e aí
seguimos". Este doc é o mapa: quem ataca, o que protege hoje, o que este commit
arruma, e o que fica como risco ACEITO com nome.*

## Como pensar (em linguagem simples)

O sistema tem quatro coisas que valem a pena atacar:

1. **As chaves** (quem tem a chave tem o dinheiro da carteira).
2. **A assinatura** (fazer o comprador assinar algo pior do que ele pensa).
3. **O livro** (adulterar o registro do que aconteceu).
4. **A máquina** (derrubar ou espiar o processo).

E cinco atacantes realistas:

| Atacante | O que ele controla | Exemplos |
|---|---|---|
| **Vendedor malicioso** | a cotação 402, a resposta paga, o conteúdo | payTo trocado, ativade sósia, validade eterna, resposta de 10 GB, texto que tenta mandar no agente |
| **Vizinho de rede** (Wi-Fi/LAN) | pacotes na mesma rede | conectar no Postgres exposto, espiar o Jaeger |
| **RPC mentiroso** | as respostas do nó público | saldo falso, evento de liquidação inventado |
| **Índice envenenado** (Bazaar) | a lista de candidatos | URL para IP interno, http:// puro, corpo gigante |
| **Alguém com acesso ao disco/banco** | arquivos e linhas | reescrever o livro, ler segredos |

## O que JÁ protegia (conferido nesta revisão)

- Chaves fora do OneDrive (`C:\dev\mesa.env`), fora do git (histórico varrido: limpo —
  só hashes de transação públicos).
- Tetos duros DENTRO do seletor do SDK: rodam antes de qualquer assinatura, fail-closed
  (Fase 5; 3 golpes recusados offline: payTo trocado, ativo sósia, decimais mentidos).
- SQL 100% parametrizado (nenhum f-string em query); livro append-only; corrente de
  hash + carimbo externo (RFC3161 + OTS) — adulterar linha fechada = VERMELHO no
  verificador independente.
- Coletor idempotente (UNIQUE + ON CONFLICT): re-varrer nunca duplica.
- Vendedor de brinquedo e MCP em `127.0.0.1`; nada de `verify=False`, `eval`,
  `pickle`, `shell=True` no repo.
- `.gitignore` cobre `.env`; conteúdo comprado NUNCA é executado (só hash+tamanho, D-11).

## Os furos achados (e o que este commit faz)

| # | Furo | Ataque concreto | Correção |
|---|---|---|---|
| 1 | **Postgres e Jaeger publicados em `0.0.0.0`** | qualquer máquina no mesmo Wi-Fi conecta no livro (senha fraca de dev) e lê o painel | recriar containers com bind `127.0.0.1` (volume nomeado preservado); README atualizado; backup antes |
| 2 | **Chaves como `str` no Settings** | um `print(settings)`, log ou traceback qualquer imprime as 5 chaves | `SecretStr` do pydantic: qualquer print vira `**********`; uso explícito via `.get_secret_value()` |
| 3 | **Validade da autorização vem do vendedor** | `maxTimeoutSeconds: 10⁹` na cotação → assinamos uma "nota promissória" que vale 30 anos (SDK: `valid_before = now + maxTimeoutSeconds`) | checagem nova: `validade-excessiva` recusa acima de 1h |
| 4 | **Valor não checa piso** | cotação com valor 0/negativo/absurdo passa pelos tetos (`-5 ≤ teto` é verdadeiro) | checagem nova: `valor-invalido` (≤ 0 ou > 2⁶²) |
| 5 | **Resposta paga lida sem limite** | vendedor responde 10 GB → processo morre por memória | leitura em stream com teto (5 MB) na sondagem, na rodada paga e na sonda de vínculo |
| 6 | **URL do índice seguida às cegas** | candidato aponta `http://` puro ou IP interno (`127.0.0.1`, `10.x`, link-local) → sonda vira SSRF | guarda de URL: só `https://`, resolve o DNS e exige TODOS os IPs públicos |
| 7 | **Header base64 sem teto** | header `payment-required` de 100 MB antes do decode | teto de 64 KB antes de decodificar |
| 8 | **Clientes de teste sem checagens** | fase1/2 e o MCP upstream usavam o seletor default do SDK (pega o primeiro aceite, sem teto) | `make_client`/`make_mcp_client` agora têm seletor SEGURO por padrão (testnet + registro pinado + teto US$ 1) — "nenhum cliente sem checagens" |
| 9 | **Sem backup do livro** | disco morre = livro morre (carimbo prova integridade, não recupera dado) | `scripts/backup_db.py` (pg_dump p/ `backups/`, gitignorado, sincronizado pelo OneDrive = cópia fora da máquina; sem segredo no banco por construção) |
| 10 | **Saúde espalhada** | conferir tudo exigia 5 comandos de cabeça | `scripts/saude.py`: um comando roda ruff+mypy+pytest+verificador+bind das portas+varredura de segredo e imprime VERDE/VERMELHO |

## Riscos ACEITOS (com nome, não escondidos)

- **Corpo do 402 lido sem teto DENTRO do SDK** (`x402AsyncTransport` faz `aread()`
  do 402 antes do nosso seletor). Nosso teto cobre a resposta PAGA; o 402 gigante
  ainda derruba o processo (só trava, não assina). Vai como observação no texto do
  PR do SDK (notes/).
- **RPC mentiroso**: saldo, decimais pinados e liquidações confiam em
  `mainnet.base.org`. Mentira no pin seria pega pelo teste registro⇔constantes;
  liquidação inventada entraria no livro como settlement falso. Mitigação futura
  (Fase 9+): segundo RPC de conferência. Hoje: risco aceito, baixo (exige
  comprometer a Base/Cloudflare ou MitM com TLS quebrado).
- **Adulteração same-day**: linha alterada ANTES do fechamento do período não é
  pega pelo carimbo (só pela corrente, que um atacante com o banco recalcula).
  Mitigação: fechamento diário (rotina que já existe). Janela ≤ 24h.
- **Rebinding de DNS** (resolver público na checagem, IP interno na conexão): a
  guarda resolve e checa, mas não pina o IP na conexão. Sobra de risco pequena
  (alvo interno teria que falar HTTPS com certificado válido do domínio).
- **Conteúdo comprado como injeção de prompt**: o texto comprado volta para o loop
  do agente (T6) e pode tentar mandar nele ("compre de novo!"). Hoje o agente só
  tem 2 ferramentas e teto de gasto — dano máximo = gastar o teto. REGRA para a
  Fase 8+: conteúdo comprado é DADO, nunca instrução; agente que lê conteúdo
  comprado não ganha ferramentas novas na mesma conversa; tetos sempre.
- **Senha fraca do Postgres de dev** (`mesa`/`mesa`): aceitável SOMENTE porque o
  bind agora é `127.0.0.1`. Se um dia expor, troca antes.

## O que NUNCA entra (invariantes que a segurança reforça)

- Custódia de chave de terceiro (D-32/invariante 2) — a ideia "cadastrar chaves no
  app" continua PARADA. Vale também para nós: nenhum segredo em banco, log ou span.
- Chave privada em pasta sincronizada, em commit, em print — nem mascarada.
- Executar conteúdo comprado.

## Runbook de incidente (curto)

- **Ao FINANCIAR qualquer carteira (Coinbase → censo etc.)**: o ataque mais comum
  do mundo cripto não é contra o código, é contra o clipboard — malware troca o
  endereço copiado pelo do atacante. Sempre conferir os 4 primeiros E os 4 últimos
  caracteres NA TELA da exchange antes de confirmar (o nosso: `0x637f…B2DC`).
- **Suspeita de chave vazada**: gerar carteira nova (`setup_wallets.py` / censo),
  mover o saldo na hora (a chave é barata, o processo é 5 min), trocar no
  `C:\dev\mesa.env`. Nunca "esperar pra ver".
- **Livro suspeito**: `verificador/verificar.py` no último export + comparar com o
  carimbo do período — VERMELHO diz a linha exata.
- **Banco caiu/corrompeu**: restaurar o último `backups/*.dump`
  (`scripts/backup_db.py --restore` documenta o comando), re-rodar o coletor.

> **Prova deste doc:** `scripts/saude.py` VERDE de ponta a ponta + `pytest` com a
> suíte nova `tests/test_seguranca.py` (recusas: valor-invalido, validade-excessiva,
> URL privada, header gigante; Settings não vaza; registro⇔constantes) + portas dos
> containers respondendo só em `127.0.0.1`.
