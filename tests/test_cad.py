"""El generador de CAD produce piezas imprimibles y consistentes con el firmware y la pista."""
import math
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "cad"))
trimesh = pytest.importorskip("trimesh")
pytest.importorskip("manifold3d")

import generar_cad as G  # noqa: E402
import parametros as P  # noqa: E402


@pytest.fixture(scope="module")
def piezas():
    return G.construir_todo()


def test_todas_las_piezas_son_hermeticas_y_caben_en_la_cama(piezas):
    imp, _ = piezas
    for n, m in imp.items():
        assert m.is_watertight, n
        assert m.volume > 0, n
        assert max(m.extents[:2]) <= P.LIMITE_CAMA, f"{n} {m.extents}"


def test_validacion_completa_sin_errores(piezas):
    err, _ = G.validar(*piezas)
    assert err == []


def test_angulos_de_servo_iguales_al_firmware():
    ino = (RAIZ / "firmware/estacion_esp32/estacion_esp32.ino").read_text(encoding="utf-8")
    fw = [int(x) for x in re.search(r"ANGULOS\[N_CUBICULOS\]\s*=\s*\{([^}]*)\}", ino).group(1).split(",")]
    assert tuple(fw) == P.ANGULOS_SERVO


def test_un_vaso_por_denominacion():
    from monedas import config as cfg
    assert len(P.ANGULOS_SERVO) == len(cfg.CUBICULO_DE_VALOR) == 5


def test_la_moneda_mayor_cabe_en_el_vaso_y_el_canal():
    from monedas.tipos import TIPOS
    d = max(t["diam_mm"] for t in TIPOS)
    assert P.VASO_DI >= d + 8 and P.CANAL_ANCHO >= d + 3


def test_la_oreja_encaja_con_el_pasador():
    assert P.OREJA_HUECO > P.PASADOR_D


def test_la_escena_tiene_los_nodos_que_usa_el_visor(piezas):
    sc = G.escena(*piezas)
    nodos = set(sc.graph.nodes_geometry)
    for n in ["carro", "canaleta", "banda", "pista"] + [f"vaso_{k}" for k in range(5)] + [f"termo_{i}" for i in (1, 2, 3)]:
        assert n in nodos, n
    visor = (RAIZ / "visor3d/src/visor.js").read_text(encoding="utf-8")
    for n in ("carro", "canaleta", "vaso_", "termo_"):
        assert n in visor


def test_termos_en_la_escena_coinciden_con_pista():
    pos = G.posiciones_termos()
    assert len(pos) == 3 and all(math.isfinite(v) for p in pos for v in p)


def test_dibujos_y_catalogo_generados():
    import os
    raiz = os.path.join(os.path.dirname(__file__), "..")
    for f in ("docs/img/cad_planta.png", "docs/img/cad_corte.png", "docs/piezas3d.html", "docs/img/cad/vaso.png"):
        assert os.path.getsize(os.path.join(raiz, f)) > 1000, f


def test_readme_explica_cada_pieza_con_su_imagen():
    import os
    raiz = os.path.join(os.path.dirname(__file__), "..")
    txt = open(os.path.join(raiz, "README.md"), encoding="utf-8").read()
    for img in ("vaso", "placa_portavasos_A", "torre_servo", "canaleta", "tolva_entrada",
                "soporte_sensor_ir", "soporte_celular", "enganche_carro"):
        assert f"docs/img/cad/{img}.png" in txt
