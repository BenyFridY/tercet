"""O pedaço do GATE 2 que é matemática: a soma bate em qualquer altura, como teste.

Árvore sintética de 3 níveis com compras em profundidades diferentes — sem banco,
sem rede: rollup e verificações são funções puras (mesmo padrão do reconcile).
"""

from mesa.arvore import No, Problema, rollup, total_das_raizes, verificar

# tarefa (raiz)
# ├── preparar
# ├── pesquisar
# │   ├── comprar-a   (compra: 10_000)
# │   └── comprar-b   (compra: 10_000)
# └── sintetizar      (compra: 5_000)
ARVORE = [
    No("raiz", None, "tarefa"),
    No("prep", "raiz", "preparar"),
    No("pesq", "raiz", "pesquisar"),
    No("ca", "pesq", "comprar-a"),
    No("cb", "pesq", "comprar-b"),
    No("sint", "raiz", "sintetizar"),
]
GASTO = {"ca": 10_000, "cb": 10_000, "sint": 5_000}


def test_arvore_integra_nao_tem_problemas() -> None:
    assert verificar(ARVORE, GASTO) == []


def test_soma_bate_na_folha() -> None:
    acc = rollup(ARVORE, GASTO)
    assert acc["ca"] == 10_000
    assert acc["cb"] == 10_000
    assert acc["prep"] == 0


def test_soma_bate_no_meio() -> None:
    acc = rollup(ARVORE, GASTO)
    assert acc["pesq"] == 20_000  # os dois filhos, nada próprio


def test_soma_bate_no_topo_e_igual_ao_total() -> None:
    acc = rollup(ARVORE, GASTO)
    assert acc["raiz"] == 25_000
    assert total_das_raizes(ARVORE, acc) == sum(GASTO.values())


def test_cada_no_e_proprio_mais_filhos() -> None:
    """A definição da altura: TODO nó = gasto próprio + soma dos rollups dos filhos."""
    acc = rollup(ARVORE, GASTO)
    for n in ARVORE:
        filhos = [f for f in ARVORE if f.parent_span_id == n.span_id]
        assert acc[n.span_id] == GASTO.get(n.span_id, 0) + sum(acc[f.span_id] for f in filhos)


def test_compra_em_span_inexistente_e_detectada() -> None:
    """A compra aninhada que 'desaparece' — o produto existe para pegar isso."""
    problemas = verificar(ARVORE, {**GASTO, "fantasma": 999})
    esperado = Problema("compra-sem-span", "compra pendurada em span inexistente: fantasma")
    assert esperado in problemas


def test_raiz_dupla_e_span_orfao_sao_detectados() -> None:
    quebrada = [*ARVORE, No("raiz2", None, "segunda-raiz"), No("perdido", "nao-existe", "x")]
    tipos = {p.tipo for p in verificar(quebrada, GASTO)}
    assert tipos == {"raiz-multipla", "span-orfao"}
