import math
import re

import pytest

from monedas import pista as p


def test_ruta_usa_solo_tokens_validos():
    ruta = p.construir_ruta()
    assert ruta
    for c, ms in ruta:
        assert c in "FBLRS" and isinstance(ms, int) and 0 < ms <= 8000
    assert re.fullmatch(r"[FBLRS]\d+(,[FBLRS]\d+)*", p.a_texto(ruta))


def test_la_ruta_cabe_en_el_firmware():
    assert len(p.construir_ruta()) <= p.MAX_TRAMOS_FIRMWARE


def test_la_ruta_termina_en_la_meta():
    ruta = p.construir_ruta()
    pts, rumbo = p.simular(ruta)
    xi, xc, xd, y_sup, y_inf, y_meta = p.geometria()
    assert math.hypot(pts[-1][0] - xd, pts[-1][1] - y_meta) < 40
    assert abs(rumbo) < 5                        # termina mirando hacia adelante


def test_la_trayectoria_no_se_sale_de_la_pista_en_los_rectos():
    pts, _ = p.simular(p.construir_ruta())
    xi, xc, xd, y_sup, y_inf, y_meta = p.geometria()
    for x, y in pts:
        # en el tramo izquierdo (antes de empezar el retorno) el carro no se aleja mas de medio carril
        if y < y_sup - 1 and x < xi + p.ANCHO_CARRIL and abs(x - xi) > 0:
            assert abs(x - xi) <= p.ANCHO_CARRIL / 2


def test_pedazos_para_bluetooth():
    lineas = p.en_pedazos(p.construir_ruta())
    assert lineas[0] == "C" and lineas[-1] == "E"
    for l in lineas[1:-1]:
        assert l.startswith("A") and len(l) <= p.PEDAZO_MAX
    reunido = ",".join(l[1:] for l in lineas[1:-1])
    assert reunido == p.a_texto(p.construir_ruta())


def test_avance_controlado_alterna_recto_y_correccion():
    toks = p.avance(1000.0)
    assert toks[0] == ("F", p.PASO_RECTO_MS) and toks[1] == ("L", p.CORRECCION_IZQ_MS)
    assert p.avance(0) == []


def test_retorno_gira_180_grados():
    for giro in ("R", "L"):
        toks = p.retorno(giro, p.SEPARACION_IZQ_CEN)
        total = sum(p.ms_giro(0) + ms for c, ms in toks if c == giro)
        assert total == pytest.approx(p.T_GIRO90 * 2, rel=0.03)


def test_verificar_detecta_obstaculo_que_no_cabe(monkeypatch):
    monkeypatch.setattr(p, "OBSTACULOS", [(2, 600.0, "izq")])
    avisos = p.verificar()
    assert any("DESPUES del final del tramo" in a for a in avisos)


def test_poses_para_animacion():
    poses = p.simular_poses(p.construir_ruta())
    assert poses[0] == (0.0, 0.0, 0.0, 0.0)
    ts = [t for t, *_ in poses]
    assert ts == sorted(ts)
    assert ts[-1] == pytest.approx(sum(ms for _, ms in p.construir_ruta()) / 1000, rel=1e-6)


def test_cli_escribe_ordenes(tmp_path):
    assert p.cli(["--salida", str(tmp_path), "--sin-dibujo"]) == 0
    assert (tmp_path / "pista_ordenes.txt").read_text().startswith("C\n")
