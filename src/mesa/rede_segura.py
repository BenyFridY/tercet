"""Rede segura — o que vem de fora entra com teto e com endereço conferido.

docs/seguranca.md, furos 5–7. Três defesas, todas fail-closed:

- **Guarda de URL** (furo 6): candidato do índice só é sondado/comprado se for
  `https://` e se TODOS os IPs resolvidos do host forem públicos — um item
  envenenado no Bazaar não faz a nossa sonda bater em `127.0.0.1`, `10.x`,
  link-local (169.254 — metadados de nuvem) nem em serviço interno.
- **Leitura com teto** (furo 5): resposta de vendedor é lida em stream até
  `REDE_CORPO_MAX_BYTES`; acima disso paramos de ler (o processo não morre por
  memória; o livro registra o prefixo retido — hash e tamanho do que GUARDAMOS).
- **Header com teto** (furo 7): header base64 acima de `REDE_HEADER_MAX_BYTES`
  nem é decodificado.

Residual dito com franqueza: a guarda resolve DNS na checagem e não pina o IP na
conexão (rebinding fica como risco aceito, ver seguranca.md).
"""

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from mesa.config import REDE_CORPO_MAX_BYTES, REDE_HEADER_MAX_BYTES


def url_segura(url: str) -> tuple[bool, str]:
    """(ok, motivo). Só https, host presente, e todos os IPs resolvidos públicos."""
    try:
        p = urlparse(url)
    except ValueError:
        return False, "url-ilegivel"
    if p.scheme != "https":
        return False, "esquema-nao-https"
    host = p.hostname
    if not host:
        return False, "sem-host"
    if host.lower() in {"localhost", "localhost.localdomain"}:
        return False, "host-local"
    # IP literal: checa direto; nome: resolve e exige TODOS os IPs públicos
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, p.port or 443, proto=socket.IPPROTO_TCP)
        except OSError:
            return False, "dns-nao-resolve"
        ips = [ipaddress.ip_address(info[4][0]) for info in infos]
    for ip in ips:
        if not ip.is_global:  # cobre private, loopback, link-local, reserved, unspecified
            return False, f"ip-nao-publico ({ip})"
    return True, "ok"


def decodificavel(header: str | None) -> bool:
    """Header base64 só é decodificado abaixo do teto (furo 7)."""
    return header is not None and 0 < len(header) <= REDE_HEADER_MAX_BYTES


def ler_corpo_limitado(r: httpx.Response, max_bytes: int = REDE_CORPO_MAX_BYTES,
                       ) -> tuple[bytes, bool]:
    """Lê um Response SÍNCRONO aberto em stream. Devolve (corpo, truncado)."""
    pedacos: list[bytes] = []
    lidos = 0
    for pedaco in r.iter_bytes():
        pedacos.append(pedaco)
        lidos += len(pedaco)
        if lidos > max_bytes:
            return b"".join(pedacos)[:max_bytes], True
    return b"".join(pedacos), False


async def ler_corpo_limitado_async(r: Any, max_bytes: int = REDE_CORPO_MAX_BYTES,
                                   ) -> tuple[bytes, bool]:
    """Lê um Response ASSÍNCRONO aberto em stream. Devolve (corpo, truncado)."""
    pedacos: list[bytes] = []
    lidos = 0
    async for pedaco in r.aiter_bytes():
        pedacos.append(pedaco)
        lidos += len(pedaco)
        if lidos > max_bytes:
            return b"".join(pedacos)[:max_bytes], True
    return b"".join(pedacos), False
