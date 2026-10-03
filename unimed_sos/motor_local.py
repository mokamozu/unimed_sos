"""Motor Python executado no navegador (PyScript/Pyodide). Sem servidor.
Mesmas regras do main.py; o estado fica no localStorage do navegador."""
import json
import re
from datetime import date, datetime

from pyodide.ffi import create_proxy
from pyscript import window

SEED = json.loads(window.document.getElementById("seed").textContent)
KEY = "SOS_TREINAMENTOS_V2"
PRAZO_FINAL = SEED["config"]["deadline"]


class Erro(Exception):
    pass


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "sim", "s"}
    return False


def data_iso(txt):
    if not txt or not isinstance(txt, str):
        return ""
    m = re.search(r"(\d{1,2})(?:-\d{1,2})?/(\d{2})/(\d{4})", txt)
    if not m:
        return ""
    return f"{m[3]}-{m[2]}-{int(m[1]):02d}"


def estado_inicial():
    turmas = []
    for t in SEED["turmas"]:
        reg = {m: {"presente": 1, "justificativa": ""} for m in t.get("presentes", [])}
        for m, j in (t.get("justificativas") or {}).items():
            reg.setdefault(m, {"presente": 0, "justificativa": j})
        turmas.append({"id": t["id"], "code": t["code"], "tema": t["tema"], "data_txt": t["data"],
                       "data_iso": data_iso(t["data"]), "instrutores": t["instrutores"],
                       "status": t["status"], "reg": reg})
    pessoas = [{"mat": p["mat"], "nome": p["nome"], "cargo": p["cargo"],
                "ativo": 0 if p.get("isEx") else 1, "email": ""} for p in SEED["participantes"]]
    return {"participantes": pessoas, "turmas": turmas}


def carrega():
    raw = window.localStorage.getItem(KEY)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return estado_inicial()


ST = carrega()
ST.setdefault("setor", "SOS Emergências Médicas")
ST.setdefault("vazio", False)
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]


def snapshot_estado():
    return {k: json.loads(json.dumps(v)) for k, v in ST.items() if k not in {"unidades", "unidade_atual"}}


def salva():
    window.localStorage.setItem(KEY, json.dumps(ST))


def prepara_unidades():
    if "unidades" not in ST or not isinstance(ST["unidades"], list):
        ST["unidades"] = [{"id": "default", "nome": ST.get("setor", "SOS Emergências Médicas"),
                            "dados": snapshot_estado()}]
        ST["unidade_atual"] = "default"
    atual = ST.get("unidade_atual")
    if atual is None:
        ST["unidade_atual"] = ST["unidades"][0]["id"]
    for u in ST["unidades"]:
        if u.get("id") == ST["unidade_atual"]:
            u["dados"] = snapshot_estado()
            break


def n_presencas(mat):
    return sum(1 for t in ST["turmas"] if t["reg"].get(mat, {}).get("presente") == 1)


def com_presencas(lista):
    return [{**p, "presencas": n_presencas(p["mat"])} for p in lista]


def ativos():
    return sorted(com_presencas([p for p in ST["participantes"] if p["ativo"]]), key=lambda p: p["nome"])


def turmas_ordenadas():
    return sorted(ST["turmas"], key=lambda t: (t["data_iso"], t["id"]))


def temas():
    """Dados originais: os 27 temas do programa. Base limpa: os temas das turmas cadastradas."""
    if not ST.get("vazio"):
        return SEED["topics"]
    vistos = []
    for t in turmas_ordenadas():
        if t["tema"] not in vistos:
            vistos.append(t["tema"])
    return vistos


def programa():
    if not ST.get("vazio"):
        return SEED["programa"]
    return [{"periodo": MESES[int(t["data_iso"][5:7]) - 1] if t["data_iso"] else "Sem data",
             "turmaCode": t["code"]} for t in turmas_ordenadas()]


