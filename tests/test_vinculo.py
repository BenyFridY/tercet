"""Fase 5 / T3: o vínculo reverso (nível 2) — ida e volta, impostor, domínio trocado."""

from eth_account import Account

from mesa import checagens, vinculo

PK = "0x" + "55" * 32
ENDERECO = Account.from_key(PK).address
DOMINIO = "vendedor.example"


def test_ida_e_volta_n2() -> None:
    doc = vinculo.emitir_wellknown(PK, DOMINIO, ["eip155:84532"])
    v = vinculo.verificar_wellknown(doc, DOMINIO, ENDERECO)
    assert v["valido"] and v["nivel"] == 2
    assert v["payto"] == ENDERECO


def test_impostor_assina_payto_alheio() -> None:
    """Impostor publica binding com o payTo da vítima mas assina com a chave dele."""
    doc = vinculo.emitir_wellknown(PK, DOMINIO, ["eip155:84532"])
    vitima = "0x" + "66" * 20
    doc["bindings"][0]["address"] = vitima  # forja o address; assinatura é do impostor
    v = vinculo.verificar_wellknown(doc, DOMINIO, vitima)
    assert not v["valido"]
    assert v["motivo"] == "assinante-nao-e-o-endereco"


def test_dominio_trocado_reprova() -> None:
    """O documento de um domínio replicado em OUTRO domínio não vale (a mensagem
    assinada carrega o domínio — replay entre domínios quebra)."""
    doc = vinculo.emitir_wellknown(PK, DOMINIO, ["eip155:84532"])
    v = vinculo.verificar_wellknown(doc, "atacante.example", ENDERECO)
    assert not v["valido"]
    assert v["motivo"] == "dominio-declarado-diferente-do-sondado"


def test_vinculo_alimenta_checagens() -> None:
    """Ponta a ponta offline: well-known N2 verificado vira insumo do checar_payto."""
    doc = vinculo.emitir_wellknown(PK, DOMINIO, ["eip155:8453"])
    v = vinculo.verificar_wellknown(doc, DOMINIO, ENDERECO)
    ok = checagens.checar_payto(ENDERECO, 10_000, v, teto_unverified_minor=1)
    assert ok.aprovada and ok.motivo == "ok" and ok.evidencia["nivel"] == 2
    trocado = checagens.checar_payto("0x" + "77" * 20, 10_000, v,
                                     teto_unverified_minor=None)
    assert not trocado.aprovada and trocado.motivo == "payto-trocado"
