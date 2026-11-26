"""
construir.py - Empaqueta el visor 3D en UN solo archivo HTML (docs/visor3d.html) que se abre con doble clic.

    python visor3d/construir.py

Requiere Node.js. Usa cad/escena.glb (generala antes con cad/generar_cad.py) y las poses de monedas.pista.
"""
import base64
import json
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..")
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "cad"))

from monedas import pista  # noqa: E402
import parametros as P  # noqa: E402


def construir_piezas(datos_info=None):
    """Catalogo interactivo de las piezas imprimibles -> docs/piezas3d.html"""
    import generar_cad as G
    glb = os.path.join(RAIZ, "cad", "piezas.glb")
    imp, _ = G.construir_todo()
    info = G.info_piezas(imp)
    colores = {k: list(v) for k, v in G.COLORES_PIEZA.items()}
    subprocess.check_call([os.path.join(AQUI, "node_modules", ".bin", "esbuild"), "src/piezas.js", "--bundle",
                           "--minify", "--format=iife", f"--outfile={os.path.join(AQUI, 'bundle_piezas.js')}"], cwd=AQUI)
    datos = {"glb": base64.b64encode(open(glb, "rb").read()).decode(), "piezas": info, "colores": colores}
    html = open(os.path.join(AQUI, "plantilla_piezas.html"), encoding="utf-8").read()
    html = html.replace("/*DATOS*/", json.dumps(datos, separators=(",", ":")))
    html = html.replace("/*BUNDLE*/", open(os.path.join(AQUI, "bundle_piezas.js"), encoding="utf-8").read().replace("</script", "<\\/script"))
    with open(os.path.join(RAIZ, "docs", "piezas3d.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    os.remove(os.path.join(AQUI, "bundle_piezas.js"))


def main():
    glb = os.path.join(RAIZ, "cad", "escena.glb")
    if not os.path.exists(glb):
        sys.exit("Falta cad/escena.glb: ejecuta primero  python cad/generar_cad.py")
    npm = shutil.which("npm")
    if not npm:
        sys.exit("Se necesita Node.js (npm) para empaquetar el visor.")
    if not os.path.isdir(os.path.join(AQUI, "node_modules", "three")):
        subprocess.check_call([npm, "install", "--no-audit", "--no-fund"], cwd=AQUI)
    out_js = os.path.join(AQUI, "bundle.js")
    subprocess.check_call([os.path.join(AQUI, "node_modules", ".bin", "esbuild"), "src/visor.js", "--bundle",
                           "--minify", "--format=iife", f"--outfile={out_js}"], cwd=AQUI)
    ruta = pista.construir_ruta()
    poses = [[round(a, 3), round(b, 1), round(c, 1), round(d, 2)] for a, b, c, d in pista.simular_poses(ruta)]
    datos = {
        "glb": base64.b64encode(open(glb, "rb").read()).decode(),
        "poses": poses,
        "pista_x0": P.PISTA_X0,
        "pivote_x": P.PIVOTE_X, "pivote_z": P.PIVOTE_Z, "banda_alto": P.BANDA_ALTO,
        "angulos": list(P.ANGULOS_SERVO), "punta_r": P.PUNTA_R, "pendiente": P.PENDIENTE_GRADOS,
        "placa": P.PLACA_ESP, "vaso_fondo": P.VASO_FONDO, "vaso_de": P.VASO_DE, "carro_largo": P.CARRO_LARGO,
        "atras": P.CARRO_LARGO / 2 + 14.0 + (P.VASO_DE / 2 + P.OREJA_L - P.OREJA_ANCHO / 2),   # el agujero de la oreja queda sobre el pasador
    }
    html = open(os.path.join(AQUI, "plantilla.html"), encoding="utf-8").read()
    html = html.replace("/*DATOS*/", json.dumps(datos, separators=(",", ":")))
    html = html.replace("/*BUNDLE*/", open(out_js, encoding="utf-8").read().replace("</script", "<\\/script"))
    destino = os.path.join(RAIZ, "docs", "visor3d.html")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(html)
    construir_piezas(datos_info=None)
    os.remove(out_js)
    print(f"OK -> docs/visor3d.html  ({os.path.getsize(destino) / 1e6:.1f} MB, ruta de {len(ruta)} tramos, {poses[-1][0]:.1f} s)")


if __name__ == "__main__":
    main()
