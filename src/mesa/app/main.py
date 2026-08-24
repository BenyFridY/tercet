"""O servidor da mesa — cinco telas, somente leitura, dado real (D-35).

Subir: uv run mesa-app   (ou: uv run uvicorn mesa.app.main:app --port 8400)
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from mesa import telas
from mesa.app import dados, jobs

app = FastAPI(title="mesa — o livro da compra feita por agente")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# estado derivado (telas.derivar_estado) → classe visual da pílula
ESTADO_CLASSE = {
    "liquidado": "ok", "fatura-conciliada": "info", "ingerido": "roxo",
    "pago-sem-entrega": "ruim", "entregue-sem-cobrar": "ruim",
    "cobranca-pendente": "aviso", "autorizado-pendente": "aviso",
    "expirou-sem-uso": "mudo", "sem-pagamento": "mudo", "fatura-pendente": "aviso",
}


def _fmt_usd(minor: int | None, casas: int = 4) -> str:
    """Unidade mínima (6 casas) → 'US$' no padrão do design (vírgula decimal)."""
    if minor is None:
        return "—"
    v = Decimal(minor) / 1_000_000
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _curto(texto: str | None, n: int = 10) -> str:
    if not texto:
        return "—"
    return texto if len(texto) <= n + 2 else f"{texto[:n]}…"


templates.env.filters["usd"] = _fmt_usd
templates.env.filters["usd2"] = lambda m: _fmt_usd(m, 2)
templates.env.filters["curto"] = _curto


def _render(request: Request, tela: str, contexto: dict[str, Any]) -> HTMLResponse:
    with dados.conectar_leitura() as conn:
        status = dados.status_livro(conn)
    contexto.update({"tela": tela, "status": status, "estado_classe": ESTADO_CLASSE})
    return templates.TemplateResponse(request, f"{tela}.html", contexto)


@app.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    return RedirectResponse("/blotter")


@app.get("/blotter", response_class=HTMLResponse)
def blotter(request: Request, dias: int | None = None) -> HTMLResponse:
    # dias = janela de período (7/30); None = tudo. Recomputado no SERVIDOR:
    # os cards, o gráfico e a tabela contam a MESMA janela — nunca números mistos.
    with dados.conectar_leitura() as conn:
        ctx = dados.contexto_blotter(conn, dias=dias)
    return _render(request, "blotter", ctx)


@app.get("/tca", response_class=HTMLResponse)
def tca(request: Request) -> HTMLResponse:
    with dados.conectar_leitura() as conn:
        ctx = dados.contexto_tca(conn)
    return _render(request, "tca", ctx)


@app.get("/risco", response_class=HTMLResponse)
def risco(request: Request) -> HTMLResponse:
    with dados.conectar_leitura() as conn:
        ctx = dados.contexto_risco(conn)
    return _render(request, "risco", ctx)


@app.get("/laboratorio", response_class=HTMLResponse)
def laboratorio_(request: Request) -> HTMLResponse:
    with dados.conectar_leitura() as conn:
        ctx = dados.contexto_laboratorio(conn)
    return _render(request, "laboratorio", ctx)


@app.get("/livros", response_class=HTMLResponse)
def livros(request: Request) -> HTMLResponse:
    with dados.conectar_leitura() as conn:
        ctx = dados.contexto_livros(conn)
    return _render(request, "livros", ctx)


@app.get("/operacoes", response_class=HTMLResponse)
def operacoes(request: Request) -> HTMLResponse:
    return _render(request, "operacoes",
                   {"operacoes": list(jobs.OPERACOES.values()), "job": jobs.status()})


@app.post("/api/operacao/{nome}")
def operacao_iniciar(nome: str) -> JSONResponse:
    """Dispara UMA operação da lista fechada (D-36). 404 fora da lista; 409 ocupado."""
    if nome not in jobs.OPERACOES:
        raise HTTPException(404, f"operação desconhecida: {nome!r}")
    ok, motivo = jobs.iniciar(nome)
    if not ok:
        raise HTTPException(409, motivo)
    return JSONResponse({"ok": True, "motivo": motivo})


@app.get("/api/operacao")
def operacao_status() -> JSONResponse:
    return JSONResponse({"job": jobs.status()})


@app.get("/api/compra/{rid}")
def compra(rid: str) -> JSONResponse:
    """A gaveta: a cadeia de eventos de UMA compra (somente leitura, como tudo)."""
    with dados.conectar_leitura() as conn:
        linhas = telas.carregar_linhas(conn, dados.mapa_dominios())
        alvo = next((ln for ln in linhas if ln.rid == rid), None)
        if alvo is None:
            raise HTTPException(404, "compra não encontrada no livro")
        eventos = telas.eventos_da_compra(conn, rid)
    return JSONResponse({
        "rid": alvo.rid, "ts": alvo.ts_utc.isoformat(), "estado": alvo.estado,
        "dominio": alvo.dominio, "recurso_hash": alvo.recurso_hash,
        "rail": alvo.rail, "network": alvo.network, "agente": alvo.agente,
        "tarefa": alvo.tarefa, "amount_minor": alvo.amount_minor,
        "settled_minor": alvo.settled_minor, "pay_to": alvo.pay_to,
        "tx": alvo.tx, "body_sha256": alvo.body_sha256,
        "body_bytes": alvo.body_bytes, "principal_ref": alvo.principal_ref,
        "repetido": alvo.repetido, "dedup_n": alvo.dedup_n, "eventos": eventos,
    })


def rodar() -> None:
    """Entry point do pacote: `mesa-app`."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8400)


if __name__ == "__main__":
    rodar()
