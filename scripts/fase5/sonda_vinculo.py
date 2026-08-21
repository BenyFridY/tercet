"""Fase 5 / T3 — sonda o vínculo reverso nos 15 domínios do censo. Grátis.

Para cada fonte: busca `/.well-known/x402-payto` (online, só coleta) e VERIFICA a
assinatura offline contra o payTo cotado na sondagem da Fase 3. O resultado entra
no livro como `verification` (evidência com o NÍVEL da escada — `unknown` nível 4 é
primeira classe, não erro).

Achado esperado (e é o dado que justifica a extensão): 0/15 publicam o vínculo.

Uso: uv run python scripts/fase5/sonda_vinculo.py
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from mesa import db, vinculo

console = Console()
SONDAGEM = Path(__file__).resolve().parents[1] / "fase3" / "sondagem_resultado.json"
SAIDA = Path(__file__).parent / "sonda_vinculo_resultado.json"


def main() -> None:
    conn = db.connect()
    db.apply_migrations(conn)
    fontes = [r for r in json.loads(SONDAGEM.read_text(encoding="utf-8"))["resultados"]
              if r["cotacao_valida"]]

    resultados: list[dict[str, Any]] = []
    for f in fontes:
        dominio, payto = f["dominio"], str(f["pay_to"])
        status, doc = vinculo.sondar(dominio)
        if doc is not None:
            v = vinculo.verificar_wellknown(doc, dominio, payto)
            resultado = "verified" if v["valido"] else "failed"
            evidencia: dict[str, Any] = {"nivel": v["nivel"], "http_status": status,
                                         "detalhe": v, "well_known": doc}
        else:
            resultado = "unknown"  # nível 4: unverified é primeira classe
            evidencia = {"nivel": 4, "http_status": status,
                         "nota": "well-known ausente/ilegível — unverified (N4)"}
        db.insert_verification(
            conn, subject_type="pay_to", subject_ref=f"{dominio}|{payto.lower()}",
            method="x402-payto-binding/N2-sonda", result=resultado,
            evidence=evidencia)
        resultados.append({"dominio": dominio, "payto": payto,
                           "http_status": status, "resultado": resultado,
                           "nivel": evidencia["nivel"]})

    verificados = sum(1 for r in resultados if r["resultado"] == "verified")
    t = Table(title="vínculo reverso payTo⇔domínio — sonda no censo")
    t.add_column("domínio")
    t.add_column("well-known")
    t.add_column("resultado")
    for r in resultados:
        t.add_row(r["dominio"],
                  str(r["http_status"]) if r["http_status"] else "sem resposta",
                  f"{r['resultado']} (N{r['nivel']})")
    console.print(t)
    nota = ("o mecanismo é necessário e inexistente: é o dado da proposta"
            if verificados == 0 else "há adoção!")
    console.print(f"[bold]{verificados}/{len(resultados)} publicam vínculo verificável "
                  f"— {nota}[/bold]")
    SAIDA.write_text(json.dumps({
        "gerado_utc": datetime.now(UTC).isoformat(),
        "verificados": verificados, "sondados": len(resultados),
        "resultados": resultados,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"gravado em {SAIDA} + verification rows no livro")


if __name__ == "__main__":
    main()
