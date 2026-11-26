"""
CLASIFICADOR DE MONEDAS POR VISION - Proyecto banda transportadora
Celular Android (app IP Webcam) encima de la banda  ->  PC con Python + OpenCV
Monedas: $50, $100, $200 y $1000 (familia nueva)

Como funciona:
  1. Separa las monedas del fondo (banda blanca) comparando con una foto de la banda vacia.
  2. Mide el diametro de cada moneda y que tan dorado es su centro.
  3. Compara con las monedas de referencia que tu calibras y decide cual es.
  4. Cuenta cada moneda cuando cruza una linea y suma el total.

Uso:
  python vision_monedas.py                                      -> usa FUENTE (abajo)
  python vision_monedas.py --fuente http://192.168.43.1:8080/video
  python vision_monedas.py --fuente 0                           -> camara del portatil
  python vision_monedas.py --imagen foto.jpg                    -> prueba con una foto

Teclas (con la ventana de video seleccionada):
  F        capturar el fondo (banda VACIA, sin monedas)
  1 2 3 4  calibrar con UNA moneda en camara: 1=$50 2=$100 3=$200 4=$1000
  M        cambiar modo: CONTEO (cuenta al cruzar la linea) / ESTATICO (suma lo que ve)
  D        cambiar la direccion en que avanza la banda
  R        reiniciar el conteo
  X        borrar la calibracion
  V        ver/ocultar la mascara (para ajustar)
  + / -    subir/bajar el umbral de deteccion
  S        guardar una captura de pantalla
  Q o Esc  salir
"""
import argparse
import json
import os
import sys
import threading
import time
from collections import Counter

import cv2
import numpy as np

# =====================================================================
#  CONFIGURACION (ajusta aqui)
# =====================================================================
# Direccion que muestra la app IP Webcam, terminada en /video
FUENTE = "http://192.168.43.1:8080/video"

ANCHO_PROCESO = 960      # el video se reescala a este ancho para procesar
ROTACION = 0             # 0, 90, 180 o 270 si la imagen sale girada

# valor -> diametro real (mm), si su centro es dorado, color del dibujo (BGR), tecla
MONEDAS = {
    50:   {"mm": 17.0, "dorada": False, "color": (255, 170, 0),  "tecla": "1"},
    100:  {"mm": 20.3, "dorada": True,  "color": (0, 200, 255),  "tecla": "2"},
    200:  {"mm": 22.4, "dorada": False, "color": (230, 60, 230), "tecla": "3"},
    1000: {"mm": 26.7, "dorada": True,  "color": (0, 210, 0),    "tecla": "4"},
}

# --- Deteccion ---
UMBRAL_FONDO = 40        # diferencia minima con el fondo para considerar "moneda" (+/- en vivo)
SAT_MIN_SIN_FONDO = 60   # solo se usa si no has capturado fondo
AREA_MIN = 400           # area minima en px (descarta basuritas)
AREA_MAX_FRAC = 0.25     # area maxima como fraccion de la imagen
RELLENO_MIN = 0.72       # area / circulo envolvente. Menor = no es UNA moneda (estan juntas)

# --- Color dorado (HSV de OpenCV, H de 0 a 179) ---
DORADO_H = (8, 38)
DORADO_S_MIN = 70
DORADO_V_MIN = 60

# --- Clasificacion ---
TOL_TAMANO = 0.08        # diferencia maxima de diametro con la referencia (8 %)
PESO_COLOR = 1.0         # cuanto pesa el color frente al tamano

# --- Conteo ---
DIRECCION = "derecha"    # hacia donde se mueven las monedas EN LA IMAGEN: derecha, izquierda, abajo, arriba
POS_LINEA = 0.5          # posicion de la linea de conteo (0 a 1)
DIST_MAX_SEGUIMIENTO = 90  # px que puede moverse una moneda entre dos cuadros
FRAMES_PERDIDA = 8       # cuadros sin ver una moneda antes de olvidarla

