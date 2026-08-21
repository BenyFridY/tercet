"""O GATE 1 como teste: a tabela-oráculo do caos, em dado sujo sintético.

Puro — sem banco, sem rede. Cada cenário do PLANO vira um caso aqui, com o
veredito esperado. Se a lógica de reconciliação mudar e quebrar um cenário,
este arquivo fica vermelho antes de qualquer demo.
"""

from mesa.reconcile import Compra, Liquidacao, Veredito, reconciliar


def compra(
    rid: str,
    *,
    delivered: bool = True,
    status: int | None = 200,
    authz: str | None = None,
    nonce: str | None = None,
    settled: bool = False,
) -> Compra:
    return Compra(
        request_id=rid, delivered=delivered, status_http=status,
        authz_id=authz, payer="0xabc" if authz else None, nonce=nonce, settled=settled,
    )


def test_normal_e_ok() -> None:
    r = reconciliar([compra("r1", authz="a1", nonce="0x01", settled=True)], [])
    assert [c.request_id for c in r[Veredito.OK]] == ["r1"]


def test_free_ride_e_uncollected() -> None:
    r = reconciliar([compra("r1", delivered=True, authz=None)], [])
    assert len(r[Veredito.UNCOLLECTED]) == 1


def test_fail_handler_e_autorizada_sem_liquidacao() -> None:
    # SDK serve-then-settle NÃO liquida em erro: authz existe, settlement não, entrega falhou
    r = reconciliar([compra("r1", delivered=False, status=500, authz="a1", nonce="0x01")], [])
    assert len(r[Veredito.AUTORIZADA_SEM_LIQUIDACAO]) == 1


def test_kill_after_settle_e_pago_sem_entrega() -> None:
    r = reconciliar(
        [compra("r1", delivered=False, status=None, authz="a1", nonce="0x01", settled=True)], []
    )
    assert len(r[Veredito.PAGO_SEM_ENTREGA]) == 1


def test_replay_detectado_pela_chave() -> None:
    original = compra("r1", authz="a1", nonce="0x01", settled=True)
    reenvio = compra("r2", delivered=False, status=402, authz="a2", nonce="0x01")
    r = reconciliar([original, reenvio], [])
    assert [c.request_id for c in r[Veredito.OK]] == ["r1"]
    assert [c.request_id for c in r[Veredito.REPLAY_EXTRA]] == ["r2"]


def test_liquidacao_sem_par_e_orfao_chain() -> None:
    liq = Liquidacao(settlement_id="s1", external_ref="0xdead", amount_minor=10_000, tem_leg=False)
    r = reconciliar([], [liq])
    assert len(r[Veredito.ORFAO_CHAIN]) == 1


def test_falha_antes_de_pagar_nao_e_anomalia_financeira() -> None:
    r = reconciliar([compra("r1", delivered=False, status=None, authz=None)], [])
    assert len(r[Veredito.FALHOU_SEM_PAGAR]) == 1


def test_cada_item_cai_em_exatamente_um_veredito() -> None:
    compras = [
        compra("r1", authz="a1", nonce="0x01", settled=True),
        compra("r2", delivered=True, authz=None),
        compra("r3", delivered=False, status=500, authz="a3", nonce="0x03"),
        compra("r4", delivered=False, status=None, authz="a4", nonce="0x04", settled=True),
        compra("r5", delivered=False, status=402, authz="a5", nonce="0x01"),
        compra("r6", delivered=False, status=None, authz=None),
    ]
    liqs = [Liquidacao("s1", "0x01", 10_000, tem_leg=True),
            Liquidacao("s2", "0x02", 10_000, tem_leg=False)]
    r = reconciliar(compras, liqs)
    total = sum(len(rows) for rows in r.values())
    assert total == len(compras) + 1  # +1 = só a liquidação órfã entra (a casada já está no OK)