def dashboard():
    at = ativos()
    pend = [p for p in at if p["presencas"] == 0]
    status = {t["code"]: t["status"] for t in ST["turmas"]}
    cargos = {}
    for p in at:
        cargos[p["cargo"]] = cargos.get(p["cargo"], 0) + 1
    meses = {}
    for e in programa():
        ok = all(status.get(c) == "Realizada" for c in e["turmaCode"].split("/"))
        meses.setdefault(e["periodo"], [0, 0])[0 if ok else 1] += 1
    fut = [t for t in turmas_ordenadas() if t["status"] == "Agendada"]
    hoje = date.today().isoformat()
    prox = next((t for t in fut if t["data_iso"] >= hoje), fut[0] if fut else None)
    return {"setor": ST["setor"], "kpis": {"base": len(at), "treinados": len(at) - len(pend), "pendentes": len(pend),
                     "ex": sum(1 for p in ST["participantes"] if not p["ativo"]), "prazo": PRAZO_FINAL},
            "pendentes": pend, "cargos": cargos, "proxima": prox,
            "programa": {"meses": meses, "entregas_ok": sum(v[0] for v in meses.values()),
                         "entregas": len(programa())}}


def cobertura():
    mats = {p["mat"] for p in ST["participantes"] if p["ativo"]}
    por_tema = {}
    for t in ST["turmas"]:
        for m, r in t["reg"].items():
            if r["presente"] == 1:
                por_tema.setdefault(t["tema"], set()).add(m)
    out = []
    for tema in temas():
        ok = len(por_tema.get(tema, set()) & mats)
        out.append({"tema": tema, "treinados": ok, "pendentes": len(mats) - ok,
                    "pct": round(100 * ok / len(mats)) if mats else 0})
    return sorted(out, key=lambda x: x["pct"])


def relatorio():
    turmas_de = {}
    for t in turmas_ordenadas():
        for mat, r in t["reg"].items():
            if r["presente"] == 1:
                turmas_de.setdefault(mat, []).append(t["code"])
    linhas = [{**p, "turmas": turmas_de.get(p["mat"], [])}
              for p in sorted(ativos(), key=lambda p: (p["cargo"], p["nome"]))]
    return {"setor": ST["setor"], "gerado": datetime.now().strftime("%d/%m/%Y %H:%M"), "prazo": PRAZO_FINAL, "base": len(linhas),
            "treinados": [l for l in linhas if l["presencas"] > 0],
            "nao_treinados": [l for l in linhas if l["presencas"] == 0]}


def acha_turma(tid):
    t = next((t for t in ST["turmas"] if t["id"] == tid), None)
    if not t:
        raise Erro("Turma não encontrada.")
    return t


