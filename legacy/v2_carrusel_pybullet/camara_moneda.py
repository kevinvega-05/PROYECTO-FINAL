"""
camara_moneda.py - Clasificación REAL de monedas usando la cámara del celular.

Este módulo reemplaza la "cámara simulada" que hoy tiene simulacion.py (donde, como las
monedas las genera el propio código, simplemente lee la denominación que él mismo creó).
Aquí sí se analiza una imagen de verdad: el celular transmite video por WiFi, este script
la recibe, detecta la moneda con visión por computador y decide qué denominación es,
comparando contra los 9 tipos de config.py::TIPOS.

No está conectado a la simulación PyBullet (esa usa monedas virtuales, no fotos reales).
Este script es el componente que, en el sistema físico real, alimentaría al ESP32 /
Streamlit con la denominación detectada. Su salida es camara_estado.json, mismo patrón
de archivo JSON que ya usan simulacion.py y chatbot.py (estado.json / comando.json).

------------------------------------------------------------------------------
PASO 1: Convierte tu celular en una cámara IP
------------------------------------------------------------------------------
Android:
    1. Instala "IP Webcam" (Pavel Khlebovich) desde Play Store.
    2. Ábrela, baja hasta el final y toca "Start server".
    3. Te muestra una URL tipo  http://192.168.1.34:8080
       - Video MJPEG:  http://192.168.1.34:8080/video   <-- esta es la que usa este script
       - Puedes abrir esa URL en el navegador del PC para confirmar que ves la imagen.
    4. El celular y el computador deben estar en la MISMA red WiFi.

iPhone:
    1. Instala "DroidCam" o "Iriun Webcam" (ambas tienen versión iOS y Android).
    2. Sigue las instrucciones de la app: generalmente te da una IP:puerto igual.
    3. Si la app solo funciona como webcam "virtual" (no da URL MJPEG), instala también
       el driver de escritorio de esa misma app; en ese caso, en vez de una URL, la
       cámara aparece como un dispositivo más (ábrela con cv2.VideoCapture(1) o el
       índice que le corresponda: ver PASO 2b).

------------------------------------------------------------------------------
PASO 2a: Probar la conexión por URL (IP Webcam / similar)
------------------------------------------------------------------------------
    python camara_moneda.py --url http://192.168.1.34:8080/video --probar

PASO 2b: Probar como webcam local (DroidCam/Iriun instalados como driver)
------------------------------------------------------------------------------
    python camara_moneda.py --indice 1 --probar

(si --indice 0 es la webcam del propio PC, la del celular suele quedar en 1; prueba
0, 1, 2... hasta encontrarla)

------------------------------------------------------------------------------
PASO 3: Calibrar (una sola vez, o cuando cambies la distancia/ángulo de la cámara)
------------------------------------------------------------------------------
Pon UNA moneda de $1000 (26.0 mm, la más grande y fácil de aislar) centrada en el
cuadro, quieta, bien iluminada, sobre fondo liso oscuro (contraste ayuda mucho), y
corre:

    python camara_moneda.py --url http://192.168.1.34:8080/video --calibrar

Verás un círculo verde detectado sobre la moneda; con la ventana activa presiona
la barra espaciadora para capturar la calibración (guarda mm_por_pixel en
calibracion.json). Ctrl+C o 'q' para salir sin guardar.

------------------------------------------------------------------------------
PASO 4: Correr la clasificación en vivo
------------------------------------------------------------------------------
    python camara_moneda.py --url http://192.168.1.34:8080/video

Muestra la ventana con el círculo detectado y la denominación estimada, y cada vez
que hay una lectura estable (misma denominación repetida --estabilidad veces
seguidas) la publica en camara_estado.json:

    {"tipo": "500_actual", "confianza": 0.83, "ts": 1234567890.1}

'q' para salir.
"""
import argparse
import json
import time
from collections import deque

import cv2
import numpy as np
import requests

from config import TIPOS

CALIBRACION_PATH = "calibracion.json"
CAMARA_ESTADO_PATH = "camara_estado.json"

# Diámetro de referencia usado para calibrar (la moneda más grande y fácil de aislar).
CAL_TIPO_ID = "1000_actual"
CAL_DIAM_MM = next(t["diam_mm"] for t in TIPOS if t["id"] == CAL_TIPO_ID)


