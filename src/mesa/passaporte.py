"""Fase 10: o passaporte do pagador single-buyer (D-08).

Atestação assinada sobre o livro do PRÓPRIO comprador, para UM payer numa janela
declarada. Quatro alegações (D-08): taxa de liquidação sobre autorização, nonce nunca
reusado, nenhuma entrega consumida sem pagar, reconciliação fechada.

Desenho (docs/fase10.md):
- `montar_payload` é FUNÇÃO PURA sobre linhas do livro — como a reconciliação.
- Assina a CHAVE DO PRÓPRIO PAYER (RFC 8785 → sha256 → EIP-191): ninguém veste
  histórico alheio, e a prova de posse ao vivo usa a mesma chave.
- Honestidade estrutural (D-12) viaja em `ressalvas`, dentro do payload assinado.
- A EMISSÃO é online (atribui liquidações sem par via AuthorizationUsed na chain);
  offline é obrigação do VERIFICADOR (nível 1), nunca do emissor.
"""

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import rfc8785
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

FORMATO = "mesa-passaporte/v0"
PROVA_JANELA_S = 60  # prova de posse: janela de frescor (brinquedo, declarada no doc)

# As ressalvas D-12 fazem parte do PAYLOAD ASSINADO — quem apresenta o passaporte
# apresenta também os limites dele. Removê-las quebra a assinatura.
RESSALVAS_V0 = (
    "denominador auto-reportado: autorizacao assinada que nunca liquidou nao deixa rastro na chain",
    "janela escolhida pelo emissor: campo assinado; o vendedor decide se aceita janela parcial",
    "completude das liquidadas confere-se no nivel 2: varrer AuthorizationUsed(payer) na chain",
)

AUTH_USED_SIG = "AuthorizationUsed(address,bytes32)"


@dataclass(frozen=True)
class LinhaAuthz:
    """Uma autorização do payer, com o contexto da compra — a matéria-prima do passaporte."""

    authz_id: str
    nonce: str | None
    valid_until_utc: datetime | None
    ts_utc: datetime
    delivered: bool
    pay_to: str
    asset_contract: str
    tx: str | None  # external_ref da liquidação; None = não liquidou
    settled_amount_minor: int | None


# ---------------------------------------------------------------- o núcleo puro


def montar_payload(
    *,
    payer_ref: str,
    rede: str,
    linhas: list[LinhaAuthz],
    sem_par_do_payer: list[str],
    periodos: list[dict[str, str]],
    agora: datetime,
) -> dict[str, Any]:
    """Pura. As 4 alegações do D-08 computadas das linhas; nada de float, nada de rede."""
    if not linhas:
        raise ValueError("passaporte sem histórico não existe — nenhuma autorização do payer")
    liquidadas = [ln for ln in linhas if ln.tx is not None]
    contagem_nonce = Counter(ln.nonce for ln in linhas if ln.nonce is not None)
    nonces_reusados = sum(1 for c in contagem_nonce.values() if c > 1)
    # alegação 3: consumiu (delivered) + validade MORTA sem liquidar = o vendedor nunca
    # mais cobra. Autorização viva pendente NÃO é calote — é cobrança em curso.
    entregas_sem_pagar = sum(
        1 for ln in linhas
        if ln.tx is None and ln.delivered
        and ln.valid_until_utc is not None and ln.valid_until_utc < agora
    )
    cobrancas_pendentes = sum(
        1 for ln in linhas
        if ln.tx is None and (ln.valid_until_utc is None or ln.valid_until_utc >= agora)
    )
    evidencia = [
        {"tx": ln.tx, "nonce": ln.nonce, "amount_minor": ln.settled_amount_minor,
         "asset_contract": ln.asset_contract, "pay_to": ln.pay_to}
        for ln in liquidadas
    ]
    return {
        "sujeito": {"payer_ref": payer_ref, "rede": rede, "rail": "x402"},
        "janela": {
            "de": min(ln.ts_utc for ln in linhas).astimezone(UTC).isoformat(),
            "ate": max(ln.ts_utc for ln in linhas).astimezone(UTC).isoformat(),
        },
        "metricas": {
            "autorizacoes": len(linhas),
            "liquidadas": len(liquidadas),
            "nonces_reusados": nonces_reusados,
            "entregas_sem_pagar": entregas_sem_pagar,
            "cobrancas_pendentes": cobrancas_pendentes,
            "orfaos_chain_inexplicados": len(sem_par_do_payer),
        },
        "evidencia": evidencia,
        "liquidacoes_sem_par": list(sem_par_do_payer),
        "integridade": {"period_close": periodos},
        "ressalvas": list(RESSALVAS_V0),
        "emitido_utc": agora.astimezone(UTC).isoformat(),
    }


