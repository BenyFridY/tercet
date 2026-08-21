"""Fase 4 / T5: a extensão oficial offer-and-receipt — ida e volta + adulteração."""

from eth_account import Account

from mesa import recibo_x402

PK = "0x" + "11" * 32
ENDERECO = Account.from_key(PK).address


def test_recibo_ida_e_volta() -> None:
    r = recibo_x402.emitir_recibo(
        PK, network="eip155:84532", resource_url="http://127.0.0.1:8402/brinquedo",
        payer="0x" + "22" * 20, issued_at=1_755_000_000, transaction="0x" + "ab" * 32)
    assert r["format"] == "eip712"
    assert recibo_x402.signatario(r) == ENDERECO


def test_recibo_privacidade_minima() -> None:
    r = recibo_x402.emitir_recibo(
        PK, network="eip155:8453", resource_url="https://x", payer="0x" + "22" * 20,
        issued_at=1, transaction="")  # opcional ausente = "" (regra do spec §5.3)
    assert r["payload"]["transaction"] == ""
    assert recibo_x402.signatario(r) == ENDERECO


def test_oferta_ida_e_volta_e_autorizacao() -> None:
    o = recibo_x402.emitir_oferta(
        PK, resource_url="https://x/y", scheme="exact", network="eip155:8453",
        asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", pay_to=ENDERECO,
        amount="10000", accept_index=0)
    assert o["acceptIndex"] == 0
    assert recibo_x402.verificar_oferta(o)  # signer == payTo


def test_adulteracao_muda_o_signatario() -> None:
    r = recibo_x402.emitir_recibo(
        PK, network="eip155:8453", resource_url="https://x", payer="0x" + "22" * 20,
        issued_at=1, transaction="")
    r["payload"]["payer"] = "0x" + "33" * 20  # adultera 1 campo assinado
    assert recibo_x402.signatario(r) != ENDERECO  # recupera OUTRO endereço


def test_oferta_de_impostor_reprovada() -> None:
    o = recibo_x402.emitir_oferta(  # assina com chave que NÃO é a do payTo
        PK, resource_url="https://x", scheme="exact", network="eip155:8453",
        asset="0xAsset", pay_to="0x" + "44" * 20, amount="1")
    assert not recibo_x402.verificar_oferta(o)
