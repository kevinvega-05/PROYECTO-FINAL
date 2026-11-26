"""
tipos.py - Las 9 clases de moneda colombiana que maneja el sistema y su vaso fisico.

Hay 5 vasos (uno por denominacion: $50, $100, $200, $500, $1000). Cada vaso recibe la moneda ACTUAL y la
ANTIGUA de su valor, por eso aqui hay 9 tipos (la camara distingue 9 clases) pero solo 5 destinos.

OJO: los diametros y masas son valores de REFERENCIA. Mide tus monedas reales con un pie de rey y corrigelos aqui
(o, mejor, calibra la camara con las monedas reales: ver docs/calibracion.md).
"""
# id, valor (COP), diametro (mm), masa (g), color de dibujo (RGBA)
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

N_TIPOS = len(TIPOS)                       # 9 clases
TIPO_INDEX = {t["id"]: i for i, t in enumerate(TIPOS)}
TIPO_POR_ID = {t["id"]: t for t in TIPOS}
DENOMINACIONES = (50, 100, 200, 500, 1000)  # una por vaso, en el orden de los vasos 0..4
