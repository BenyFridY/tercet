"""Verificador OFFLINE do passaporte do pagador (mesa-passaporte/v0) — independente.

Este script NÃO importa o código do mesa: reimplementa as regras públicas
(payload canônico RFC 8785 → sha256 → assinatura EIP-191 recuperável), para que o
vendedor confie no que LÊ aqui, não em nós.

Nível 1 (padrão, SEM rede):
1. O assinante recuperado da assinatura é o próprio sujeito (payer_ref).
2. As contagens batem com a evidência (liquidadas, órfãos, nonce sem duplicata).
3. Imprime as métricas E as ressalvas — as ressalvas fazem parte do documento.

Nível 2 (--rpc URL): cada tx da evidência existe na chain com
AuthorizationUsed(payer, nonce) EXATOS. (--varredura: além disso, varre a faixa de
blocos coberta pela evidência atrás de liquidação do payer FORA da lista — esconder
compra liquidada é detectável.)

Dependências: rfc8785 + eth-account; web3 só para --rpc.
Uso: python verificar_passaporte.py passaporte.json [--rpc URL] [--varredura]
"""

import hashlib
import json
import sys
from pathlib import Path

import rfc8785
from eth_account import Account
from eth_account.messages import encode_defunct

FORMATO = "mesa-passaporte/v0"
AUTH_USED_SIG = "AuthorizationUsed(address,bytes32)"
CHUNK = 999  # RPC público limita ~1000 blocos por eth_getLogs


def falha(msg: str) -> None:
    print(f"VERMELHO: {msg}")
    sys.exit(1)


def h_payload(payload: object) -> str:
    return hashlib.sha256(bytes(rfc8785.dumps(payload))).hexdigest()


def main() -> None:
    art = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rpc = sys.argv[sys.argv.index("--rpc") + 1] if "--rpc" in sys.argv else None

    if art.get("formato") != FORMATO:
        falha(f"formato desconhecido: {art.get('formato')!r}")
    payload = art["payload"]
    sujeito = str(payload["sujeito"]["payer_ref"])
    m = payload["metricas"]
    evidencia = payload["evidencia"]

    # 1 — autenticidade: quem assinou é o sujeito (e adulterar 1 bit muda o hash)
    assinante = Account.recover_message(
        encode_defunct(hexstr=h_payload(payload)), signature=art["assinatura"])
    if assinante.lower() != sujeito.lower():
        falha(f"assinante {assinante} não é o sujeito {sujeito} — adulterado ou forjado")

    # 2 — consistência interna: as contagens são recomputáveis da própria evidência
    if m["liquidadas"] != len(evidencia):
        falha(f"métricas dizem {m['liquidadas']} liquidadas; evidência tem {len(evidencia)}")
    if m["autorizacoes"] < m["liquidadas"]:
        falha("mais liquidadas que autorizadas")
    if m["orfaos_chain_inexplicados"] != len(payload["liquidacoes_sem_par"]):
        falha("contagem de órfãos não bate com a lista")
    nonces = [e["nonce"] for e in evidencia]
    if len(nonces) != len(set(nonces)):
        falha("nonce duplicado na evidência — impossível on-chain, logo forjado")
    if any(not isinstance(e["amount_minor"], int) or e["amount_minor"] <= 0
           for e in evidencia):
        falha("valor inválido na evidência")

    print(f"sujeito   : {sujeito}  ({payload['sujeito']['rede']}, "
          f"{payload['sujeito']['rail']})")
    print(f"janela    : {payload['janela']['de']} → {payload['janela']['ate']}")
    print(f"métricas  : {m['autorizacoes']} autorizadas · {m['liquidadas']} liquidadas"
          f" · {m['nonces_reusados']} nonce reusado · {m['entregas_sem_pagar']} sem pagar"
          f" · {m['orfaos_chain_inexplicados']} órfã(s)")
    for r in payload["ressalvas"]:
        print(f"ressalva  : {r}")

    # 3 — nível 2 (opcional): a evidência contra a chain pública
    if rpc:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc))
        auth_topic = w3.keccak(text=AUTH_USED_SIG)
        blocos: list[int] = []
        for e in evidencia:
            rec = w3.eth.get_transaction_receipt(e["tx"])
            ok = any(
                lg["topics"][0] == auth_topic
                and ("0x" + lg["topics"][1].hex()[-40:]).lower() == sujeito.lower()
                and ("0x" + lg["topics"][2].hex()).lower() == str(e["nonce"]).lower()
                for lg in rec["logs"]
            )
            if not ok:
                falha(f"tx {e['tx']}: sem AuthorizationUsed({sujeito}, {e['nonce']})")
            blocos.append(int(rec["blockNumber"]))
        print(f"nível 2   : {len(evidencia)} liquidações confirmadas na chain via {rpc}")

        if "--varredura" in sys.argv and blocos:
            alegadas = {str(e["tx"]).lower() for e in evidencia}
            alegadas |= {str(t).lower() for t in payload["liquidacoes_sem_par"]}
            topico_payer = "0x" + "0" * 24 + sujeito[2:].lower()
            escondidas: list[str] = []
            frm, ate = min(blocos), max(blocos)
            print(f"varredura : blocos {frm}..{ate} (a faixa coberta pela evidência)")
            b = frm
            while b <= ate:
                logs = w3.eth.get_logs({
                    "fromBlock": b, "toBlock": min(b + CHUNK, ate),
                    "topics": [auth_topic, topico_payer],
                })
                for lg in logs:
                    txh = "0x" + bytes(lg["transactionHash"]).hex()
                    if txh.lower() not in alegadas:
                        escondidas.append(txh)
                b += CHUNK + 1
            if escondidas:
                falha(f"{len(escondidas)} liquidação(ões) do payer FORA do passaporte:"
                      f" {escondidas[:3]}…")
            print("varredura : nenhuma liquidação do payer fora da lista")

    print("VERDE: passaporte íntegro e do sujeito"
          + (" (conferido contra a chain)" if rpc else " (nível 1, offline)"))


if __name__ == "__main__":
    main()
