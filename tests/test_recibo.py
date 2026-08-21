"""Recibo propagado v0: assina/verifica e detecta adulteração — sem rede, sem banco."""

from eth_account import Account

from mesa import recibo

PK = "0x" + "11" * 32  # chave de teste determinística (nunca usada em rede nenhuma)
ADDR = Account.from_key(PK).address

RECIBO = {
    "v": recibo.VERSAO,
    "comprador_delegado": ADDR,
    "recurso_hash": "ab" * 32,
    "amount_minor": 10_000,
    "authorization": {"from": ADDR, "nonce": "0x" + "cd" * 32},
}


def test_assina_e_verifica() -> None:
    sig = recibo.assinar(RECIBO, PK)
    assert recibo.signatario(RECIBO, sig).lower() == ADDR.lower()
    assert recibo.verificar(RECIBO, sig)


def test_adulteracao_e_detectada() -> None:
    sig = recibo.assinar(RECIBO, PK)
    adulterado = {**RECIBO, "amount_minor": 1}  # mudou o valor depois de assinado
    assert not recibo.verificar(adulterado, sig)


def test_recibo_de_outro_nao_passa() -> None:
    outra_pk = "0x" + "22" * 32
    sig_de_outro = recibo.assinar(RECIBO, outra_pk)  # assinou, mas não é o comprador_delegado
    assert not recibo.verificar(RECIBO, sig_de_outro)


def test_canonico_e_estavel_a_ordem_das_chaves() -> None:
    a = {"x": 1, "a": {"z": 2, "b": 3}}
    b = {"a": {"b": 3, "z": 2}, "x": 1}
    assert recibo.canonico(a) == recibo.canonico(b)
