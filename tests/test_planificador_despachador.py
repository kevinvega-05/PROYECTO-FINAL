"""Planificador (servo justo a tiempo) y Despachador (ordenes de comando.json) con hardware simulado."""
import json
import time

import pytest

from monedas import clases as mc
from monedas import config as cfg
from monedas.estado import Estado
from monedas.hardware import CarroSim, EstacionSim
from monedas.planificador import Despachador, Planificador


@pytest.fixture
def rapido(monkeypatch):
    monkeypatch.setattr(cfg, "TIEMPO_SERVO_S", 0.05)
    monkeypatch.setattr(cfg, "TIEMPO_CAIDA_S", 0.05)
    monkeypatch.setattr(cfg, "SERVO_INMEDIATO", True)


def _esperar(cond, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_el_servo_va_al_vaso_de_cada_moneda(rapido):
    est = Estado()
    est.estacion_ok = True
    estacion = EstacionSim(est, silenciosa=True)
    plan = Planificador(estacion, est, v_banda_mm_s=100.0)
    plan.start()
    try:
        for clave in (100, 1000, mc.clave(500, True), None, 50):
            plan.agregar(clave)
        assert _esperar(lambda: est.total + est.rechazadas == 5)
    finally:
        plan.activo = False
    ordenes = [c for _, c in estacion.ordenes]
    assert ordenes == ["C 1", "C 4", "C 3", f"G {cfg.ANGULO_RECHAZO}", "C 0"]
    assert est.cantidad_vaso(500) == 1 and est.cantidad_vaso(100) == 1 and est.rechazadas == 1
    assert est.valor == 100 + 1000 + 500 + 50


def test_modo_sincronizado_espera_a_que_la_moneda_llegue(monkeypatch):
    monkeypatch.setattr(cfg, "SERVO_INMEDIATO", False)
    monkeypatch.setattr(cfg, "DIST_LINEA_A_BORDE_MM", 100.0)
    monkeypatch.setattr(cfg, "TIEMPO_SERVO_S", 0.05)
    monkeypatch.setattr(cfg, "TIEMPO_CAIDA_S", 0.05)
    est = Estado()
    estacion = EstacionSim(est, silenciosa=True)
    plan = Planificador(estacion, est, v_banda_mm_s=100.0)       # llega en 1 s
    plan.start()
    t0 = time.time()
    try:
        plan.agregar(200)
        assert _esperar(lambda: est.total == 1, timeout=4)
    finally:
        plan.activo = False
    assert time.time() - t0 >= 0.95                              # no cuenta antes de que llegue


def _despachar(est, tipo, timeout=8):
    carro = CarroSim(est, aceleracion=5000.0)
    d = Despachador(carro, est)
    d.start()
    with open(cfg.COMANDO_PATH, "w", encoding="utf-8") as fh:
        json.dump({"accion": "despachar", "tipo": tipo, "atendido": False}, fh)
    ok = _esperar(lambda: est.carro["estado"] == "meta", timeout)
    d.activo = False
    return ok, carro


def test_despacho_completo_con_el_carro_simulado():
    est = Estado()
    est.moneda_llego(500, 3)
    ok, carro = _despachar(est, "500_actual")
    assert ok
    assert est.instantanea()["vasos"]["500"]["despachado"] is True
    assert len(carro.ordenes) == 2                               # enganche + pista
    assert carro.ordenes[0] == cfg.RUTA_ENGANCHE[3]
    with open(cfg.COMANDO_PATH, encoding="utf-8") as fh:
        assert json.load(fh)["atendido"] is True


def test_cualquier_id_del_vaso_despacha_el_mismo_vaso():
    est = Estado()
    est.moneda_llego(mc.clave(200, True), 2)
    ok, carro = _despachar(est, "200_actual")                    # la moneda era antigua, el vaso es el mismo
    assert ok and carro.ordenes[0] == cfg.RUTA_ENGANCHE[2]


def test_no_despacha_un_vaso_vacio():
    est = Estado()
    carro = CarroSim(est, aceleracion=5000.0)
    d = Despachador(carro, est)
    d.despachar("100_actual")
    assert carro.ordenes == [] and est.carro["estado"] == "en reposo"
    assert "vacio" in est.ultimo_evento


def test_tipo_desconocido_se_ignora():
    est = Estado()
    d = Despachador(CarroSim(est), est)
    d.despachar("10000_actual")
    assert "No hay un vaso" in est.ultimo_evento


def test_sin_carro_conectado_no_despacha():
    est = Estado()
    est.moneda_llego(100, 1)
    d = Despachador(None, est)
    d.despachar("100_actual")
    assert "no esta conectado" in est.ultimo_evento
