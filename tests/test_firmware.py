"""Revisiones estaticas: los firmware y el software deben estar de acuerdo (sin compilar)."""
import re
from pathlib import Path

from monedas import config as cfg
from monedas import pista

RAIZ = Path(__file__).resolve().parents[1]
CARRO = (RAIZ / "firmware/carro_monedas/carro_monedas.ino").read_text(encoding="utf-8")
ESTACION = (RAIZ / "firmware/estacion_esp32/estacion_esp32.ino").read_text(encoding="utf-8")
PANEL = (RAIZ / "herramientas/panel_carro.html").read_text(encoding="utf-8")


def test_max_tramos_igual_en_firmware_panel_y_pista():
    fw = int(re.search(r"const byte MAX_TRAMOS\s*=\s*(\d+);", CARRO).group(1))
    panel = int(re.search(r"const MAX_TRAMOS\s*=\s*(\d+)", PANEL).group(1))
    assert fw == panel == pista.MAX_TRAMOS_FIRMWARE


def test_la_estacion_tiene_5_angulos_de_servo_ordenados():
    m = re.search(r"int ANGULOS\[N_CUBICULOS\]\s*=\s*\{([^}]*)\}", ESTACION)
    angulos = [int(x) for x in m.group(1).split(",")]
    assert len(angulos) == 5 == len(cfg.CUBICULO_DE_VALOR)
    assert angulos == sorted(angulos) and all(0 <= a <= 180 for a in angulos)


def test_ambos_lados_hablan_a_la_misma_velocidad_serie():
    assert str(cfg.ESTACION_BAUDIOS) in ESTACION


def test_el_firmware_acepta_los_tokens_que_genera_pista():
    assert "c != 'F' && c != 'B' && c != 'L' && c != 'R' && c != 'S'" in CARRO
    usados = {c for c, _ in pista.construir_ruta()}
    assert usados <= set("FBLRS")


def test_el_firmware_de_la_estacion_acepta_los_comandos_que_envia_el_programa():
    for cmd in ("case 'B'", "case 'C'", "case 'G'"):
        assert cmd in ESTACION


def test_los_ino_estan_en_carpeta_con_su_mismo_nombre():
    for ino in (RAIZ / "firmware").rglob("*.ino"):
        assert ino.parent.name == ino.stem, f"{ino}: la carpeta debe llamarse igual que el .ino (Arduino IDE)"
