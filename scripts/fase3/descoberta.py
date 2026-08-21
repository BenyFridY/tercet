"""Fase 3 / T2 — descoberta: enumerar candidatos nos índices públicos. 100% grátis.

Índices consultados (nenhum exige chave):
- Bazaar da Coinbase (CDP): lista de recursos x402 anunciados no facilitator deles.
- Facilitator x402.org: endpoint de discovery do facilitator de referência.

Filtros PRÉ-COMPROMETIDOS (fase3.md, regras 2–4 — decididos antes de ver qualquer fonte):
- rede: Base MAINNET (aceita "base" v1 ou "eip155:8453" CAIP-2);
- asset: USDC canônico da Circle (comparação por endereço, nunca por símbolo);
- esquema: exact;
- preço anunciado ≤ US$ 1,00 (teto por compra).

Dedup por domínio, até 15 candidatos por SELEÇÃO ESTRATIFICADA por faixa de preço
(só "mais barato primeiro" enche a lista de demos de US$ 0,001; as APIs de verdade
moram nas faixas de centavos — quotas por faixa, mecânicas, decididas antes de olhar
nomes). Saída versionada no repo: scripts/fase3/candidatos.json — URL, preço
anunciado, payTo, índice de origem.
Tudo que foi DESCARTADO é contado por motivo (nada de corte silencioso).

Uso: uv run python scripts/fase3/descoberta.py
"""

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from rich.console import Console
from rich.table import Table

from mesa.config import CENSO_TETO_POR_COMPRA_MINOR, USDC_BASE_MAINNET

console = Console()
SAIDA = Path(__file__).parent / "candidatos.json"
MAX_CANDIDATOS = 15
PAGINA = 100
MAX_PAGINAS = 30  # hard-stop de segurança; se bater, o corte é LOGADO, nunca silencioso

# Estratos de preço (minor units) e quotas — a rodada fica ~US$ 3–6 no pior caso,
# bem abaixo do teto de US$ 20, e o censo não vira "só demos de US$ 0,001".
ESTRATOS: list[tuple[int, int, int]] = [
    (1, 2_000, 6),            # até US$ 0,002 — os micro
    (2_000, 20_000, 4),       # US$ 0,002–0,02
    (20_000, 200_000, 3),     # US$ 0,02–0,20
    (200_000, 1_000_001, 2),  # US$ 0,20–1,00 — os "caros" dentro do teto
]

INDICES = {
    "bazaar-cdp": "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources",
    "facilitator-x402org": "https://x402.org/facilitator/discovery/resources",
}
REDES_BASE_MAINNET = {"base", "eip155:8453"}


def _itens_do_indice(nome: str, url: str) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []
    with httpx.Client(timeout=20) as cli:
        for pagina in range(MAX_PAGINAS):
            try:
                r = cli.get(url, params={"limit": PAGINA, "offset": pagina * PAGINA})
                r.raise_for_status()
            except httpx.HTTPError as e:
                console.print(f"[yellow]{nome}: falhou na página {pagina} ({e}) — "
                              f"seguindo com o que veio[/yellow]")
                break
            corpo = r.json()
            lote = corpo.get("items", corpo.get("resources", []))
            if not isinstance(lote, list) or not lote:
                break
            itens.extend(lote)
            if len(lote) < PAGINA:
                break
        else:
            console.print(f"[yellow]{nome}: parou no hard-stop de {MAX_PAGINAS} páginas — "
                          f"o índice tem MAIS itens que os {len(itens)} lidos[/yellow]")
    console.print(f"{nome}: {len(itens)} itens brutos")
    return itens


def _preco_minor(aceite: dict[str, Any]) -> int | None:
    for campo in ("maxAmountRequired", "amount", "maxAmount"):
        bruto = aceite.get(campo)
        if bruto is not None:
            try:
                return int(str(bruto))
            except ValueError:
                return None
    return None


