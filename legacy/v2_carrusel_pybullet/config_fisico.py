"""
config_fisico.py - Medidas REALES (mm) de la banda y de los cubículos de clasificación.

Es la única fuente de verdad para:
  - cad/generar_cubiculos.py  (planos DXF y piezas STL)
  - tests/test_cubiculos_reales.py  (prueba en PyBullet: cada moneda a su cubículo)

Origen de coordenadas: extremo de salida de la banda, x hacia afuera de la banda
(hacia el carrusel), y hacia el lado, z hacia arriba desde la mesa.

OJO: las medidas de la banda las tomó el autor; las de los cubículos son DISEÑO
(se calculan aquí) y las monedas son valores de REFERENCIA (mide las tuyas y corrige TIPOS).
"""
import math
from config import TIPOS, N_TIPOS

# ------------------------------------------------------------------ banda real (medida)
BANDA_ANCHO = 160.0            # ancho de la estructura
BANDA_Z = 80.0                 # altura de la superficie sobre la mesa
BANDA_LARGO = 660.0            # 3 módulos de 220 (supuesto)
V_BANDA = 150.0                # mm/s  (ajústala a la velocidad real de tu motor)

# ------------------------------------------------------------------ cubículos (vasos)
# Un vaso cilíndrico por tipo de moneda: la moneda más grande ($1000 = 26 mm) cabe con holgura
# y las monedas se apilan casi planas. Son piezas SEPARADAS del disco para que el carro
# pueda engancharlos como remolque.
D_MAX_MONEDA = max(t["diam_mm"] for t in TIPOS)
VASO_DI = 36.0                 # diámetro interior (>= D_MAX_MONEDA + 8)
VASO_PARED = 3.0
VASO_DE = VASO_DI + 2 * VASO_PARED       # 42 mm exterior
VASO_H = 55.0                  # alto total (cabe ~20 monedas de 2,5 mm apiladas)
VASO_FONDO = 3.0               # espesor del fondo

# ------------------------------------------------------------------ disco portavasos
HOLGURA_SOCKET = 0.6           # holgura radial vaso/alojamiento
SOCKET_D = VASO_DE + 2 * HOLGURA_SOCKET  # alojamiento donde asienta cada vaso
SOCKET_PROF = 4.0
SEPARACION_VASOS = 2.0         # espacio libre entre vasos contiguos
# radio al centro de los vasos: 9 vasos separados (VASO_DE + SEPARACION) entre centros contiguos
RADIO_VASOS = (VASO_DE + SEPARACION_VASOS) / (2 * math.sin(math.pi / N_TIPOS))
DISCO_RADIO = RADIO_VASOS + SOCKET_D / 2 + 5.0
DISCO_ESP = 8.0
CAIDA = 12.0                   # caída libre entre la banda y el borde del vaso
VASO_TOPE_Z = BANDA_Z - CAIDA            # borde superior del vaso en la estación de llenado
DISCO_TOPE_Z = VASO_TOPE_Z - VASO_H + SOCKET_PROF   # cara superior del disco
DISCO_BASE_Z = DISCO_TOPE_Z - DISCO_ESP

# Posición del eje del carrusel respecto al extremo de la banda:
# el vaso de la estación de llenado queda centrado a (VASO_DI/2 + 5) mm del borde de la banda.
DIST_BORDE_A_VASO = VASO_DI / 2 + 5.0
EJE_X = DIST_BORDE_A_VASO + RADIO_VASOS
EJE_Y = 0.0

# ------------------------------------------------------------------ indexado
PASO_GRADOS = 360.0 / N_TIPOS            # 40° por tipo
# Vaso k de la lista TIPOS está a k*PASO_GRADOS (marco del disco).
# Para llenarlo se gira el disco hasta que ese vaso quede en el ángulo 180° (mirando a la banda).


def angulo_vaso_local(k):
    return math.radians(k * PASO_GRADOS)


def yaw_disco_para_llenar(k):
    """Yaw del disco (rad) para que el vaso k quede en la estación de llenado (ángulo mundo = pi)."""
    return math.pi - angulo_vaso_local(k)


def pos_vaso(k, yaw=0.0):
    """Centro (x, y) del vaso k con el disco girado `yaw`, en el marco de la banda."""
    a = angulo_vaso_local(k) + yaw
    return (EJE_X + RADIO_VASOS * math.cos(a), EJE_Y + RADIO_VASOS * math.sin(a))


if __name__ == "__main__":
    print(f"Moneda mayor: {D_MAX_MONEDA} mm | vaso {VASO_DI}/{VASO_DE} mm x {VASO_H} mm")
    print(f"Radio de vasos {RADIO_VASOS:.1f} mm | disco R {DISCO_RADIO:.1f} mm (D {2*DISCO_RADIO:.0f})")
    print(f"Borde del vaso z={VASO_TOPE_Z:.0f} | cara del disco z={DISCO_TOPE_Z:.0f} | base z={DISCO_BASE_Z:.0f}")
    print(f"Eje del carrusel a {EJE_X:.1f} mm del borde de la banda")
    for k, t in enumerate(TIPOS):
        x, y = pos_vaso(k, yaw_disco_para_llenar(0))
        print(f"  vaso {k} -> {t['id']:12s} ({t['diam_mm']:.1f} mm)")

# Eje del motor (28BYJ-48 o NEMA17: eje de 5 mm). Cubo central del disco.
EJE_D = 5.2
CUBO_R = 10.0
CUBO_H = 10.0