MUESTRAS_CALIBRACION = 15
TIEMPO_MAX_CALIBRACION = 6.0  # segundos

# --- Envio al ESP32 por USB (opcional, para despues) ---
SERIAL_PUERTO = None     # ej. "COM5". None = desactivado
SERIAL_BAUDIOS = 115200

from monedas.config import DATOS  # noqa: E402  (la calibracion se guarda en la carpeta de datos)
CARPETA = DATOS
ARCHIVO_CALIBRACION = os.path.join(DATOS, "calibracion.json")
DIRECCIONES = ["derecha", "abajo", "izquierda", "arriba"]
VENTANA = "Clasificador de monedas"


# =====================================================================
#  Utilidades
# =====================================================================
def pesos(valor):
    """Formato colombiano: 1500 -> $1.500"""
    return "$" + f"{valor:,}".replace(",", ".")


def preparar(frame):
    if ROTACION == 90:
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif ROTACION == 180:
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    elif ROTACION == 270:
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    alto, ancho = frame.shape[:2]
    if ancho != ANCHO_PROCESO:
        escala = ANCHO_PROCESO / ancho
        frame = cv2.resize(frame, (ANCHO_PROCESO, int(alto * escala)), interpolation=cv2.INTER_AREA)
    return frame


def suavizar(frame):
    return cv2.GaussianBlur(frame, (5, 5), 0)


# =====================================================================
#  1. Segmentacion: separar monedas del fondo
# =====================================================================
def segmentar(frame, fondo, umbral):
    suave = suavizar(frame)
    if fondo is not None and fondo.shape == suave.shape:
        # Diferencia con la banda vacia, en el canal donde mas cambia
        dif = cv2.absdiff(suave, fondo).max(axis=2)
        _, mascara = cv2.threshold(dif, umbral, 255, cv2.THRESH_BINARY)
    else:
        # Sin fondo: estima el papel blanco "borrando" las monedas (dilatacion grande)
        # y busca lo que es mas oscuro o mas colorido que el papel
        gris = cv2.cvtColor(suave, cv2.COLOR_BGR2GRAY)
        alto, ancho = gris.shape
        peq = cv2.resize(gris, (ancho // 4, alto // 4), interpolation=cv2.INTER_AREA)
        k = max(15, int(ancho * 0.22 / 4)) | 1
        papel = cv2.dilate(peq, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        papel = cv2.resize(cv2.blur(papel, (k, k)), (ancho, alto), interpolation=cv2.INTER_LINEAR)
        _, m1 = cv2.threshold(cv2.subtract(papel, gris), umbral, 255, cv2.THRESH_BINARY)
        sat = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)[:, :, 1]
        m2 = cv2.inRange(sat, SAT_MIN_SIN_FONDO, 255)
        mascara = cv2.bitwise_or(m1, m2)

    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, nucleo, iterations=1)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, nucleo, iterations=2)

    # Rellenar huecos (brillos dentro de la moneda)
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    llena = np.zeros_like(mascara)
    cv2.drawContours(llena, contornos, -1, 255, cv2.FILLED)
    return llena


# =====================================================================
#  2. Deteccion y medicion
# =====================================================================
def fraccion_dorada(hsv, x, y, r):
    """Fraccion de pixeles dorados en el centro de la moneda (radio 0.5 r)."""
    alto, ancho = hsv.shape[:2]
    rc = max(2, int(r * 0.5))
    x0, x1 = max(0, int(x) - rc), min(ancho, int(x) + rc + 1)
    y0, y1 = max(0, int(y) - rc), min(alto, int(y) + rc + 1)
    recorte = hsv[y0:y1, x0:x1]
    if recorte.size == 0:
        return 0.0
    yy, xx = np.ogrid[y0:y1, x0:x1]
    dentro = (xx - x) ** 2 + (yy - y) ** 2 <= rc ** 2
    h, s, v = recorte[:, :, 0], recorte[:, :, 1], recorte[:, :, 2]
    dorado = (h >= DORADO_H[0]) & (h <= DORADO_H[1]) & (s >= DORADO_S_MIN) & (v >= DORADO_V_MIN)
    n = dentro.sum()
    return float((dorado & dentro).sum() / n) if n else 0.0


