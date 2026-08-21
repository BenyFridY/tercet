"""Fase 5: as checagens pré-assinatura — puras, OFFLINE, veredito com evidência.

Os três golpes contra o comprador-agente acontecem ANTES de assinar:
payTo trocado · ativo sósia · decimais mentidos. A defesa roda SEM REDE: a verdade
vem do registro pinado (`registro_ativos.json`, lido dos contratos uma única vez —
scripts/fase5/pinar_registro.py) e de um vínculo payTo⇔domínio verificado à parte
(mesa/vinculo.py). D-07: endereço é identidade, símbolo nunca decide nada.
`unverified` é estado de primeira classe (nível 4 da escada), nunca erro — a
POLÍTICA do comprador decide o teto para contraparte não verificada.

Funções internas do SDK do livro, nunca pacote standalone (D-23).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mesa.config import (
    CAIP2_BASE_SEPOLIA,
    CHECAGEM_VALIDADE_MAX_S,
    CHECAGEM_VALOR_MAX_MINOR,
)

REGISTRO_PATH = Path(__file__).parent / "registro_ativos.json"


@dataclass(frozen=True)
class Veredito:
    """Evidência, não booleano (invariante 4): motivo nomeado + prova completa."""

    aprovada: bool
    motivo: str
    evidencia: dict[str, Any] = field(default_factory=dict)


def carregar_registro() -> dict[str, Any]:
    """O registro pinado. As checagens só LEEM — nada de rede aqui."""
    dados: dict[str, Any] = json.loads(REGISTRO_PATH.read_text(encoding="utf-8"))
    return dados


def checar_ativo(rede: str, asset: str, registro: dict[str, Any]) -> Veredito:
    """Golpe 2 (ativo sósia): o ENDEREÇO do contrato está pinado naquela rede?"""
    por_rede = registro["ativos"].get(rede)
    if por_rede is None:
        return Veredito(False, "rede-desconhecida", {"rede": rede})
    if asset.lower() not in por_rede:
        return Veredito(False, "ativo-sosia", {
            "rede": rede, "asset_ofertado": asset,
            "pinados": sorted(por_rede.keys()),
            "nota": "símbolo NÃO foi consultado — endereço é identidade (D-07)"})
    return Veredito(True, "ok", {"rede": rede, "asset": asset.lower()})


def checar_decimais(rede: str, asset: str, decimais_afirmados: int | None,
                    registro: dict[str, Any]) -> Veredito:
    """Golpe 3 (decimais mentidos): a cotação afirma decimais ≠ do contrato?

    `None` = a cotação não afirma nada (wire v2 não carrega decimais): usamos o
    pinado e o valor cru é calculado por NÓS — aprovado por construção.
    """
    ativo = checar_ativo(rede, asset, registro)
    if not ativo.aprovada:
        return ativo
    pinado = int(registro["ativos"][rede][asset.lower()]["decimals"])
    if decimais_afirmados is not None and decimais_afirmados != pinado:
        return Veredito(False, "decimais-mentidos", {
            "afirmado": decimais_afirmados, "pinado_no_contrato": pinado,
            "rede": rede, "asset": asset.lower()})
    return Veredito(True, "ok", {"decimais": pinado, "fonte": "registro pinado on-chain"})


def checar_payto(pay_to: str, amount_minor: int,
                 vinculo: dict[str, Any] | None,
                 teto_unverified_minor: int | None) -> Veredito:
    """Golpe 1 (payTo trocado) + política para contraparte não verificada.

    `vinculo` vem de mesa/vinculo.py: {"nivel": 1..4, "payto": ..., "dominio": ...,
    "valido": bool}. Sem vínculo (ou nível 4) = unverified — primeira classe: passa
    se couber no teto da política (None = sem teto).
    """
    if vinculo and vinculo.get("valido") and int(vinculo.get("nivel", 4)) <= 3:
        if str(vinculo["payto"]).lower() != pay_to.lower():
            return Veredito(False, "payto-trocado", {
                "payto_da_cotacao": pay_to,
                "payto_vinculado_ao_dominio": vinculo["payto"],
                "dominio": vinculo.get("dominio"), "nivel": vinculo.get("nivel")})
        return Veredito(True, "ok", {"nivel": vinculo["nivel"],
                                     "dominio": vinculo.get("dominio")})
    if teto_unverified_minor is not None and amount_minor > teto_unverified_minor:
        return Veredito(False, "payto-nao-verificado-acima-do-teto", {
            "amount_minor": amount_minor, "teto_minor": teto_unverified_minor,
            "nivel": 4})
    return Veredito(True, "unverified", {
        "nivel": 4, "nota": "primeira classe, nunca erro — política decidiu aceitar"})


def checar_cotacao(*, rede: str, asset: str, pay_to: str, amount_minor: int,
                   decimais_afirmados: int | None = None,
                   registro: dict[str, Any] | None = None,
                   vinculo: dict[str, Any] | None = None,
                   teto_unverified_minor: int | None = None) -> Veredito:
    """Agrega as três checagens; curto-circuito no primeiro golpe detectado.

    Aprovada-mas-unverified SOBREVIVE à agregação (é evidência, não detalhe).
    """
    reg = registro if registro is not None else carregar_registro()
    payto_v = checar_payto(pay_to, amount_minor, vinculo, teto_unverified_minor)
    for v in (checar_ativo(rede, asset, reg),
              checar_decimais(rede, asset, decimais_afirmados, reg),
              payto_v):
        if not v.aprovada:
            return v
    if payto_v.motivo == "unverified":
        return payto_v
    return Veredito(True, "ok", {"rede": rede, "asset": asset.lower(),
                                 "pay_to": pay_to, "amount_minor": amount_minor})


def seletor_com_checagens(
    rede: str,
    *,
    registro: dict[str, Any] | None = None,
    cabe_no_orcamento: Callable[[int], bool] | None = None,
    vinculos: dict[str, dict[str, Any]] | None = None,
    teto_unverified_minor: int | None = None,
) -> Callable[[int, list[Any]], Any]:
    """Seletor para o x402Client: as checagens rodam ANTES de qualquer assinatura.

    Nenhum aceite aprovado ⇒ exceção ⇒ a compra simplesmente não acontece
    (fail-closed). `vinculos` é payTo(lower) → vínculo verificado (mesa/vinculo.py).
    """
    reg = registro if registro is not None else carregar_registro()

    def seletor(_version: int, requirements: list[Any]) -> Any:
        recusas: list[str] = []
        for req in requirements:
            if str(req.network) != rede:
                continue
            if str(req.scheme).lower() != "exact":
                recusas.append("esquema-nao-exact")
                continue
            valor = int(req.get_amount())
            # docs/seguranca.md furo 4: -5 passa em "≤ teto"; lixo gigante estoura o livro
            if valor <= 0 or valor > CHECAGEM_VALOR_MAX_MINOR:
                recusas.append("valor-invalido")
                continue
            # docs/seguranca.md furo 3: o SDK assina validBefore = now + maxTimeoutSeconds
            # DO VENDEDOR — sem este teto, uma cotação vira nota promissória de 30 anos
            validade = getattr(req, "max_timeout_seconds", None)
            if validade is not None and int(validade) > CHECAGEM_VALIDADE_MAX_S:
                recusas.append("validade-excessiva")
                continue
            v = checar_cotacao(
                rede=rede, asset=str(req.asset), pay_to=str(req.pay_to),
                amount_minor=valor, registro=reg,
                vinculo=(vinculos or {}).get(str(req.pay_to).lower()),
                teto_unverified_minor=teto_unverified_minor)
            if not v.aprovada:
                recusas.append(v.motivo)
                continue
            if cabe_no_orcamento is not None and not cabe_no_orcamento(valor):
                recusas.append("fora-do-orcamento")
                continue
            return req
        raise ValueError(f"nenhum aceite passou nas checagens: {recusas or 'rede errada'}")

    return seletor


def seletor_padrao_testnet() -> Callable[[int, list[Any]], Any]:
    """O seletor SEGURO que todo cliente de teste ganha por padrão (seguranca.md furo 8).

    Regra da casa: NENHUM cliente x402 sem checagens — nem em testnet. Base Sepolia,
    registro pinado, contraparte não verificada até US$ 1 (dinheiro de mentira, mas o
    hábito é o de verdade).
    """
    return seletor_com_checagens(CAIP2_BASE_SEPOLIA, teto_unverified_minor=1_000_000)
