"""
demo.py - Video falso de una banda con monedas, para probar el sistema SIN camara ni hardware.
Dibuja monedas (plata y doradas, con los tamanos reales) que cruzan la imagen de izquierda a derecha.
Tiene la misma interfaz que vision_monedas.Camara: leer() y cerrar().
"""
import time

import cv2
import numpy as np

from monedas import vision as vm

PX_POR_MM = 5.0
ANCHO, ALTO = 960, 540
PLATA = (172, 172, 172)       # BGR
ORO = (40, 165, 212)

from monedas import clases as mc

mc.instalar()
# clave de clase -> (diametro mm, dorada), con las 9 clases (actual y antigua); 0 = moneda desconocida
MONEDAS_DEMO = {c: (i["mm"], i["dorada"]) for c, i in vm.MONEDAS.items()}
MONEDAS_DEMO[0] = (14.0, False)          # no coincide con ninguna: debe ir a la bandeja de rechazo
SECUENCIA = [100, 1000, 50, 500, mc.clave(200, True), 0, mc.clave(50, True), 500, 100, 1000]


def calibrar_clasificador(clasificador):
    """Carga la calibracion ideal (tamano y color nominales) sin tocar tu calibracion.json real."""
    for valor, info in vm.MONEDAS.items():
        clasificador.muestras[valor] = [[info["mm"] * PX_POR_MM, 1.0 if info["dorada"] else 0.0]]


class FuenteSintetica:
    def __init__(self, v_banda_mm_s, intervalo_s=3.5, secuencia=None, repetir=True):
        self.v_px = v_banda_mm_s * PX_POR_MM
        self.intervalo = intervalo_s
        self.secuencia = list(secuencia or SECUENCIA)
        self.repetir = repetir
        self.t0 = time.time()
        self.vacia = np.full((ALTO, ANCHO, 3), 245, np.uint8)
        self.rng = np.random.default_rng(1)

    def _monedas(self, t):
        out = []
        n = len(self.secuencia)
        i = 0
        while True:
            ts = i * self.intervalo + 0.5
            if ts > t:
                break
            if i >= n and not self.repetir:
                break
            valor = self.secuencia[i % n]
            mm, dorada = MONEDAS_DEMO[valor]
            r = mm * PX_POR_MM / 2
            x = -r + self.v_px * (t - ts)
            if x - r < ANCHO:
                y = ALTO // 2 + 30 * ((i % 3) - 1)
                out.append((x, y, r, dorada))
            i += 1
        return out

    def leer(self):
        t = time.time() - self.t0
        img = self.vacia.copy()
        for x, y, r, dorada in self._monedas(t):
            col = ORO if dorada else PLATA
            cv2.circle(img, (int(x), int(y)), int(r), col, -1, cv2.LINE_AA)
            cv2.circle(img, (int(x), int(y)), int(r), tuple(int(c * 0.7) for c in col), 2, cv2.LINE_AA)
        ruido = self.rng.normal(0, 2.0, img.shape)
        return np.clip(img.astype(np.float32) + ruido, 0, 255).astype(np.uint8)

    def cerrar(self):
        pass