def passaporte_hash(payload: dict[str, Any]) -> str:
    """sha256 hex do payload canônico RFC 8785 — a identidade do passaporte."""
    return hashlib.sha256(bytes(rfc8785.dumps(payload))).hexdigest()


def _assinar_hash(pk: str, hash_hex: str) -> str:
    assinada = Account.sign_message(encode_defunct(hexstr=hash_hex), private_key=pk)
    return str(assinada.signature.to_0x_hex())


def _recuperar(hash_hex: str, assinatura: str) -> str:
    recuperado: str = Account.recover_message(
        encode_defunct(hexstr=hash_hex), signature=assinatura
    )
    return recuperado


def assinar(payload: dict[str, Any], pk: str) -> dict[str, Any]:
    """O artefato final. `pk` DEVE ser a chave do payer_ref — verificado aqui mesmo."""
    artefato = {"formato": FORMATO, "payload": payload,
                "assinatura": _assinar_hash(pk, passaporte_hash(payload))}
    if falhas := verificar_offline(artefato):
        raise ValueError(f"assinei um passaporte inválido — bug do emissor: {falhas}")
    return artefato


def verificar_offline(artefato: dict[str, Any]) -> list[str]:
    """Nível 1 (sem rede, sem RPC): lista de falhas; vazia = íntegro.

    Cobre autenticidade (assinante == sujeito) e consistência interna (as contagens
    são recomputáveis da própria evidência). NÃO é a política do vendedor — é o
    'este documento é o que diz ser'.
    """
    falhas: list[str] = []
    if artefato.get("formato") != FORMATO:
        return [f"formato-desconhecido: {artefato.get('formato')!r}"]
    payload = artefato["payload"]
    sujeito = str(payload["sujeito"]["payer_ref"])
    try:
        assinante = _recuperar(passaporte_hash(payload), str(artefato["assinatura"]))
    except Exception:
        return ["assinatura-ilegivel"]
    if assinante.lower() != sujeito.lower():
        falhas.append("assinatura-nao-e-do-sujeito")
    m = payload["metricas"]
    evidencia = payload["evidencia"]
    if m["liquidadas"] != len(evidencia):
        falhas.append("liquidadas-nao-bate-com-evidencia")
    if m["autorizacoes"] < m["liquidadas"]:
        falhas.append("mais-liquidadas-que-autorizadas")
    if m["orfaos_chain_inexplicados"] != len(payload["liquidacoes_sem_par"]):
        falhas.append("orfaos-nao-bate-com-lista")
    nonces = [e["nonce"] for e in evidencia]
    if len(nonces) != len(set(nonces)):
        falhas.append("nonce-duplicado-na-evidencia")  # impossível on-chain = forjado
    if any(not isinstance(e["amount_minor"], int) or e["amount_minor"] <= 0
           for e in evidencia):
        falhas.append("valor-invalido-na-evidencia")
    return falhas


# ------------------------------------------------------- prova de posse ao vivo


def prova_de_posse(pk: str, *, passaporte_hash_hex: str, rota: str, ts_unix: int
                   ) -> dict[str, Any]:
    """Arquivo vaza; chave não. Assina {hash do passaporte, rota, ts} — janela de 60s."""
    corpo: dict[str, Any] = {"passaporte": passaporte_hash_hex, "rota": rota, "ts": ts_unix}
    h = hashlib.sha256(bytes(rfc8785.dumps(corpo))).hexdigest()
    return {"corpo": corpo, "assinatura": _assinar_hash(pk, h)}


def verificar_prova(prova: dict[str, Any], artefato: dict[str, Any], *, rota: str,
                    agora_unix: int, janela_s: int = PROVA_JANELA_S) -> list[str]:
    """A prova vale para ESTE passaporte, ESTA rota, AGORA — e só o sujeito assina."""
    falhas: list[str] = []
    corpo = prova["corpo"]
    if corpo["passaporte"] != passaporte_hash(artefato["payload"]):
        falhas.append("prova-de-outro-passaporte")
    if corpo["rota"] != rota:
        falhas.append("prova-de-outra-rota")
    if abs(agora_unix - int(corpo["ts"])) > janela_s:
        falhas.append("prova-vencida")
    h = hashlib.sha256(bytes(rfc8785.dumps(corpo))).hexdigest()
    try:
        assinante = _recuperar(h, str(prova["assinatura"]))
    except Exception:
        return [*falhas, "assinatura-da-prova-ilegivel"]
    sujeito = str(artefato["payload"]["sujeito"]["payer_ref"])
    if assinante.lower() != sujeito.lower():
        falhas.append("prova-nao-e-do-sujeito")
    return falhas


# ------------------------------------------------------- a política do vendedor


@dataclass(frozen=True)
class Politica:
    """Decisão do VENDEDOR, não do formato — limiares nomeados (docs/fase10.md)."""

    taxa_minima_bp: int = 8_000     # liquidadas/autorizações ≥ 80% (inteiros, sem float)
    minimo_compras: int = 3
    validade_max_dias: int = 30


