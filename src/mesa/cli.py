"""CLI do livro: `uv run python -m mesa.cli` imprime a reconciliação de três pontas."""

from rich.console import Console
from rich.table import Table

from mesa import db
from mesa.reconcile import EXPLICACAO, Veredito, carregar, reconciliar

ANOMALIAS = {
    Veredito.PAGO_SEM_ENTREGA, Veredito.ORFAO_CHAIN,
    Veredito.REPLAY_EXTRA, Veredito.UNCOLLECTED,
}


def main() -> None:
    console = Console()
    conn = db.connect()
    compras, liquidacoes = carregar(conn)
    resultado = reconciliar(compras, liquidacoes)

    table = Table(title="mesa — reconciliação de três pontas")
    table.add_column("veredito")
    table.add_column("qtde", justify="right")
    table.add_column("o que significa")
    for veredito in Veredito:
        linhas = resultado[veredito]
        estilo = "red" if (veredito in ANOMALIAS and linhas) else (
            "green" if veredito is Veredito.OK else "yellow"
        )
        table.add_row(
            f"[{estilo}]{veredito.value}[/]", str(len(linhas)), EXPLICACAO[veredito]
        )
    console.print(table)
    console.print(
        f"compras no livro: {len(compras)} · liquidações na chain: {len(liquidacoes)}"
    )


if __name__ == "__main__":
    main()