def rota(m, path, b):
    b = {} if b is None else b
    if path == "/api/unidades" and m == "GET":
        prepara_unidades()
        return ST["unidades"]
    if path == "/api/unidades" and m == "POST":
        prepara_unidades()
        nome = str(b.get("nome", "")).strip() or "Nova unidade"
        clonar = bool(b.get("clonar", True))
        atual_id = ST.get("unidade_atual", "default")
        for unidade in ST["unidades"]:
            if unidade.get("id") == atual_id:
                unidade["dados"] = snapshot_estado()
                break
        novo_id = f"u{int(datetime.now().timestamp()*1000)}"
        unidades = ST["unidades"]
        novo_dados = snapshot_estado() if clonar else {"participantes": [], "turmas": [], "vazio": True, "setor": nome}
        novo = {"id": novo_id, "nome": nome, "dados": novo_dados}
        unidades.append(novo)
        ST.clear()
        ST.update({**novo_dados, "unidades": unidades, "unidade_atual": novo_id})
        salva()
        return {"id": novo_id, "nome": nome}
    if m == "GET" and path == "/api/dashboard":
        return dashboard()
    if m == "GET" and path == "/api/relatorio":
        return relatorio()
    if m == "GET" and path == "/api/cobertura":
        return cobertura()
    if m == "GET" and path == "/api/participantes":
        return sorted(com_presencas(ST["participantes"]), key=lambda p: (-p["ativo"], p["nome"]))
    if m == "POST" and path == "/api/participantes":
        mat = str(b.get("mat", "")).strip()
        nome = str(b.get("nome", "")).strip()
        cargo = str(b.get("cargo", "")).strip()
        if not mat or not nome or not cargo:
            raise Erro("Informe nome, matrícula e função.")
        if any(p["mat"] == mat for p in ST["participantes"]):
            raise Erro("Matrícula já cadastrada.")
        ST["participantes"].append({"mat": mat, "nome": nome, "cargo": cargo, "ativo": 1, "email": ""})
        salva()
        return {}
    g = re.fullmatch(r"/api/participantes/(.+)", path)
    if m == "PATCH" and g:
        p = next((p for p in ST["participantes"] if p["mat"] == g[1]), None)
        if not p:
            raise Erro("Participante não encontrado.")
        if b.get("email") is not None:
            e = str(b["email"]).strip()
            if e and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e):
                raise Erro("E-mail inválido.")
            p["email"] = e
        if b.get("ativo") is not None:
            p["ativo"] = 1 if _coerce_bool(b["ativo"]) else 0
        salva()
        return {}
    if m == "POST" and path == "/api/turmas":
        tema = str(b.get("tema", "")).strip()
        iso = str(b.get("data", "")).strip()
        if not tema:
            raise Erro("Informe o tema do treinamento.")
        if iso:
            try:
                date.fromisoformat(iso)
            except ValueError as exc:
                raise Erro("Data inválida. Use o formato AAAA-MM-DD.") from exc
        nid = max([t["id"] for t in ST["turmas"]], default=0) + 1
        ST["turmas"].append({"id": nid, "code": f"T{nid}", "tema": tema, "data_iso": iso,
                             "data_txt": f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "A definir",
                             "instrutores": str(b.get("instrutores", "")).strip() or "A definir",
                             "status": "Agendada", "reg": {}})
        salva()
        return {}
    if m == "POST" and path == "/api/limpar":
        setor = str(b.get("setor", "")).strip() or "Setor"
        ST.clear()
        ST.update({"participantes": [], "turmas": [], "vazio": True, "setor": setor})
        salva()
        return {}
    if m == "GET" and path == "/api/turmas":
        return [{k: v for k, v in t.items() if k != "reg"} |
                {"presentes": sum(1 for r in t["reg"].values() if r["presente"] == 1)}
                for t in turmas_ordenadas()]
    g = re.fullmatch(r"/api/turmas/(\d+)", path)
    if m == "GET" and g:
        t = acha_turma(int(g[1]))
        lista = [{"mat": p["mat"], "nome": p["nome"], "cargo": p["cargo"],
                  "presente": (bool(t["reg"][p["mat"]]["presente"]) if p["mat"] in t["reg"] else None),
                  "justificativa": t["reg"].get(p["mat"], {}).get("justificativa", "")} for p in ativos()]
        return {"turma": {k: v for k, v in t.items() if k != "reg"}, "participantes": lista}
    g = re.fullmatch(r"/api/turmas/(\d+)/presenca", path)
    if m == "PUT" and g:
        if not isinstance(b, dict) or "registros" not in b or not isinstance(b["registros"], list):
            raise Erro("Registros de presença ausentes.")
        t = acha_turma(int(g[1]))
        registros = []
        for r in b["registros"]:
            if not isinstance(r, dict):
                raise Erro("Registro de presença inválido.")
            mat = str(r.get("mat", "")).strip()
            if not mat:
                raise Erro("Matrícula ausente no registro de presença.")
            presente = _coerce_bool(r.get("presente"))
            justificativa = str(r.get("justificativa", "")).strip()
            if not presente and not justificativa:
                raise Erro(f"Justificativa obrigatória para a ausência da matrícula {mat}.")
            registros.append({"mat": mat, "presente": int(presente), "justificativa": justificativa})
        t["reg"] = {r["mat"]: {"presente": r["presente"], "justificativa": r["justificativa"]}
                    for r in registros}
        if any(r["presente"] for r in registros):
            t["status"] = "Realizada"
        salva()
        return {}
    raise Erro("Rota não encontrada.")


def handle(method, path, body):
    try:
        payload = json.loads(body) if body else {}
        return json.dumps({"ok": True, "data": rota(method, path, payload)})
    except Erro as e:
        return json.dumps({"ok": False, "detail": str(e)})
    except (TypeError, ValueError, KeyError) as exc:
        return json.dumps({"ok": False, "detail": f"Dados inválidos: {exc}"})
    except Exception as exc:  # pragma: no cover - fallback para interface do navegador
        return json.dumps({"ok": False, "detail": str(exc) or "Erro interno."})


try:
    window.pyHandle = create_proxy(handle)
    if hasattr(window, "__pyOk"):
        window.__pyOk()
except Exception:
    pass