def detectar(frame, mascara):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    area_max = AREA_MAX_FRAC * frame.shape[0] * frame.shape[1]
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    monedas = []
    for c in contornos:
        area = cv2.contourArea(c)
        if area < AREA_MIN or area > area_max:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        relleno = area / (np.pi * r * r) if r > 0 else 0
        m = {
            "x": float(x), "y": float(y), "r": float(r),
            "d": float(2 * np.sqrt(area / np.pi)),  # diametro equivalente por area (mas estable)
            "relleno": float(relleno),
            "valida": relleno >= RELLENO_MIN,
            "oro": 0.0, "valor": None, "mm": None,
        }
        if m["valida"]:
            m["oro"] = fraccion_dorada(hsv, x, y, r)
        monedas.append(m)
    return monedas


# =====================================================================
#  3. Clasificacion (con calibracion usando tus monedas reales)
# =====================================================================
class Clasificador:
    def __init__(self, ruta=ARCHIVO_CALIBRACION):
        self.ruta = ruta
        self.muestras = {v: [] for v in MONEDAS}   # valor -> [[diametro_px, oro], ...]
        self.cargar()

    def cargar(self):
        try:
            with open(self.ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            for clave, lista in datos.items():
                valor = int(clave)
                if valor in MONEDAS:
                    self.muestras[valor] = [[float(a), float(b)] for a, b in lista]
            print(f"[Calibracion] Cargada: {self.resumen()}")
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, ValueError, TypeError, OSError) as e:
            print(f"[Calibracion] No pude leer {self.ruta} ({e}). Empiezo sin calibracion.")

    def guardar(self):
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump({str(v): l for v, l in self.muestras.items()}, f, indent=2)

    def agregar(self, valor, d, oro):
        self.muestras[valor].append([d, oro])
        self.muestras[valor] = self.muestras[valor][-5:]   # ultimas 5 calibraciones
        self.guardar()

    def borrar(self):
        self.muestras = {v: [] for v in MONEDAS}
        if os.path.exists(self.ruta):
            os.remove(self.ruta)

    def calibradas(self):
        return [v for v in MONEDAS if self.muestras[v]]

    def resumen(self):
        cal = self.calibradas()
        return ", ".join(pesos(v) for v in cal) if cal else "ninguna"

    def mm_por_px(self):
        cal = self.calibradas()
        if not cal:
            return None
        return float(np.mean([MONEDAS[v]["mm"] / np.mean([m[0] for m in self.muestras[v]])
                              for v in cal]))

    def referencias(self):
        """Referencias medidas; las monedas sin calibrar se estiman por su tamano real."""
        escala = self.mm_por_px()
        if escala is None:
            return {}
        refs = {}
        for v, info in MONEDAS.items():
            if self.muestras[v]:
                arr = np.array(self.muestras[v])
                refs[v] = {"d": float(arr[:, 0].mean()), "oro": float(arr[:, 1].mean()), "medida": True}
            else:
                refs[v] = {"d": info["mm"] / escala, "oro": 0.6 if info["dorada"] else 0.0,
                           "medida": False}
        return refs

    @staticmethod
    def clasificar(d, oro, refs):
        mejor, mejor_puntaje = None, float("inf")
        for v, ref in refs.items():
            err_tam = abs(d - ref["d"]) / ref["d"]
            if err_tam > TOL_TAMANO:
                continue
            err_color = abs(oro - ref["oro"])
            if not ref["medida"]:
                err_color *= 0.5   # color estimado: pesa menos
            puntaje = err_tam / TOL_TAMANO + PESO_COLOR * err_color
            if puntaje < mejor_puntaje:
                mejor, mejor_puntaje = v, puntaje
        return mejor


