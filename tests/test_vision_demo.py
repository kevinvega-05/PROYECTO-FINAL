"""La vision clasifica y cuenta las monedas del video sintetico (sin camara ni hardware)."""
import argparse
import os

import pytest

from monedas import clases as mc
from monedas import config as cfg
from monedas import demo
from monedas import vision as vm
from monedas.estado import Estado
from monedas.hardware import EstacionSim
from monedas.sistema import Sistema


class PlanFalso:
    def __init__(self):
        self.vistas = []

    def agregar(self, clave):
        self.vistas.append(clave)


def _correr(secuencia, v_banda=100.0, fps=20.0):
    fuente = demo.FuenteSintetica(v_banda, intervalo_s=3.5, secuencia=secuencia, repetir=False)
    clasif = vm.Clasificador(ruta=os.path.join(cfg.DATOS, "cal_test.json"))
    demo.calibrar_clasificador(clasif)
    est = Estado()
    plan = PlanFalso()
    sis = Sistema(argparse.Namespace(), est, EstacionSim(est, silenciosa=True), plan, clasif)
    fuente.t0 = __import__("time").time()
    sis.fondo = vm.suavizar(vm.preparar(fuente.vacia))
    t_fin = 0.5 + 3.5 * len(secuencia) + 12.0 / v_banda * 10
    t = 0.0
    while t < t_fin:
        fuente.t0 = __import__("time").time() - t         # reloj virtual: sin esperar tiempo real
        sis.procesar(fuente.leer())
        t += 1.0 / fps
    return plan.vistas, sis


def test_clasifica_y_cuenta_cada_moneda_una_vez():
    secuencia = [100, 1000, 50, 500, 0]
    vistas, sis = _correr(secuencia)
    esperado = [100, 1000, 50, 500, None]
    assert vistas == esperado
    assert sis.vm_estado["total"] == 100 + 1000 + 50 + 500
    assert sis.vm_estado["conteo"]["?"] == 1


def test_distingue_moneda_antigua_de_la_actual():
    secuencia = [mc.clave(200, True), 200, mc.clave(50, True)]
    vistas, _ = _correr(secuencia)
    assert [mc.valor_de(c) for c in vistas] == [200, 200, 50]


@pytest.mark.parametrize("valor", [50, 100, 200, 500, 1000])
def test_cada_denominacion_va_a_su_vaso(valor):
    vistas, _ = _correr([valor])
    assert [cfg.cubiculo_de_valor(mc.valor_de(c)) for c in vistas] == [cfg.CUBICULO_DE_VALOR[valor]]
