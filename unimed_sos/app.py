"""Abre o sistema como programa de desktop: servidor interno + janela própria."""
import socket
import threading
import time
import urllib.request

import uvicorn
import webview

from main import app


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    porta = porta_livre()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=porta, log_config=None,
                         loop="asyncio", http="h11", lifespan="off")
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    url = f"http://127.0.0.1:{porta}"
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/dashboard", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    webview.create_window("Controle de Treinamentos - SOS Emergências Médicas", url,
                          width=1360, height=860, min_size=(1000, 650))
    webview.start()
    srv.should_exit = True


if __name__ == "__main__":
    main()
