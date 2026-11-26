from monedas import config as cfg
from monedas.hardware import duracion_ruta_s, partir_ruta


def test_partir_ruta_formato():
    lineas = partir_ruta("F1000,L40,F403,R125,B800")
    assert lineas[0] == "C" and lineas[-1] == "E"
    assert all(l.startswith("A") for l in lineas[1:-1])


def test_partir_ruta_respeta_el_largo_maximo():
    ruta = ",".join(["F1000", "L40"] * 40)
    lineas = partir_ruta(ruta)
    assert all(len(l) <= cfg.CARRO_PEDAZO_MAX for l in lineas[1:-1])
    assert ",".join(l[1:] for l in lineas[1:-1]) == ruta


def test_duracion():
    assert duracion_ruta_s("F1000,L500,S250") == 1.75
    assert duracion_ruta_s("") == 0
