"""capturar.py - Saca capturas PNG del visor 3D con Chromium sin cabeza (para el README).

    python visor3d/capturar.py            # escribe docs/img/hero.png, estacion.png, pista.png
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HTML = os.path.abspath(os.path.join(RAIZ, "docs", "visor3d.html"))
OUT = os.path.join(RAIZ, "docs", "img")


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1500, "height": 860}, device_scale_factor=1.5)
        errores = []
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pg.goto("file://" + HTML)
        pg.wait_for_function("window.__visor !== undefined", timeout=60000)
        time.sleep(1.0)
        def foto(nombre, vista, t=0.0, vaso=3, extra=None):
            pg.evaluate(f"window.__visor.elegirVaso({vaso})")
            pg.evaluate(f"window.__visor.vista('{vista}')")
            pg.evaluate(f"window.__visor.ponerT({t})")
            if extra:
                pg.evaluate(extra)
            time.sleep(0.6)
            pg.screenshot(path=os.path.join(OUT, nombre))
            print("ok", nombre)
        foto("visor_general.png", "general", t=9.0)
        foto("visor_estacion.png", "estacion", t=0.0, vaso=1)
        foto("visor_pista.png", "pista", t=13.0)
        b.close()
        if errores:
            print("ERRORES JS:", *errores[:5], sep="\n  ")
            sys.exit(1)


if __name__ == "__main__":
    main()
