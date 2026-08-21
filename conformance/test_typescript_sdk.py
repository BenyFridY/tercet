"""Conformance do SDK TypeScript oficial (@x402/mcp) — via sonda node (ts/check.mjs).

Pula com aviso se node ou o pacote não estiverem disponíveis (instalação:
`npm install @x402/mcp` em C:\\dev\\mesa-ts-check — fora do OneDrive de propósito).

Resultado registrado em 20/08/2026 (v2.23.0): N1/N2 CONFORMES, N4/N5 conformes,
NC-3 presente (código 402, mesmo do Python). O TS está à frente do Python: o wrapper
funciona com o SDK MCP atual — as NC-1/NC-2 são exclusivas do pacote Python.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TS_DIR = Path(r"C:\dev\mesa-ts-check")
CHECK = Path(__file__).parent / "ts" / "check.mjs"


@pytest.fixture(scope="module")
def sonda() -> dict[str, object]:
    if shutil.which("node") is None:
        pytest.skip("node não disponível")
    if not (TS_DIR / "node_modules" / "@x402" / "mcp").exists():
        pytest.skip(f"@x402/mcp não instalado em {TS_DIR} (npm install @x402/mcp)")
    out = subprocess.run(
        ["node", str(CHECK)], capture_output=True, text=True, timeout=60, check=True
    )
    resultado: dict[str, object] = json.loads(out.stdout.strip().splitlines()[-1])
    return resultado


def test_n1_payment_required_in_band(sonda: dict[str, object]) -> None:
    assert sonda["n1_is_error_in_band"] is True


def test_n2_structured_content_e_texto(sonda: dict[str, object]) -> None:
    assert sonda["n2_structured_content"] is True
    assert sonda["n2_content_text_json"] is True


def test_n4_n5_meta_keys(sonda: dict[str, object]) -> None:
    assert sonda["n4_meta_key"] == "x402/payment"
    assert sonda["n5_meta_response_key"] == "x402/payment-response"


@pytest.mark.xfail(
    strict=True,
    reason="NC-3 (também no TS): 402 sem base normativa — vivo não define erro; "
    "SEP-2007 dormente pedia -32402",
)
def test_nc3_codigo_de_erro_tem_base_normativa(sonda: dict[str, object]) -> None:
    assert sonda["nc3_codigo_erro"] == -32402