# ---------------------------------------------------------------- captura de video
class MjpegStream:
    """Lee a mano un stream MJPEG por HTTP (lo que sirve IP Webcam en /video).

    Se usa en vez de cv2.VideoCapture(url) porque el backend FFmpeg de OpenCV en
    Windows falla frecuentemente con estos streams (error tipo 'Error number -138
    occurred' aunque la URL sí cargue bien en el navegador).
    """

    def __init__(self, url, timeout=10):
        self.url = url
        self._resp = requests.get(url, stream=True, timeout=timeout)
        self._resp.raise_for_status()
        self._it = self._resp.iter_content(chunk_size=4096)
        self._buf = b""

    def isOpened(self):
        return True

    def read(self):
        try:
            while True:
                a = self._buf.find(b"\xff\xd8")  # inicio de JPEG
                b = self._buf.find(b"\xff\xd9")  # fin de JPEG
                if a != -1 and b != -1 and b > a:
                    jpg = self._buf[a:b + 2]
                    self._buf = self._buf[b + 2:]
                    arr = np.frombuffer(jpg, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return True, frame
                    continue
                chunk = next(self._it, None)
                if chunk is None:
                    return False, None
                self._buf += chunk
                if len(self._buf) > 5_000_000:  # nunca debería pasar; corta basura acumulada
                    self._buf = self._buf[-1_000_000:]
        except Exception:
            return False, None

    def release(self):
        try:
            self._resp.close()
        except Exception:
            pass


def abrir_captura(args):
    if args.url:
        url = args.url
        if not url.rstrip("/").endswith("/video"):
            print(f"Aviso: la URL no termina en /video ({url}); si falla, prueba agregándolo.")
        try:
            cap = MjpegStream(url)
        except requests.RequestException as e:
            raise RuntimeError(
                f"No pude conectarme a {url} ({e}). Revisa que el celular y el PC estén "
                "en la misma red WiFi y que el servidor de la app siga corriendo."
            )
    else:
        cap = cv2.VideoCapture(args.indice, cv2.CAP_DSHOW if args.dshow else 0)
        if not cap.isOpened():
            raise RuntimeError(
                "No pude abrir la cámara local/driver en ese índice. Prueba otro número "
                "con --indice (0, 1, 2...) o agrega --dshow en Windows."
            )
    return cap


# ---------------------------------------------------------------- detección de la moneda
def detectar_circulo(frame_bgr):
    """Devuelve (x, y, radio_px) del círculo más prominente, o None si no encontró nada."""
    gris = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gris = cv2.medianBlur(gris, 5)
    h, w = gris.shape
    circulos = cv2.HoughCircles(
        gris, cv2.HOUGH_GRADIENT, dp=1.2, minDist=h,
        param1=100, param2=40,
        minRadius=int(min(h, w) * 0.08), maxRadius=int(min(h, w) * 0.45),
    )
    if circulos is None:
        return None
    circulos = np.round(circulos[0, :]).astype(int)
    # si detecta varios, toma el más grande (asumimos una sola moneda en cuadro)
    x, y, r = max(circulos, key=lambda c: c[2])
    return int(x), int(y), int(r)


def color_promedio_hsv(frame_bgr, x, y, r):
    """Promedia el color (HSV) dentro de un círculo interior (evita el borde/reflejos)."""
    mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
    cv2.circle(mask, (x, y), max(1, int(r * 0.7)), 255, -1)
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    media = cv2.mean(hsv, mask=mask)  # (H, S, V, _)
    return media[0], media[1], media[2]


def es_dorada(hsv):
    """Heurística simple: saturación alta + tono amarillo/naranja => 'dorada' (bimetálica/
    bronce); saturación baja => 'plateada' (monometálica gris)."""
    h, s, v = hsv
    return s > 60 and 12 <= h <= 45


# ---------------------------------------------------------------- clasificación
def clasificar(diam_mm, dorada):
    """Compara contra los 9 TIPOS por diámetro (principal) y color (para desambiguar
    denominaciones con diámetro parecido, p. ej. 100 / 200 / 500_antigua)."""
    mejor = None
    mejor_score = -1.0
    for t in TIPOS:
        dif_mm = abs(t["diam_mm"] - diam_mm)
        score_tam = max(0.0, 1.0 - dif_mm / 3.0)  # tolera ~3mm de error de medición
        color_t = t["color"]
        # color dorado si el canal rojo/verde domina claramente sobre el azul (paleta config.py)
        t_dorada = (color_t[0] - color_t[2]) > 0.15 or (color_t[1] - color_t[2]) > 0.15
        score_color = 1.0 if t_dorada == dorada else 0.3
        score = 0.7 * score_tam + 0.3 * score_color
        if score > mejor_score:
            mejor_score = score
            mejor = t["id"]
    return mejor, mejor_score


# ---------------------------------------------------------------- calibración
def cargar_calibracion():
    try:
        with open(CALIBRACION_PATH) as fh:
            return json.load(fh)["mm_por_pixel"]
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def guardar_calibracion(mm_por_pixel):
    with open(CALIBRACION_PATH, "w") as fh:
        json.dump({"mm_por_pixel": mm_por_pixel}, fh)


def publicar_lectura(tipo_id, confianza):
    with open(CAMARA_ESTADO_PATH, "w") as fh:
        json.dump({"tipo": tipo_id, "confianza": round(confianza, 3), "ts": time.time()}, fh)


# ---------------------------------------------------------------- modos de ejecución
def modo_probar(cap):
    print("Mostrando video crudo. Presiona 'q' para salir.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No llegó frame; revisa la conexión.")
            break
        cv2.imshow("camara_moneda - prueba", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


def modo_calibrar(cap):
    print(f"Pon la moneda de referencia ({CAL_TIPO_ID}, {CAL_DIAM_MM} mm) centrada y quieta.")
    print("Barra espaciadora = capturar calibración. 'q' = salir sin guardar.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No llegó frame; revisa la conexión.")
            break
        vis = frame.copy()
        circ = detectar_circulo(frame)
        if circ:
            x, y, r = circ
            cv2.circle(vis, (x, y), r, (0, 255, 0), 2)
            cv2.putText(vis, f"radio={r}px", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 255, 0), 2)
        cv2.imshow("camara_moneda - calibracion", vis)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("q"):
            break
        if tecla == ord(" ") and circ:
            x, y, r = circ
            mm_por_pixel = CAL_DIAM_MM / (2 * r)
            guardar_calibracion(mm_por_pixel)
            print(f"Calibración guardada: {mm_por_pixel:.5f} mm/px "
                  f"(radio detectado: {r}px) -> {CALIBRACION_PATH}")
            break
    cap.release()
    cv2.destroyAllWindows()


def modo_clasificar(cap, mm_por_pixel, estabilidad):
    print("Clasificando en vivo. 'q' para salir.")
    historial = deque(maxlen=estabilidad)
    ultimo_publicado = None
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No llegó frame; revisa la conexión.")
            break
        vis = frame.copy()
        circ = detectar_circulo(frame)
        texto = "sin moneda detectada"
        if circ:
            x, y, r = circ
            diam_mm = 2 * r * mm_por_pixel
            hsv = color_promedio_hsv(frame, x, y, r)
            dorada = es_dorada(hsv)
            tipo_id, score = clasificar(diam_mm, dorada)
            historial.append(tipo_id)
            texto = f"{tipo_id}  (diam~{diam_mm:.1f}mm, {'dorada' if dorada else 'plateada'}, score={score:.2f})"
            cv2.circle(vis, (x, y), r, (0, 255, 0), 2)

            if len(historial) == estabilidad and len(set(historial)) == 1:
                if tipo_id != ultimo_publicado:
                    publicar_lectura(tipo_id, score)
                    ultimo_publicado = tipo_id
                    print(f"[publicado] {tipo_id}  score={score:.2f}")
        else:
            historial.clear()
            ultimo_publicado = None

        cv2.putText(vis, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("camara_moneda", vis)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fuente = ap.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--url", help="URL MJPEG de la app de cámara IP, ej: http://192.168.1.34:8080/video")
    fuente.add_argument("--indice", type=int, help="Índice de dispositivo (webcam local/driver DroidCam/Iriun)")
    ap.add_argument("--dshow", action="store_true", help="En Windows, fuerza backend DirectShow (más estable con --indice)")
    ap.add_argument("--probar", action="store_true", help="Solo mostrar el video, sin detectar nada")
    ap.add_argument("--calibrar", action="store_true", help="Modo calibración con la moneda de referencia")
    ap.add_argument("--estabilidad", type=int, default=5, help="Lecturas iguales seguidas antes de publicar (default 5)")
    args = ap.parse_args()

    cap = abrir_captura(args)

    if args.probar:
        modo_probar(cap)
        return
    if args.calibrar:
        modo_calibrar(cap)
        return

    mm_por_pixel = cargar_calibracion()
    if mm_por_pixel is None:
        print(f"No hay calibración guardada todavía. Corre primero:\n"
              f"    python camara_moneda.py {'--url ' + args.url if args.url else '--indice ' + str(args.indice)} --calibrar")
        cap.release()
        return

    modo_clasificar(cap, mm_por_pixel, args.estabilidad)


if __name__ == "__main__":
    main()
