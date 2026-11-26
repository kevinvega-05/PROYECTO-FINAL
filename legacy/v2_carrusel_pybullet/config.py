"""
config.py - Parámetros del sistema logístico de monedas (rediseño v2).

Flujo físico:
    entrada -> banda RECTA -> sensor de presencia + cámara (identifica denominación)
    -> carrusel de 9 cubículos (uno por tipo de moneda) -> el carro se engancha
    como remolque al cubículo que se despache -> recorrido por la pista con obstáculos.

El despacho (acople + salida del carro) lo ordena el chatbot (ver chatbot.py).

Unidades: metros, kilogramos, segundos, radianes.
Si algo cambia aquí, vuelve a correr:  python generar_urdf.py
"""
import math

# ------------------------------------------------------------------ física
DT = 1.0 / 240.0

# ------------------------------------------------------------------ tipos de moneda (9 cubículos)
# id, valor (COP), diámetro (mm), masa (g). Antigua/actual comparten tamaño físico real
# (la cámara las distingue por el diseño acuñado, no por el tamaño) salvo el $500,
# donde la versión "actual" es bimetálica y más grande que la antigua monometálica.
# OJO: son valores de REFERENCIA. Mide tus monedas reales y corrige aquí.
TIPOS = [
    {"id": "50_antigua",  "valor": 50,   "diam_mm": 17.0, "masa_g": 3.0, "color": (0.75, 0.75, 0.78, 1)},
    {"id": "50_actual",   "valor": 50,   "diam_mm": 17.0, "masa_g": 3.0, "color": (0.80, 0.62, 0.35, 1)},
    {"id": "100_antigua", "valor": 100,  "diam_mm": 20.5, "masa_g": 5.0, "color": (0.72, 0.72, 0.75, 1)},
    {"id": "100_actual",  "valor": 100,  "diam_mm": 20.5, "masa_g": 5.0, "color": (0.78, 0.60, 0.32, 1)},
    {"id": "200_antigua", "valor": 200,  "diam_mm": 22.5, "masa_g": 6.0, "color": (0.70, 0.70, 0.73, 1)},
    {"id": "200_actual",  "valor": 200,  "diam_mm": 22.5, "masa_g": 6.0, "color": (0.85, 0.75, 0.30, 1)},
    {"id": "500_antigua", "valor": 500,  "diam_mm": 21.0, "masa_g": 4.5, "color": (0.68, 0.68, 0.72, 1)},
    {"id": "500_actual",  "valor": 500,  "diam_mm": 23.7, "masa_g": 7.3, "color": (0.90, 0.78, 0.25, 1)},
    {"id": "1000_actual", "valor": 1000, "diam_mm": 26.0, "masa_g": 7.6, "color": (0.95, 0.80, 0.20, 1)},
]
N_TIPOS = len(TIPOS)                    # 9
TIPO_INDEX = {t["id"]: i for i, t in enumerate(TIPOS)}
MONEDA_ESPESOR = 0.0025

# Precisión simulada de la identificación por cámara (1.0 = siempre acierta).
# Bájala (p. ej. 0.9) para ver cómo se comporta el sistema con clasificación imperfecta.
CAMARA_PRECISION = 1.0

def coin_radius(idx):
    return TIPOS[idx]["diam_mm"] / 2000.0

def coin_mass(idx):
    return TIPOS[idx]["masa_g"] / 1000.0

# ------------------------------------------------------------------ banda (recta)
BANDA_H = 0.20                 # altura de la superficie
BANDA_ANCHO = 0.12
BANDA_LARGO = 1.00             # de x=0 (entrada) a x=BANDA_LARGO (estación de llenado)
S_SENSOR = 0.35                # posición del sensor de presencia + cámara (arco desde el inicio)
S_ENTRADA = 0.05               # punto donde entra la moneda
V_BANDA = 0.15                 # m/s
MONEDA_INTERVALO = 2.2         # s entre monedas que entran a la banda

# ------------------------------------------------------------------ carrusel de 9 cubículos
CARRUSEL_RADIO = 0.18          # radio al centro de cada cubículo
CUBICULO_LADO = 0.075          # cubículo cuadrado por dentro
CUBICULO_H = 0.06
CUBICULO_PARED = 0.004
CUBICULO_PISO = 0.006
CUBICULO_MASA = 0.09
DISCO_RADIO = CARRUSEL_RADIO + CUBICULO_LADO / 2 + 0.015
DISCO_H = 0.02
DISCO_PEDESTAL_H = BANDA_H - DISCO_H     # así el disco queda a la misma altura que la banda
DISCO_CENTRO = (BANDA_LARGO + CARRUSEL_RADIO, 0.0)     # eje de giro del carrusel
ESTACION_LLENADO = (BANDA_LARGO, 0.0)                  # == extremo de la banda (ángulo mundo = pi)
ESTACION_DESPACHO = (DISCO_CENTRO[0] + CARRUSEL_RADIO, 0.0)  # lado opuesto (ángulo mundo = 0)
ANGULO_VEL = math.radians(70)   # velocidad de indexado del carrusel (motor paso a paso simulado)

def angulo_local(k):
    return k * (2 * math.pi / N_TIPOS)

def yaw_para_llevar(k, angulo_mundo_objetivo):
    """Yaw que debe tener el disco para que el cubículo k quede en angulo_mundo_objetivo."""
    return angulo_mundo_objetivo - angulo_local(k)

YAW_LLENADO = {k: yaw_para_llevar(k, math.pi) for k in range(N_TIPOS)}
YAW_DESPACHO = {k: yaw_para_llevar(k, 0.0) for k in range(N_TIPOS)}

# ------------------------------------------------------------------ carro (remolque)
RUEDA_R = 0.035
RUEDA_ANCHO = 0.02
VIA = 0.18
CARRO_L = 0.30
CARRO_W = 0.14
CARRO_Z = 0.05
CARRO_CHASIS_H = 0.03
CARRO_YAW = 0.0                                          # mirando hacia +x, de espaldas al carrusel
CARRO_POS = (ESTACION_DESPACHO[0] + CARRO_L / 2 + 0.01, ESTACION_DESPACHO[1])
V_CARRO = 0.30
# punto de enganche (remolque), en el marco local del chasis: justo en la parte trasera
HITCH_LOCAL = (-CARRO_L / 2 - 0.01, 0.0, 0.02)

# ------------------------------------------------------------------ pista (curvas + 3 obstáculos)
# Misma forma que antes, trasladada para arrancar justo en CARRO_POS.
_PISTA_REL = [
    (0.90, -0.82), (1.20, -0.82), (1.55, -0.88), (1.85, -1.05), (1.95, -1.35),
    (1.80, -1.65), (1.50, -1.80), (1.15, -1.80), (0.85, -1.95), (0.70, -2.25),
    (0.90, -2.50), (1.30, -2.55), (1.75, -2.50), (2.10, -2.40),
]
_dx = CARRO_POS[0] - _PISTA_REL[0][0]
_dy = CARRO_POS[1] - _PISTA_REL[0][1]
PISTA_PUNTOS = [(x + _dx, y + _dy) for x, y in _PISTA_REL]
PISTA_ANCHO = 0.40
OBSTACULOS_FRAC = (0.11, 0.445, 0.83)
OBSTACULO_DESFASE = 0.06
OBSTACULO_TAM = (0.06, 0.10, 0.10)