# =====================================================================
#  4. Seguimiento y conteo al cruzar la linea
# =====================================================================
def parametros_linea(direccion, ancho, alto):
    eje = 0 if direccion in ("derecha", "izquierda") else 1
    signo = 1 if direccion in ("derecha", "abajo") else -1
    linea = POS_LINEA * (ancho if eje == 0 else alto)
    return eje, signo, linea


class Rastreador:
    def __init__(self):
        self.pistas = {}
        self.siguiente_id = 0

    def reiniciar(self):
        self.pistas.clear()

    def actualizar(self, monedas, eje, signo, linea):
        """Devuelve la lista de valores de las monedas que acaban de cruzar la linea."""
        dets = [m for m in monedas if m["valida"]]
        libres = set(range(len(dets)))
        usadas = set()
        cruces = []

        pares = sorted(
            (float(np.hypot(p["x"] - d["x"], p["y"] - d["y"])), pid, i)
            for pid, p in self.pistas.items() for i, d in enumerate(dets)
        )
        for dist, pid, i in pares:
            if dist > DIST_MAX_SEGUIMIENTO:
                break
            if pid in usadas or i not in libres:
                continue
            usadas.add(pid)
            libres.discard(i)
            p, d = self.pistas[pid], dets[i]
            antes = p["x"] if eje == 0 else p["y"]
            ahora = d["x"] if eje == 0 else d["y"]
            p.update(x=d["x"], y=d["y"], perdida=0)
            if d["valor"] is not None:
                p["votos"][d["valor"]] += 1
            d["id"] = pid
            if not p["contada"] and signo * (antes - linea) < 0 <= signo * (ahora - linea):
                p["contada"] = True
                valor = p["votos"].most_common(1)[0][0] if p["votos"] else None
                cruces.append(valor)
                d["cruzo"] = True

        for pid in list(self.pistas):
            if pid not in usadas:
                self.pistas[pid]["perdida"] += 1
                if self.pistas[pid]["perdida"] > FRAMES_PERDIDA:
                    del self.pistas[pid]

        for i in libres:
            d = dets[i]
            pos = d["x"] if eje == 0 else d["y"]
            votos = Counter()
            if d["valor"] is not None:
                votos[d["valor"]] += 1
            self.pistas[self.siguiente_id] = {
                "x": d["x"], "y": d["y"], "votos": votos, "perdida": 0,
                # si aparece ya pasada la linea, no se cuenta
                "contada": signo * (pos - linea) >= 0,
            }
            d["id"] = self.siguiente_id
            self.siguiente_id += 1
        return cruces


# =====================================================================
#  Camara en un hilo (siempre entrega el cuadro mas reciente, sin retraso)
# =====================================================================
class Camara:
    def __init__(self, fuente):
        self.fuente = fuente
        self.frame = None
        self.lock = threading.Lock()
        self.activa = True
        self.cap = self._abrir()
        if not self.cap.isOpened():
            print(f"[Camara] No pude abrir {fuente}. Seguire intentando...")
        threading.Thread(target=self._bucle, daemon=True).start()

    def _abrir(self):
        if isinstance(self.fuente, int) and sys.platform == "win32":
            return cv2.VideoCapture(self.fuente, cv2.CAP_DSHOW)
        return cv2.VideoCapture(self.fuente)

    def _bucle(self):
        fallos = 0
        while self.activa:
            ok, f = self.cap.read()
            if ok and f is not None:
                fallos = 0
                with self.lock:
                    self.frame = f
            else:
                fallos += 1
                time.sleep(0.1)
                if fallos >= 20:
                    print("[Camara] Sin video, reconectando...")
                    self.cap.release()
                    time.sleep(1)
                    self.cap = self._abrir()
                    fallos = 0

    def leer(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def cerrar(self):
        self.activa = False
        time.sleep(0.15)
        self.cap.release()


# =====================================================================
#  Dibujo en pantalla (sin tildes: OpenCV no las dibuja)
# =====================================================================
def texto(img, t, pos, escala=0.6, color=(255, 255, 255), grosor=1):
    cv2.putText(img, t, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), grosor + 2, cv2.LINE_AA)
    cv2.putText(img, t, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)


