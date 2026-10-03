"""Gera controle_treinamentos.html: arquivo unico, sem servidor (abre com duplo clique)."""
import re
from pathlib import Path
B = Path(__file__).parent
html = (B / "static" / "index.html").read_text("utf-8")
api_novo = ("const pyReady=new Promise(r=>window.__pyOk=r);\n"
  "const api=async(u,o={})=>{await pyReady;const r=JSON.parse(window.pyHandle(o.m||'GET',u,o.b?JSON.stringify(o.b):''));"
  "if(!r.ok)throw new Error(r.detail);return r.data};\npyReady.then(()=>$('#boot').remove());")
html, n = re.subn(r"const api=async.*?return r\.json\(\)\};", lambda m: api_novo, html, flags=re.S)
assert n == 1, "funcao api nao encontrada"
css = "#boot{position:fixed;inset:0;z-index:20;display:grid;place-items:center;background:rgba(241,250,245,.85);backdrop-filter:blur(8px);color:#00563a;font-weight:600}#boot i{display:block;width:34px;height:34px;margin:0 auto 12px;border-radius:50%;border:3px solid rgba(0,153,93,.2);border-top-color:#00995d;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}"
html = html.replace("</style>", css + "\n</style>", 1)
html = html.replace("</head>", '<script type="module" src="https://pyscript.net/releases/2024.11.1/core.js"></script>\n</head>', 1)
seed = (B / "seed.json").read_text("utf-8")
py = (B / "motor_local.py").read_text("utf-8")
bloco = ('<div id="boot"><div style="text-align:center"><i></i>Carregando motor Python...</div></div>\n'
         f'<script id="seed" type="application/json">{seed}</script>\n<script type="py">\n{py}\n</script>\n')
html = html.replace("<script>\nconst $=", bloco + "<script>\nconst $=", 1)
(B / "controle_treinamentos.html").write_text(html, "utf-8")
print("ok", len(html) // 1024, "KB")
