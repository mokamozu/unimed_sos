"""Controle de Treinamentos - SOS Emergências Médicas (Unimed Vitória).

Execução:  uvicorn main:app --reload
"""
import json
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Recursos (static, seed) ficam dentro do programa; o banco fica em Documentos para facilitar o backup.
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
DATA_DIR = (Path.home() / "Documents" / "Controle Treinamentos SOS") if getattr(sys, "frozen", False) else BASE
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "sos.db"
SEED = json.loads((BASE / "seed.json").read_text("utf-8"))
PRAZO_FINAL = SEED["config"]["deadline"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS participantes(
  mat TEXT PRIMARY KEY, nome TEXT NOT NULL, cargo TEXT NOT NULL,
  ativo INTEGER NOT NULL DEFAULT 1, email TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS turmas(
  id INTEGER PRIMARY KEY, code TEXT, tema TEXT, data_txt TEXT, data_iso TEXT,
  instrutores TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS presencas(
  turma_id INTEGER, mat TEXT, presente INTEGER NOT NULL, justificativa TEXT DEFAULT '',
  PRIMARY KEY(turma_id, mat));
"""


def data_iso(txt: str) -> str:
    """'14-15/02/2026' -> '2026-02-14' (primeiro dia da turma)."""
    m = re.search(r"(\d{1,2})(?:-\d{1,2})?/(\d{2})/(\d{4})", txt)
    return f"{m[3]}-{m[2]}-{int(m[1]):02d}" if m else ""


@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def q(con, sql, *args):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def init_db():
    with db() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM participantes").fetchone()[0]:
            return
        for p in SEED["participantes"]:
            c.execute("INSERT INTO participantes(mat,nome,cargo,ativo) VALUES(?,?,?,?)",
                      (p["mat"], p["nome"], p["cargo"], 0 if p.get("isEx") else 1))
        for t in SEED["turmas"]:
            c.execute("INSERT INTO turmas VALUES(?,?,?,?,?,?,?)",
                      (t["id"], t["code"], t["tema"], t["data"], data_iso(t["data"]),
                       t["instrutores"], t["status"]))
            for mat in t.get("presentes", []):
                c.execute("INSERT OR IGNORE INTO presencas VALUES(?,?,1,'')", (t["id"], mat))
            for mat, txt in (t.get("justificativas") or {}).items():
                c.execute("INSERT OR IGNORE INTO presencas VALUES(?,?,0,?)", (t["id"], mat, txt))


def ativos_com_presencas(c):
    return q(c, """SELECT p.*, (SELECT COUNT(*) FROM presencas s
                   WHERE s.mat = p.mat AND s.presente = 1) AS presencas
                   FROM participantes p WHERE p.ativo = 1 ORDER BY p.nome""")


app = FastAPI(title="Controle de Treinamentos SOS")
init_db()


def _estado_snapshot(c):
    return {
        "participantes": q(c, "SELECT * FROM participantes ORDER BY ativo DESC, nome"),
        "turmas": q(c, "SELECT * FROM turmas ORDER BY data_iso, id"),
        "vazio": False,
        "setor": "SOS Emergências Médicas",
    }


@app.get("/api/unidades")
def unidades():
    with db() as c:
        return [{"id": "default", "nome": "SOS Emergências Médicas", "dados": _estado_snapshot(c)}]


@app.post("/api/unidades")
def cria_unidade(item: dict):
    nome = str(item.get("nome", "")).strip() or "Nova unidade"
    clonar = bool(item.get("clonar", True))
    with db() as c:
        dados = _estado_snapshot(c) if clonar else {"participantes": [], "turmas": [], "vazio": True, "setor": nome}
        return {"id": "default", "nome": nome, "dados": dados}


# ---------- Dashboard (tudo calculado, nada fixo) ----------
@app.get("/api/dashboard")
def dashboard():
    with db() as c:
        ativos = ativos_com_presencas(c)
        pend = [p for p in ativos if p["presencas"] == 0]
        turmas = q(c, "SELECT * FROM turmas ORDER BY data_iso")
        ex = c.execute("SELECT COUNT(*) FROM participantes WHERE ativo = 0").fetchone()[0]
    status = {t["code"]: t["status"] for t in turmas}
    cargos: dict = {}
    for p in ativos:
        cargos[p["cargo"]] = cargos.get(p["cargo"], 0) + 1

    def feita(entrega):
        return all(status.get(x) == "Realizada" for x in entrega["turmaCode"].split("/"))

    meses: dict = {}
    for e in SEED["programa"]:
        m = meses.setdefault(e["periodo"], [0, 0])
        m[0 if feita(e) else 1] += 1
    hoje = date.today().isoformat()
    futuras = [t for t in turmas if t["status"] == "Agendada"]
    proxima = next((t for t in futuras if t["data_iso"] >= hoje), futuras[0] if futuras else None)
    entregas_ok = sum(v[0] for v in meses.values())
    return {
        "kpis": {"base": len(ativos), "treinados": len(ativos) - len(pend),
                 "pendentes": len(pend), "ex": ex, "prazo": PRAZO_FINAL},
        "pendentes": pend, "cargos": cargos, "proxima": proxima,
        "programa": {"meses": meses, "entregas_ok": entregas_ok,
                     "entregas": len(SEED["programa"]),
                     "turmas_ok": sum(t["status"] == "Realizada" for t in turmas),
                     "turmas": len(turmas)},
    }


# ---------- Participantes ----------
class NovoParticipante(BaseModel):
    nome: str
    mat: str
    cargo: str


class EditaParticipante(BaseModel):
    email: Optional[str] = None
    ativo: Optional[bool] = None


@app.get("/api/participantes")
def participantes():
    with db() as c:
        return q(c, """SELECT p.*, (SELECT COUNT(*) FROM presencas s
                       WHERE s.mat = p.mat AND s.presente = 1) AS presencas
                       FROM participantes p ORDER BY p.ativo DESC, p.nome""")


@app.post("/api/participantes", status_code=201)
def cria_participante(p: NovoParticipante):
    with db() as c:
        if c.execute("SELECT 1 FROM participantes WHERE mat = ?", (p.mat,)).fetchone():
            raise HTTPException(409, "Matrícula já cadastrada.")
        c.execute("INSERT INTO participantes(mat,nome,cargo) VALUES(?,?,?)",
                  (p.mat.strip(), p.nome.strip(), p.cargo))
    return {"ok": True}


@app.patch("/api/participantes/{mat}")
def edita_participante(mat: str, d: EditaParticipante):
    with db() as c:
        if d.email is not None:
            email = d.email.strip()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise HTTPException(422, "E-mail inválido.")
            c.execute("UPDATE participantes SET email = ? WHERE mat = ?", (email, mat))
        if d.ativo is not None:
            c.execute("UPDATE participantes SET ativo = ? WHERE mat = ?", (int(d.ativo), mat))
    return {"ok": True}


# ---------- Turmas e presença ----------
class Registro(BaseModel):
    mat: str
    presente: bool
    justificativa: str = ""


class Presenca(BaseModel):
    registros: list[Registro]


@app.get("/api/turmas")
def turmas():
    with db() as c:
        return q(c, """SELECT t.*, (SELECT COUNT(*) FROM presencas s
                       WHERE s.turma_id = t.id AND s.presente = 1) AS presentes
                       FROM turmas t ORDER BY t.data_iso, t.id""")


@app.get("/api/turmas/{tid}")
def turma(tid: int):
    with db() as c:
        t = q(c, "SELECT * FROM turmas WHERE id = ?", tid)
        if not t:
            raise HTTPException(404, "Turma não encontrada.")
        reg = {r["mat"]: r for r in q(c, "SELECT * FROM presencas WHERE turma_id = ?", tid)}
        lista = [{"mat": p["mat"], "nome": p["nome"], "cargo": p["cargo"],
                  "presente": (bool(reg[p["mat"]]["presente"]) if p["mat"] in reg else None),
                  "justificativa": reg.get(p["mat"], {}).get("justificativa", "")}
                 for p in ativos_com_presencas(c)]
    return {"turma": t[0], "participantes": lista}


@app.put("/api/turmas/{tid}/presenca")
def salva_presenca(tid: int, body: Presenca):
    for r in body.registros:
        if not r.presente and not r.justificativa.strip():
            raise HTTPException(422, f"Justificativa obrigatória para a ausência da matrícula {r.mat}.")
    with db() as c:
        c.execute("DELETE FROM presencas WHERE turma_id = ?", (tid,))
        c.executemany("INSERT INTO presencas VALUES(?,?,?,?)",
                      [(tid, r.mat, int(r.presente), r.justificativa.strip()) for r in body.registros])
        if any(r.presente for r in body.registros):
            c.execute("UPDATE turmas SET status = 'Realizada' WHERE id = ?", (tid,))
    return {"ok": True}


# ---------- Cobertura por tema (igualdade exata do tema, sem "contém") ----------
@app.get("/api/cobertura")
def cobertura():
    with db() as c:
        ativos = {p["mat"] for p in ativos_com_presencas(c)}
        linhas = q(c, """SELECT t.tema, s.mat FROM presencas s
                         JOIN turmas t ON t.id = s.turma_id WHERE s.presente = 1""")
    por_tema: dict = {}
    for r in linhas:
        por_tema.setdefault(r["tema"], set()).add(r["mat"])
    out = []
    for tema in SEED["topics"]:
        ok = len(por_tema.get(tema, set()) & ativos)
        out.append({"tema": tema, "treinados": ok, "pendentes": len(ativos) - ok,
                    "pct": round(100 * ok / len(ativos)) if ativos else 0})
    return sorted(out, key=lambda x: x["pct"])


@app.get("/api/relatorio")
def relatorio():
    with db() as c:
        ativos = ativos_com_presencas(c)
        pres = q(c, """SELECT t.code, s.mat FROM presencas s JOIN turmas t ON t.id = s.turma_id
                       WHERE s.presente = 1 ORDER BY t.data_iso, t.id""")
    de: dict = {}
    for r in pres:
        de.setdefault(r["mat"], []).append(r["code"])
    linhas = [{**p, "turmas": de.get(p["mat"], [])} for p in sorted(ativos, key=lambda p: (p["cargo"], p["nome"]))]
    return {"gerado": datetime.now().strftime("%d/%m/%Y %H:%M"), "prazo": PRAZO_FINAL, "base": len(linhas),
            "treinados": [l for l in linhas if l["presencas"] > 0],
            "nao_treinados": [l for l in linhas if l["presencas"] == 0]}


@app.get("/")
def index():
    html = (BASE / "static" / "index.html").read_text("utf-8")
    if (BASE / "static" / "plotly.min.js").exists():  # uso offline: biblioteca de gráficos local
        html = html.replace("https://cdn.plot.ly/plotly-2.35.2.min.js", "/static/plotly.min.js")
    return HTMLResponse(html)


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