def dibujar(frame, monedas, estado):
    vista = frame.copy()
    alto, ancho = vista.shape[:2]

    # Linea de conteo
    if estado["modo"] == "CONTEO":
        eje, signo, linea = parametros_linea(estado["direccion"], ancho, alto)
        l = int(linea)
        if eje == 0:
            cv2.line(vista, (l, 0), (l, alto), (0, 0, 255), 2)
            flecha = ((l - 40, 30), (l + 40, 30)) if signo > 0 else ((l + 40, 30), (l - 40, 30))
        else:
            cv2.line(vista, (0, l), (ancho, l), (0, 0, 255), 2)
            flecha = ((ancho - 30, l - 40), (ancho - 30, l + 40)) if signo > 0 else \
                     ((ancho - 30, l + 40), (ancho - 30, l - 40))
        cv2.arrowedLine(vista, flecha[0], flecha[1], (0, 0, 255), 2, tipLength=0.3)

    # Monedas
    for m in monedas:
        c = (int(m["x"]), int(m["y"]))
        if not m["valida"]:
            cv2.circle(vista, c, int(m["r"]), (0, 140, 255), 2)
            texto(vista, "juntas?", (c[0] - 30, c[1]), 0.5, (0, 140, 255))
            continue
        if m["valor"] is None:
            color, etiqueta = (150, 150, 150), "?"
        else:
            color, etiqueta = MONEDAS[m["valor"]]["color"], pesos(m["valor"])
        cv2.circle(vista, c, int(m["r"]), color, 4 if m.get("cruzo") else 2)
        texto(vista, etiqueta, (c[0] - 25, c[1] - int(m["r"]) - 10), 0.75, color, 2)
        if m["mm"]:
            texto(vista, f"{m['mm']:.1f} mm", (c[0] - 30, c[1] + int(m["r"]) + 20), 0.5)

    # Panel de resultados
    lineas = len(MONEDAS) + 3
    capa = vista.copy()
    cv2.rectangle(capa, (0, 0), (250, 30 + 26 * lineas), (0, 0, 0), -1)
    vista = cv2.addWeighted(capa, 0.55, vista, 0.45, 0)
    y = 32
    if estado["modo"] == "CONTEO":
        texto(vista, f"TOTAL: {pesos(estado['total'])}", (10, y), 0.85, (0, 255, 255), 2)
        for v in MONEDAS:
            y += 26
            texto(vista, f"{pesos(v):>6}  x {estado['conteo'][v]}", (10, y), 0.6, MONEDAS[v]["color"])
        y += 26
        texto(vista, f"No reconocidas: {estado['conteo']['?']}", (10, y), 0.5, (180, 180, 180))
    else:
        visibles = Counter(m["valor"] for m in monedas if m["valida"] and m["valor"] is not None)
        suma = sum(v * n for v, n in visibles.items())
        texto(vista, f"EN PANTALLA: {pesos(suma)}", (10, y), 0.8, (0, 255, 255), 2)
        for v in MONEDAS:
            y += 26
            texto(vista, f"{pesos(v):>6}  x {visibles[v]}", (10, y), 0.6, MONEDAS[v]["color"])
        y += 26
    y += 26
    texto(vista, f"Modo: {estado['modo']}  Umbral: {estado['umbral']}", (10, y), 0.5, (200, 200, 200))

    # Avisos
    avisos = []
    if not estado["hay_fondo"]:
        avisos.append("Presiona F con la banda VACIA para capturar el fondo")
    if not estado["calibradas"]:
        avisos.append("Calibra: deja UNA moneda y presiona 1($50) 2($100) 3($200) 4($500) 5($1000)  [A: antigua]")
    if estado["calibrando"]:
        avisos.append(f"Calibrando {pesos(estado['calibrando'])}... deja solo esa moneda quieta")
    if estado["mensaje"] and time.time() < estado["mensaje_hasta"]:
        avisos.append(estado["mensaje"])
    for i, a in enumerate(avisos):
        texto(vista, a, (10, alto - 40 - 26 * i), 0.6, (0, 255, 255), 2)

    texto(vista, "F fondo | 1-5 calibrar | A antigua | M modo | D direccion | R reiniciar | V mascara | +/- umbral | Q salir",
          (10, alto - 10), 0.45, (220, 220, 220))
    return vista


