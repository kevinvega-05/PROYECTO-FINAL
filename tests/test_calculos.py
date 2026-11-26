import math

from monedas import calculos as C
from monedas import pista


def test_autonomia_coherente_con_la_formula():
    s = C.Supuestos()
    r = C.autonomia_carro(s)
    assert math.isclose(r["horas_moviendose"], s.bateria_mah * s.usable / (2 * s.motor_ma + s.logica_ma))
    assert r["horas_en_reposo"] > r["horas_moviendose"]
    assert r["viajes_por_carga"] > 100


def test_mas_bateria_mas_autonomia():
    a = C.autonomia_carro(C.Supuestos(bateria_mah=2000))["horas_moviendose"]
    b = C.autonomia_carro(C.Supuestos(bateria_mah=4000))["horas_moviendose"]
    assert math.isclose(b, 2 * a)


def test_tiempo_de_ruta_igual_al_de_pista():
    r = C.cinematica_carro(C.Supuestos())
    assert math.isclose(r["tiempo_ruta_s"], pista.simular_poses(pista.construir_ruta())[-1][0])
    assert 3000 < r["camino_mm"] < 4000


def test_el_par_critico_de_vision_se_resuelve():
    v = C.vision(C.Supuestos())
    assert v["separacion_sigmas"] > 4


def test_la_fuente_de_5v_alcanza_en_el_peor_caso():
    assert C.estacion_electrica(C.Supuestos())["margen_fuente_pct"] > 0


def test_cli_imprime(capsys):
    C.main([])
    assert "autonomia" in capsys.readouterr().out
