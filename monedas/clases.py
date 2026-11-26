"""
clases.py - Las 5 denominaciones fisicas (50, 100, 200, 500, 1000), cada una con version ACTUAL y ANTIGUA.

Para la camara cada version es una "clase" distinta (tienen tamano/color diferente) pero las dos van al MISMO vaso.
Una clase se identifica con una clave entera:
    actual   -> el valor mismo           (50, 100, 200, 500, 1000)
    antigua  -> OFFSET_ANTIGUA + valor   (10000050, 10000100, ...)
instalar() reemplaza vision.MONEDAS por las 9 clases de tipos.py (sin modificar vision.py) y
hace que vision.pesos() muestre "$500 ant" para las antiguas.
"""
from monedas import vision as vm
from monedas.tipos import TIPOS

OFFSET_ANTIGUA = 10_000_000
from monedas.tipos import DENOMINACIONES  # noqa: E402,F401  (orden de los vasos 0..4)

# Color de dibujo (BGR) por denominacion
_COLOR = {50: (255, 170, 0), 100: (0, 200, 255), 200: (230, 60, 230), 500: (0, 140, 255), 1000: (0, 210, 0)}
# Las monedas ACTUALES con centro dorado (bimetalicas); las antiguas se estiman plateadas. Se corrige calibrando.
_DORADA_ACTUAL = {50: False, 100: True, 200: False, 500: True, 1000: True}
# Diametros que ya traia vision.py para las actuales
_MM_VISION = {50: 17.0, 100: 20.3, 200: 22.4, 1000: 26.7}

_pesos_original = vm.pesos  # formato colombiano original


def clave(valor, antigua=False):
    return valor + (OFFSET_ANTIGUA if antigua else 0)


def valor_de(c):
    return None if c is None else c % OFFSET_ANTIGUA


def es_antigua(c):
    return c is not None and c >= OFFSET_ANTIGUA


def tipo_id(c):
    return f"{valor_de(c)}_{'antigua' if es_antigua(c) else 'actual'}"


def pesos(c):
    if isinstance(c, (int,)) and c >= OFFSET_ANTIGUA:
        return _pesos_original(c - OFFSET_ANTIGUA) + " ant"
    return _pesos_original(c)


def _oscurecer(color):
    return tuple(int(x * 0.6) for x in color)


def instalar():
    """Deja vision_monedas listo para las 9 clases. Se puede llamar varias veces."""
    nuevas = {}
    for t in TIPOS:
        antigua = t["id"].endswith("_antigua")
        v = t["valor"]
        mm = t["diam_mm"] if antigua else _MM_VISION.get(v, t["diam_mm"])
        nuevas[clave(v, antigua)] = {
            "mm": mm,
            "dorada": False if antigua else _DORADA_ACTUAL[v],
            "color": _oscurecer(_COLOR[v]) if antigua else _COLOR[v],
            "tecla": "",
        }
    orden = sorted(nuevas, key=lambda c: (valor_de(c), es_antigua(c)))
    vm.MONEDAS.clear()
    for c in orden:
        vm.MONEDAS[c] = nuevas[c]
    vm.pesos = pesos


def pares_confundibles(tol=None):
    """Pares de clases de DISTINTO vaso con tamano parecido (dificiles de separar con la camara)."""
    tol = tol or vm.TOL_TAMANO
    cl = list(vm.MONEDAS)
    malos = []
    for i, a in enumerate(cl):
        for b in cl[i + 1:]:
            if valor_de(a) == valor_de(b):
                continue
            ma, mb = vm.MONEDAS[a], vm.MONEDAS[b]
            dif = abs(ma["mm"] - mb["mm"]) / min(ma["mm"], mb["mm"])
            if dif <= tol:
                malos.append((a, b, dif, ma["dorada"] == mb["dorada"]))
    return malos