# =====================================================================
#  Programa principal
# =====================================================================
def interpretar_fuente(valor):
    return int(valor) if str(valor).isdigit() else valor


def main():
    parser = argparse.ArgumentParser(description="Clasificador de monedas por vision")
    parser.add_argument("--fuente", default=FUENTE, help="URL de IP Webcam o numero de camara")
    parser.add_argument("--imagen", help="Probar con una foto en lugar de video")
    args = parser.parse_args()

    clasificador = Clasificador()
    rastreador = Rastreador()

    puerto = None
    if SERIAL_PUERTO:
        try:
            import serial
            puerto = serial.Serial(SERIAL_PUERTO, SERIAL_BAUDIOS, timeout=0)
            print(f"[Serial] Conectado a {SERIAL_PUERTO}")
        except Exception as e:
            print(f"[Serial] No pude abrir {SERIAL_PUERTO}: {e}")

    camara, imagen_fija = None, None
    if args.imagen:
        imagen_fija = cv2.imread(args.imagen)
        if imagen_fija is None:
            sys.exit(f"No pude abrir la imagen {args.imagen}")
    else:
        fuente = interpretar_fuente(args.fuente)
        print(f"[Camara] Conectando a {fuente} ...")
        camara = Camara(fuente)

    estado = {
        "modo": "CONTEO" if camara else "ESTATICO",
        "direccion": DIRECCION, "umbral": UMBRAL_FONDO,
        "total": 0, "conteo": Counter(), "hay_fondo": False,
        "calibradas": clasificador.calibradas(), "calibrando": None,
        "mensaje": "", "mensaje_hasta": 0.0,
    }
    fondo = None
    ver_mascara = False
    cal_muestras, cal_inicio = [], 0.0

    def avisar(msg, segundos=2.5):
        print(f"[Info] {msg}")
        estado["mensaje"], estado["mensaje_hasta"] = msg, time.time() + segundos

    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    print("[Listo] Selecciona la ventana de video y usa las teclas (Q para salir).")

    while True:
        crudo = imagen_fija.copy() if imagen_fija is not None else camara.leer()
        if crudo is None:
            espera = np.zeros((360, 760, 3), np.uint8)
            texto(espera, "Esperando video del celular...", (20, 170), 0.9, (0, 255, 255), 2)
            texto(espera, f"Fuente: {args.fuente}", (20, 210), 0.6)
            cv2.imshow(VENTANA, espera)
            if cv2.waitKey(100) & 0xFF in (ord("q"), 27):
                break
            continue

        frame = preparar(crudo)
        if fondo is not None and fondo.shape != frame.shape:
            fondo = None   # cambio la resolucion
        estado["hay_fondo"] = fondo is not None

        mascara = segmentar(frame, fondo, estado["umbral"])
        monedas = detectar(frame, mascara)

        refs = clasificador.referencias()
        escala = clasificador.mm_por_px()
        for m in monedas:
            if m["valida"]:
                m["valor"] = Clasificador.clasificar(m["d"], m["oro"], refs) if refs else None
                m["mm"] = m["d"] * escala if escala else None

        # --- Calibracion en curso ---
        if estado["calibrando"]:
            validas = [m for m in monedas if m["valida"]]
            if len(validas) == 1:
                cal_muestras.append((validas[0]["d"], validas[0]["oro"]))
            if len(cal_muestras) >= MUESTRAS_CALIBRACION:
                d = float(np.median([s[0] for s in cal_muestras]))
                oro = float(np.median([s[1] for s in cal_muestras]))
                valor = estado["calibrando"]
                clasificador.agregar(valor, d, oro)
                estado["calibradas"] = clasificador.calibradas()
                avisar(f"{pesos(valor)} calibrada: {d:.1f} px, dorado {oro:.0%}", 4)
                estado["calibrando"] = None
            elif time.time() - cal_inicio > TIEMPO_MAX_CALIBRACION:
                avisar("Calibracion cancelada: debe haber UNA sola moneda en camara", 4)
                estado["calibrando"] = None

        # --- Conteo ---
        if estado["modo"] == "CONTEO" and not estado["calibrando"]:
            eje, signo, linea = parametros_linea(estado["direccion"], frame.shape[1], frame.shape[0])
            for valor in rastreador.actualizar(monedas, eje, signo, linea):
                if valor is None:
                    estado["conteo"]["?"] += 1
                    print("[Conteo] Moneda no reconocida")
                    continue
                estado["total"] += valor
                estado["conteo"][valor] += 1
                print(f"[Conteo] {pesos(valor)}  ->  total {pesos(estado['total'])}")
                if puerto:
                    try:
                        puerto.write(f"MONEDA,{valor},{estado['total']}\n".encode())
                    except Exception as e:
                        print(f"[Serial] Error: {e}")

        cv2.imshow(VENTANA, dibujar(frame, monedas, estado))
        if ver_mascara:
            cv2.imshow("Mascara", mascara)

        tecla = cv2.waitKey(30 if imagen_fija is not None else 1) & 0xFF
        if tecla in (ord("q"), 27):
            break
        elif tecla == ord("f"):
            fondo = suavizar(frame)
            avisar("Fondo capturado")
        elif tecla in (ord("m"),):
            estado["modo"] = "ESTATICO" if estado["modo"] == "CONTEO" else "CONTEO"
            rastreador.reiniciar()
            avisar(f"Modo {estado['modo']}")
        elif tecla == ord("d"):
            i = DIRECCIONES.index(estado["direccion"])
            estado["direccion"] = DIRECCIONES[(i + 1) % len(DIRECCIONES)]
            rastreador.reiniciar()
            avisar(f"Direccion de la banda: {estado['direccion']}")
        elif tecla == ord("r"):
            estado["total"], estado["conteo"] = 0, Counter()
            rastreador.reiniciar()
            avisar("Conteo reiniciado")
        elif tecla == ord("x"):
            clasificador.borrar()
            estado["calibradas"] = []
            avisar("Calibracion borrada")
        elif tecla == ord("v"):
            ver_mascara = not ver_mascara
            if not ver_mascara:
                cv2.destroyWindow("Mascara")
        elif tecla in (ord("+"), ord("=")):
            estado["umbral"] = min(150, estado["umbral"] + 5)
        elif tecla in (ord("-"), ord("_")):
            estado["umbral"] = max(5, estado["umbral"] - 5)
        elif tecla == ord("s"):
            nombre = os.path.join(CARPETA, f"captura_{time.strftime('%H%M%S')}.png")
            cv2.imwrite(nombre, dibujar(frame, monedas, estado))
            avisar(f"Captura guardada: {os.path.basename(nombre)}")
        else:
            for v, info in MONEDAS.items():
                if tecla == ord(info["tecla"]):
                    estado["calibrando"] = v
                    cal_muestras, cal_inicio = [], time.time()
                    break

    if camara:
        camara.cerrar()
    if puerto:
        puerto.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