def avaliar_politica(artefato: dict[str, Any], politica: Politica, agora: datetime
                     ) -> tuple[bool, list[str]]:
    """(aceito, motivos). Pressupõe verificar_offline == []; motivos são nomeados."""
    payload = artefato["payload"]
    m = payload["metricas"]
    motivos: list[str] = []
    if m["autorizacoes"] < politica.minimo_compras:
        motivos.append("historico-curto")
    if m["liquidadas"] * 10_000 < m["autorizacoes"] * politica.taxa_minima_bp:
        motivos.append("taxa-de-liquidacao-abaixo-do-minimo")
    if m["nonces_reusados"] > 0:
        motivos.append("nonce-reusado")
    if m["entregas_sem_pagar"] > 0:
        motivos.append("entrega-consumida-sem-pagar")
    if m["orfaos_chain_inexplicados"] > 0:
        motivos.append("liquidacao-fora-do-livro")
    emitido = datetime.fromisoformat(str(payload["emitido_utc"]))
    if agora - emitido > timedelta(days=politica.validade_max_dias):
        motivos.append("passaporte-vencido")
    return (not motivos, motivos)


# --------------------------------------------------- a ponte com o livro (emissão)


def carregar_linhas(conn: psycopg.Connection[Any], *, payer_ref: str, rede: str
                    ) -> list[LinhaAuthz]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id::text,
                   lower((a.rail_evidence->'authorization')->>'nonce'),
                   a.valid_until_utc, r.ts_utc, r.delivered,
                   q.pay_to, q.asset_contract, s.external_ref, l.settled_amount_minor
            FROM authz a
            JOIN quote q ON q.id = a.quote_id
            JOIN request r ON r.id = q.request_id
            LEFT JOIN settlement_leg l ON l.authorization_id = a.id
            LEFT JOIN settlement s ON s.id = l.settlement_id
            WHERE a.rail = 'x402' AND lower(a.payer_ref) = lower(%s)
              AND q.asset_network_caip2 = %s
            ORDER BY r.ts_utc
            """,
            (payer_ref, rede),
        )
        return [LinhaAuthz(*row) for row in cur.fetchall()]


def sem_par_do_payer(conn: psycopg.Connection[Any], w3: Web3, *, payer_ref: str,
                     rede: str) -> list[str]:
    """Liquidações da rede sem `settlement_leg`, atribuídas ao payer via chain.

    O settlement sem par não carrega o pagador — a atribuição honesta é ler o
    `AuthorizationUsed` do receipt e comparar o authorizer (é o que faz o órfão ser
    DO payer, e não da rede inteira).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.external_ref FROM settlement s
            LEFT JOIN settlement_leg l ON l.settlement_id = s.id
            WHERE l.settlement_id IS NULL AND s.rail = 'x402' AND s.network_caip2 = %s
            ORDER BY s.block_ts_utc
            """,
            (rede,),
        )
        candidatos = [str(row[0]) for row in cur.fetchall()]
    auth_topic = w3.keccak(text=AUTH_USED_SIG)
    do_payer: list[str] = []
    for tx in candidatos:
        receipt = w3.eth.get_transaction_receipt(tx)  # type: ignore[arg-type]
        for lg in receipt["logs"]:
            if lg["topics"][0] == auth_topic and (
                "0x" + lg["topics"][1].hex()[-40:]
            ).lower() == payer_ref.lower():
                do_payer.append(tx)
                break
    return do_payer


def periodos_fechados(conn: psycopg.Connection[Any], *, de: datetime, ate: datetime
                      ) -> list[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT period_date, merkle_root FROM period_close"
            " WHERE period_date BETWEEN %s AND %s ORDER BY period_date",
            (de.date(), ate.date()),
        )
        return [{"data": str(row[0]), "merkle_root": "0x" + bytes(row[1]).hex()}
                for row in cur.fetchall()]


def emitir(conn: psycopg.Connection[Any], w3: Web3, *, payer_ref: str, rede: str,
           pk: str, agora: datetime | None = None) -> dict[str, Any]:
    """O caminho completo: livro → atribuição on-chain → payload → assinatura."""
    agora = agora or datetime.now(UTC)
    linhas = carregar_linhas(conn, payer_ref=payer_ref, rede=rede)
    if not linhas:
        raise ValueError(f"nenhuma autorização de {payer_ref} em {rede} no livro")
    payload = montar_payload(
        payer_ref=payer_ref, rede=rede, linhas=linhas,
        sem_par_do_payer=sem_par_do_payer(conn, w3, payer_ref=payer_ref, rede=rede),
        periodos=periodos_fechados(
            conn, de=min(ln.ts_utc for ln in linhas), ate=max(ln.ts_utc for ln in linhas)
        ),
        agora=agora,
    )
    return assinar(payload, pk)
