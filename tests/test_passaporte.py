"""Fase 10 — o passaporte é honesto ou não é nada.

Tudo puro (sem banco, sem rede): linhas sintéticas, chaves descartáveis. O que se
prova aqui: adulteração é detectada, assinatura de terceiro é recusada, o passaporte
REPORTA o pecado do próprio dono (replay, calote, órfão) em vez de escondê-lo, e a
prova de posse vale só para (passaporte, rota, agora).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from eth_account import Account

from mesa import passaporte as pp

AGORA = datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
TS = int(AGORA.timestamp())
REDE = "eip155:84532"
USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

# chaves descartáveis, determinísticas — NUNCA as reais (que nem entram em teste)
PK_PAYER = "0x" + "11" * 32
PAYER = Account.from_key(PK_PAYER).address
PK_OUTRO = "0x" + "22" * 32


def _linha(i: int, *, tx: str | None, nonce: str | None = None,
           delivered: bool = True, valid_until: datetime | None = None) -> pp.LinhaAuthz:
    return pp.LinhaAuthz(
        authz_id=f"a{i}", nonce=nonce or f"0x{i:064x}",
        valid_until_utc=valid_until or AGORA + timedelta(hours=1),
        ts_utc=AGORA - timedelta(days=1, minutes=i), delivered=delivered,
        pay_to="0x" + "ab" * 20, asset_contract=USDC,
        tx=tx, settled_amount_minor=10_000 if tx else None,
    )


def _limpo(n: int = 5) -> list[pp.LinhaAuthz]:
    return [_linha(i, tx=f"0xt{i:063x}") for i in range(n)]


def _emitir(linhas: list[pp.LinhaAuthz], sem_par: list[str] | None = None,
            pk: str = PK_PAYER) -> dict[str, Any]:
    payload = pp.montar_payload(
        payer_ref=PAYER, rede=REDE, linhas=linhas, sem_par_do_payer=sem_par or [],
        periodos=[{"data": "2026-08-21", "merkle_root": "0x" + "00" * 32}], agora=AGORA,
    )
    return pp.assinar(payload, pk)


# ------------------------------------------------------------------ o caminho feliz

def test_ciclo_limpo_aceito() -> None:
    art = _emitir(_limpo())
    assert pp.verificar_offline(art) == []
    aceito, motivos = pp.avaliar_politica(art, pp.Politica(), AGORA)
    assert aceito and motivos == []
    m = art["payload"]["metricas"]
    assert m == {"autorizacoes": 5, "liquidadas": 5, "nonces_reusados": 0,
                 "entregas_sem_pagar": 0, "cobrancas_pendentes": 0,
                 "orfaos_chain_inexplicados": 0}


def test_ressalvas_viajam_assinadas() -> None:
    art = _emitir(_limpo())
    assert list(art["payload"]["ressalvas"]) == list(pp.RESSALVAS_V0)
    art["payload"]["ressalvas"] = []  # tirar a ressalva quebra a assinatura
    assert "assinatura-nao-e-do-sujeito" in pp.verificar_offline(art)


# ------------------------------------- o passaporte reporta o pecado do próprio dono

def test_replay_do_dono_reportado_e_recusado() -> None:
    linhas = _limpo(4)
    # o replay da Fase 1: mesma nonce assinada 2x — uma liquidou, a outra não
    linhas.append(_linha(9, tx=None, nonce=linhas[0].nonce))
    art = _emitir(linhas)
    assert art["payload"]["metricas"]["nonces_reusados"] == 1
    assert pp.verificar_offline(art) == []  # o documento é ÍNTEGRO; o histórico é sujo
    aceito, motivos = pp.avaliar_politica(art, pp.Politica(), AGORA)
    assert not aceito and "nonce-reusado" in motivos


def test_calote_expirado_conta_pendente_vivo_nao() -> None:
    linhas = _limpo(4)
    linhas.append(_linha(7, tx=None, delivered=True,
                         valid_until=AGORA - timedelta(hours=1)))  # morta = calote
    linhas.append(_linha(8, tx=None, delivered=False))             # viva = pendente
    art = _emitir(linhas)
    m = art["payload"]["metricas"]
    assert m["entregas_sem_pagar"] == 1 and m["cobrancas_pendentes"] == 1
    aceito, motivos = pp.avaliar_politica(art, pp.Politica(), AGORA)
    assert not aceito and "entrega-consumida-sem-pagar" in motivos


def test_orfao_na_chain_recusa() -> None:
    art = _emitir(_limpo(), sem_par=["0x" + "dd" * 32])
    assert art["payload"]["metricas"]["orfaos_chain_inexplicados"] == 1
    aceito, motivos = pp.avaliar_politica(art, pp.Politica(), AGORA)
    assert not aceito and "liquidacao-fora-do-livro" in motivos


def test_taxa_baixa_e_historico_curto() -> None:
    fraco = [_linha(0, tx="0x" + "aa" * 32), _linha(1, tx=None, delivered=False)]
    art = _emitir(fraco)  # 1/2 = 50% < 80%, e 2 < mínimo de 3
    aceito, motivos = pp.avaliar_politica(art, pp.Politica(), AGORA)
    assert not aceito
    assert {"historico-curto", "taxa-de-liquidacao-abaixo-do-minimo"} <= set(motivos)


def test_passaporte_vencido() -> None:
    art = _emitir(_limpo())
    aceito, motivos = pp.avaliar_politica(art, pp.Politica(), AGORA + timedelta(days=31))
    assert not aceito and motivos == ["passaporte-vencido"]


# ----------------------------------------------------------- adulteração e falsidade

def test_metrica_adulterada_detectada() -> None:
    art = _emitir(_limpo())
    art["payload"]["metricas"]["liquidadas"] += 1  # inflar histórico
    falhas = pp.verificar_offline(art)
    assert "liquidadas-nao-bate-com-evidencia" in falhas
    assert "assinatura-nao-e-do-sujeito" in falhas  # e o hash mudou


def test_assinatura_de_terceiro_recusada() -> None:
    payload = _emitir(_limpo())["payload"]
    with pytest.raises(ValueError, match="assinatura-nao-e-do-sujeito"):
        pp.assinar(payload, PK_OUTRO)  # o emissor se recusa a emitir falso
    forjado = {"formato": pp.FORMATO, "payload": payload,
               "assinatura": pp._assinar_hash(PK_OUTRO, pp.passaporte_hash(payload))}
    assert "assinatura-nao-e-do-sujeito" in pp.verificar_offline(forjado)


def test_nonce_duplicado_na_evidencia_e_forja() -> None:
    art = _emitir(_limpo())
    art["payload"]["evidencia"].append(dict(art["payload"]["evidencia"][0]))
    art["payload"]["metricas"]["liquidadas"] += 1
    falhas = pp.verificar_offline(art)
    assert "nonce-duplicado-na-evidencia" in falhas


def test_sem_historico_nao_emite() -> None:
    with pytest.raises(ValueError, match="sem histórico"):
        pp.montar_payload(payer_ref=PAYER, rede=REDE, linhas=[],
                          sem_par_do_payer=[], periodos=[], agora=AGORA)


# ------------------------------------------------------------------ prova de posse

def test_prova_de_posse_valida() -> None:
    art = _emitir(_limpo())
    h = pp.passaporte_hash(art["payload"])
    prova = pp.prova_de_posse(PK_PAYER, passaporte_hash_hex=h, rota="/lote", ts_unix=TS)
    assert pp.verificar_prova(prova, art, rota="/lote", agora_unix=TS + 5) == []


def test_prova_de_ladrao_de_arquivo() -> None:
    art = _emitir(_limpo())  # o ladrão TEM o arquivo, não tem a chave
    h = pp.passaporte_hash(art["payload"])
    prova = pp.prova_de_posse(PK_OUTRO, passaporte_hash_hex=h, rota="/lote", ts_unix=TS)
    assert "prova-nao-e-do-sujeito" in pp.verificar_prova(
        prova, art, rota="/lote", agora_unix=TS)


def test_prova_nao_transfere_de_rota_nem_de_hora() -> None:
    art = _emitir(_limpo())
    h = pp.passaporte_hash(art["payload"])
    prova = pp.prova_de_posse(PK_PAYER, passaporte_hash_hex=h, rota="/lote", ts_unix=TS)
    assert "prova-de-outra-rota" in pp.verificar_prova(
        prova, art, rota="/unidade", agora_unix=TS)
    assert "prova-vencida" in pp.verificar_prova(
        prova, art, rota="/lote", agora_unix=TS + pp.PROVA_JANELA_S + 1)


def test_prova_de_outro_passaporte() -> None:
    art_a = _emitir(_limpo())
    art_b = _emitir(_limpo(4))
    prova_b = pp.prova_de_posse(
        PK_PAYER, passaporte_hash_hex=pp.passaporte_hash(art_b["payload"]),
        rota="/lote", ts_unix=TS)
    assert "prova-de-outro-passaporte" in pp.verificar_prova(
        prova_b, art_a, rota="/lote", agora_unix=TS)
