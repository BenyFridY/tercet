"""Fase 5: o vínculo reverso payTo⇔domínio — o pedaço que nenhuma spec cobre (D-22).

A escada N1–N4 (arquivo/06), com o nível SEMPRE na evidência:
- N1: TXT com DNSSEC validado (forte; adoção baixa) — especificado, não implementado;
- **N2 (o achado, implementado aqui): o domínio serve, sob TLS válido,
  `/.well-known/x402-payto` contendo o endereço E uma assinatura da chave daquele
  endereço atestando o domínio.** Bidirecional: o domínio (via TLS) endossa o
  endereço, e o endereço (via assinatura) endossa o domínio — DNS/BGP sozinho não
  vence, e não depende de DNSSEC;
- N3: TXT via DoH em resolvedores independentes concordando — especificado, não impl.;
- N4: `unverified` — estado de PRIMEIRA CLASSE, nunca erro.

A SONDA (buscar o well-known) é online; a VERIFICAÇÃO da assinatura é offline.
O texto de proposta de extensão está em notes/ (submissão = ação do Beny).
"""

import json
from typing import Any

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

VERSAO = 1
WELL_KNOWN_PATH = "/.well-known/x402-payto"


def mensagem_vinculo(dominio: str, endereco: str) -> str:
    """A mensagem assinada (determinística; minúsculas no endereço)."""
    return f"x402-payto-binding v{VERSAO}\ndomain: {dominio}\naddress: {endereco.lower()}"


def emitir_wellknown(pk: str, dominio: str, redes: list[str]) -> dict[str, Any]:
    """O documento que o VENDEDOR publica em /.well-known/x402-payto (nível 2)."""
    endereco = Account.from_key(pk).address
    assinada = Account.sign_message(
        encode_defunct(text=mensagem_vinculo(dominio, endereco)), pk)
    return {
        "version": VERSAO,
        "bindings": [{
            "address": endereco,
            "networks": redes,
            "domain": dominio,
            "signature": assinada.signature.to_0x_hex(),
        }],
    }


def verificar_wellknown(doc: dict[str, Any], dominio: str,
                        payto: str) -> dict[str, Any]:
    """Verificação OFFLINE do nível 2. Devolve o vínculo que mesa/checagens consome.

    Válido sse: existe binding para o payTo, o domain declarado é o sondado, e o
    assinante recuperado da mensagem é o PRÓPRIO endereço.
    """
    for b in doc.get("bindings", []):
        if not isinstance(b, dict):
            continue
        if str(b.get("address", "")).lower() != payto.lower():
            continue
        if str(b.get("domain", "")).lower() != dominio.lower():
            return {"nivel": 4, "valido": False, "payto": payto, "dominio": dominio,
                    "motivo": "dominio-declarado-diferente-do-sondado"}
        try:
            signer = Account.recover_message(
                encode_defunct(text=mensagem_vinculo(dominio, str(b["address"]))),
                signature=str(b.get("signature", "")))
        except (ValueError, KeyError):
            return {"nivel": 4, "valido": False, "payto": payto, "dominio": dominio,
                    "motivo": "assinatura-ilegivel"}
        if signer.lower() != payto.lower():
            return {"nivel": 4, "valido": False, "payto": payto, "dominio": dominio,
                    "motivo": "assinante-nao-e-o-endereco"}
        return {"nivel": 2, "valido": True, "payto": payto, "dominio": dominio,
                "networks": b.get("networks", [])}
    return {"nivel": 4, "valido": False, "payto": payto, "dominio": dominio,
            "motivo": "sem-binding-para-o-payto"}


def sondar(dominio: str, *, timeout: float = 10.0) -> tuple[int | None, Any]:
    """ONLINE (só coleta): busca o well-known. Devolve (status, doc-json-ou-None)."""
    from mesa import rede_segura  # tardio: sondar é o único pedaço online deste módulo

    url = f"https://{dominio}{WELL_KNOWN_PATH}"
    if not rede_segura.url_segura(url)[0]:  # seguranca.md furo 6
        return None, None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False,
                          headers={"User-Agent": "mesa-censo/0.1 (payto-binding probe)"},
                          ) as cli, cli.stream("GET", url) as r:
            corpo, truncado = rede_segura.ler_corpo_limitado(r)  # furo 5
    except httpx.HTTPError:
        return None, None
    if r.status_code != 200 or truncado:
        return r.status_code, None
    try:
        doc = json.loads(corpo)
        return r.status_code, doc if isinstance(doc, dict) else None
    except ValueError:
        return r.status_code, None