def _classificar(item: dict[str, Any], indice: str,
                 motivos: Counter[str]) -> dict[str, Any] | None:
    """Devolve o candidato normalizado, ou None (contando o motivo do descarte)."""
    recurso = item.get("resource") or item.get("url")
    if not isinstance(recurso, str) or not recurso.startswith("http"):
        motivos["sem-url"] += 1
        return None
    aceites = item.get("accepts") or []
    if not isinstance(aceites, list) or not aceites:
        motivos["sem-accepts"] += 1
        return None

    for aceite in aceites:
        if not isinstance(aceite, dict):
            continue
        rede = str(aceite.get("network", "")).lower()
        if rede not in REDES_BASE_MAINNET:
            continue  # avalia o próximo aceite; motivo contado só se nenhum servir
        if str(aceite.get("scheme", "")).lower() != "exact":
            motivos["esquema-nao-exact"] += 1
            return None
        asset = str(aceite.get("asset", ""))
        if asset.lower() != USDC_BASE_MAINNET.lower():
            motivos["asset-nao-canonico"] += 1
            return None
        preco = _preco_minor(aceite)
        if preco is None:
            motivos["preco-ilegivel"] += 1
            return None
        if preco > CENSO_TETO_POR_COMPRA_MINOR:
            motivos["acima-do-teto-usd1"] += 1
            return None
        if preco <= 0:
            motivos["preco-zero"] += 1
            return None
        # método/corpo de exemplo do Bazaar (fontes POST-only devolvem 405 no GET)
        info = (item.get("extensions", {}).get("bazaar", {}).get("info", {})
                .get("input", {})) if isinstance(item.get("extensions"), dict) else {}
        qualidade = item.get("quality") or {}
        return {
            "url": recurso,
            "dominio": urlparse(recurso).netloc.lower(),
            "preco_anunciado_minor": preco,
            "pay_to": str(aceite.get("payTo", "")),
            "asset": asset,
            "rede": rede,
            "metodo": str(info.get("method", "GET")).upper(),
            "corpo_exemplo": info.get("body") if isinstance(info.get("body"), dict) else None,
            "descricao": str(item.get("description", ""))[:200],
            "indice": indice,
            "last_updated": item.get("lastUpdated"),
            # uso real publicado pelo índice — contexto, não critério de seleção
            "chamadas_30d": qualidade.get("l30DaysTotalCalls"),
            "pagadores_30d": qualidade.get("l30DaysUniquePayers"),
        }
    motivos["sem-aceite-base-mainnet"] += 1
    return None


def main() -> None:
    motivos: Counter[str] = Counter()
    candidatos: list[dict[str, Any]] = []
    for nome, url in INDICES.items():
        for item in _itens_do_indice(nome, url):
            c = _classificar(item, nome, motivos)
            if c:
                candidatos.append(c)

    # dedup por domínio (1 recurso por domínio — diversidade > profundidade na rodada 1)
    por_dominio: dict[str, dict[str, Any]] = {}
    for c in sorted(candidatos, key=lambda c: c["preco_anunciado_minor"]):
        por_dominio.setdefault(c["dominio"], c)
    descartados_dedup = len(candidatos) - len(por_dominio)

    # seleção estratificada: quotas por faixa de preço; sobras preenchem barato-primeiro
    restantes = sorted(por_dominio.values(), key=lambda c: c["preco_anunciado_minor"])
    finais: list[dict[str, Any]] = []
    for minimo, maximo, quota in ESTRATOS:
        faixa = [c for c in restantes
                 if minimo <= c["preco_anunciado_minor"] < maximo and c not in finais]
        finais.extend(faixa[:quota])
    sobras = [c for c in restantes if c not in finais]
    finais.extend(sobras[:MAX_CANDIDATOS - len(finais)])
    finais = sorted(finais, key=lambda c: c["preco_anunciado_minor"])[:MAX_CANDIDATOS]
    cortados_cap = len(por_dominio) - len(finais)

    SAIDA.write_text(json.dumps({
        "gerado_utc": datetime.now(UTC).isoformat(),
        "filtros": {
            "rede": sorted(REDES_BASE_MAINNET),
            "asset": USDC_BASE_MAINNET,
            "esquema": "exact",
            "teto_por_compra_minor": CENSO_TETO_POR_COMPRA_MINOR,
            "estratos_preco_quota": ESTRATOS,
        },
        "descartes_por_motivo": dict(motivos),
        "duplicatas_de_dominio": descartados_dedup,
        "cortados_pelo_cap_15": cortados_cap,
        "candidatos": finais,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    t = Table(title=f"candidatos do censo — {len(finais)} (cap {MAX_CANDIDATOS})")
    t.add_column("domínio")
    t.add_column("preço US$", justify="right")
    t.add_column("índice")
    for c in finais:
        t.add_row(c["dominio"], f"{c['preco_anunciado_minor'] / 1e6:.4f}", c["indice"])
    console.print(t)
    console.print(f"descartes: {dict(motivos)} · duplicatas de domínio: {descartados_dedup}"
                  f" · cortados pelo cap: {cortados_cap}")
    console.print(f"gravado em {SAIDA}")


if __name__ == "__main__":
    main()
