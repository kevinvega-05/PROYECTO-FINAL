"""
monedas/pista.py - Parametrizacion de la pista del carro y generador de la ruta para carro_monedas.ino

La pista (vista desde arriba) tiene 3 tramos rectos paralelos unidos por 2 retornos en U (semicirculos):
   izquierdo (sube)  ->  retorno superior (a la derecha)  ->  central (baja)  ->  retorno inferior (a la izquierda)
   ->  derecho (sube, meta)

El carro NO va recto "de corrido" porque se desvia a la DERECHA. Por eso:
   * En los tramos rectos avanza PASO_RECTO_MS (1 s) y rectifica CORRECCION_IZQ_MS girando a la izquierda, y repite.
   * En los retornos (U) hace un semicirculo por pasos: avanza un poco, gira un poco, avanza, gira... hasta quedar
     recto en el carril siguiente (poligono de PASO_GIRO_GRADOS grados por vertice).

USO:
   1) Mide la pista y el carro y cambia los valores de MEDIDAS (en mm).
   2) Calibra el carro (CALIBRACION): V_AVANCE, T_GIRO90, CORRECCION_IZQ_MS.
   3) python -m monedas.pista   -> imprime las ordenes, avisos y dibuja docs/pista_plano.png (trayectoria simulada)
"""
import math
import os

# ======================================================== MEDIDAS DE LA PISTA (mm)  <- MIDELAS
ANCHO_CARRIL = 220.0        # ancho del asfalto negro de un tramo recto (borde blanco a borde blanco)
SEPARACION_IZQ_CEN = 320.0  # distancia entre los EJES de los tramos izquierdo y central (= diametro del retorno superior)
SEPARACION_CEN_DER = 320.0  # idem central y derecho (= diametro del retorno inferior)
# Largos de la parte RECTA de cada tramo (donde empieza y termina el semicirculo), por el eje, en mm:
LARGO_IZQ = 910.0         # del punto de partida del carro al inicio del retorno superior   (medido: 91 cm)
LARGO_CEN = 660.0         # del fin del retorno superior al inicio del retorno inferior     (medido: 66 cm)
LARGO_DER = 930.0         # del fin del retorno inferior a la meta                          (medido: 93 cm)
MARGEN_ATRAS = 180.0      # asfalto que hay detras del punto de partida (solo para dibujar)

# ======================================================== MEDIDAS DEL CARRO (mm)  (el punto de salida es el CENTRO del carro)
CARRO_ANCHO = 170.0       # de rueda a rueda
CARRO_LARGO = 240.0       # del sensor al final de la pinza/remolque

# ======================================================== OBSTACULOS (3)  <- PONLOS DONDE LOS PONGAS
# (tramo 1=izq 2=central 3=der, distancia desde el inicio de ese tramo en mm, lado donde esta el obstaculo)
OBSTACULOS = [
    (1, 600.0, "der"),
    (2, 330.0, "izq"),
    (3, 600.0, "der"),
]
OBSTACULO_DIAM = 90.0     # termo Stanley de 0,9 L: ~9 cm de diametro (MIDELO)
INTRUSION = 45.0          # cuanto entra el termo en el carril desde el borde (mm). 45 = centrado sobre la linea
                          # blanca (mitad en el pasto); 90 = todo dentro del carril, pegado al borde.
MARGEN_LATERAL = 10.0     # holgura entre el carro y el termo (mm)
MARGEN_LONG = 20.0        # holgura delante/detras del termo antes de empezar y al terminar el esquive (mm)
ANGULO_ESQUIVE = 25.0     # grados que gira para esquivar
# Cuanto debe correrse el carro hacia el lado libre para no tocar el termo (mm):
DESPLAZAMIENTO = max(0.0, CARRO_ANCHO / 2 + INTRUSION + MARGEN_LATERAL - ANCHO_CARRIL / 2)

# ======================================================== CALIBRACION DEL CARRO  <- MIDE ESTO
# Con el carro en el suelo y las velocidades por defecto del firmware (U150, G120):
#   V_AVANCE: manda RF2000 (2 s) y mide cuantos mm avanzo, divide entre 2  -> mm/s
#   T_GIRO90: prueba RR400, RR450... hasta que gire exactamente 90 grados: ese es el tiempo en ms
V_AVANCE = 250.0          # mm/s  (PLACEHOLDER)
T_GIRO90 = 450.0          # ms para 90 grados  (PLACEHOLDER)

# --- Avance controlado (el carro se desvia a la derecha)
PASO_RECTO_MS = 1000      # avanza este tiempo seguido...
CORRECCION_IZQ_MS = 40    # ...y rectifica girando a la izquierda este tiempo (CALIBRA: sube si aun se va a la derecha)
# --- Retornos en U por pasos
PASO_GIRO_GRADOS = 30.0   # cada vertice del semicirculo gira esto (180 debe ser multiplo: 15, 30, 45, 60)
T_GIRO_PASO_MS = None     # ms que gira el carro PASO_GIRO_GRADOS (mide y pon aqui); None = lo calcula con T_GIRO90

MAX_TRAMOS_FIRMWARE = 120  # igual que MAX_TRAMOS en carro_monedas.ino
PEDAZO_MAX = 60           # caracteres por linea Bluetooth (el firmware admite ~75)


def ms_dist(mm):
    return int(round(mm / V_AVANCE * 1000.0))


def ms_giro(grados):
    if T_GIRO_PASO_MS is not None and abs(grados - PASO_GIRO_GRADOS) < 1e-6:
        return int(round(T_GIRO_PASO_MS))
    if T_GIRO_PASO_MS is not None and abs(grados - PASO_GIRO_GRADOS / 2) < 1e-6:
        return int(round(T_GIRO_PASO_MS / 2))
    return int(round(T_GIRO90 * grados / 90.0))


def avance(mm):
    """Avanza `mm` en pasos: F PASO_RECTO_MS + rectificar a la izquierda, repetido; el resto proporcional."""
    ms = ms_dist(mm)
    if ms <= 0:
        return []
    toks = []
    for _ in range(ms // PASO_RECTO_MS):
        toks += [("F", PASO_RECTO_MS), ("L", CORRECCION_IZQ_MS)]
    resto = ms % PASO_RECTO_MS
    if resto >= 100:
        toks += [("F", resto), ("L", int(round(CORRECCION_IZQ_MS * resto / PASO_RECTO_MS)))]
    elif resto > 0:
        toks.append(("F", resto))
    return [t for t in toks if t[1] > 0]


def retorno(giro, separacion):
    """Semicirculo por pasos de diametro `separacion`: gira medio paso, y luego avanza-gira ... hasta quedar recto."""
    n = max(1, int(round(180.0 / PASO_GIRO_GRADOS)))
    paso = 180.0 / n
    lado = separacion * math.sin(math.radians(paso / 2))          # cuerda = 2 R sin(paso/2), R = separacion/2
    toks = [(giro, ms_giro(paso / 2))]
    for i in range(n):
        toks.append(("F", ms_dist(lado)))
        toks.append((giro, ms_giro(paso if i < n - 1 else paso / 2)))
    return toks


def esquive(lado):
    """Tramos para pasar un obstaculo en `lado` (respecto al carro): se corre al lado libre, se MANTIENE la
    desviacion hasta que la cola pasa el obstaculo y vuelve al eje."""
    a = math.radians(ANGULO_ESQUIVE)
    deg = ANGULO_ESQUIVE
    dx = DESPLAZAMIENTO / math.sin(a) if DESPLAZAMIENTO > 0 else 0.0   # recorrido inclinado
    avance_x = dx * math.cos(a)                                        # avance longitudinal de cada transicion
    hold = OBSTACULO_DIAM + CARRO_LARGO + 2 * MARGEN_LONG              # tramo recto desviado
    huida, vuelta = ("L", "R") if lado == "der" else ("R", "L")
    if DESPLAZAMIENTO <= 0:
        return [], 0.0, 0.0
    toks = [(huida, ms_giro(deg)), ("F", ms_dist(dx)), (vuelta, ms_giro(deg))]
    toks += avance(hold)
    toks += [(vuelta, ms_giro(deg)), ("F", ms_dist(dx)), (huida, ms_giro(deg))]
    return toks, avance_x, 2 * avance_x + hold


PROBLEMAS_RECTO = []      # se llena en tramos_recto: obstaculos que no caben en su tramo


def tramos_recto(num, largo):
    """Recorre un tramo recto de `largo` mm esquivando los obstaculos que haya en el."""
    obs = sorted([(d, lado) for (t, d, lado) in OBSTACULOS if t == num])
    toks, recorrido = [], 0.0
    for d, lado in obs:
        e, avance_x, total = esquive(lado)
        # el carro (centro) empieza a esquivar cuando su frente aun esta MARGEN_LONG antes del obstaculo,
        # ya con la transicion hecha (avance_x)
        inicio = d - OBSTACULO_DIAM / 2 - CARRO_LARGO / 2 - MARGEN_LONG - avance_x
        if inicio < recorrido - 1e-6:
            PROBLEMAS_RECTO.append(f"Obstaculo a {d:.0f} mm del tramo {num}: queda muy cerca del anterior o del inicio "
                                   f"del tramo (el esquive debe empezar {recorrido - inicio:.0f} mm antes de lo posible).")
        recto = max(inicio - recorrido, 0.0)
        toks += avance(recto)
        toks += e
        recorrido += recto + total
    if recorrido > largo + 1e-6:
        PROBLEMAS_RECTO.append(f"En el tramo {num} el esquive termina {recorrido - largo:.0f} mm DESPUES del final del tramo "
                               f"({largo:.0f} mm): acerca el termo al inicio, baja ANGULO_ESQUIVE/MARGEN_LONG o reubicalo.")
    toks += avance(max(largo - recorrido, 0))
    return toks


def construir_ruta():
    r = []
    r += tramos_recto(1, LARGO_IZQ)                      # sube por el tramo izquierdo
    r += retorno("R", SEPARACION_IZQ_CEN)                # retorno superior (a la derecha)
    r += tramos_recto(2, LARGO_CEN)                      # baja por el central
    r += retorno("L", SEPARACION_CEN_DER)                # retorno inferior (a la izquierda)
    r += tramos_recto(3, LARGO_DER)                      # sube por el derecho hasta la meta
    return r


def a_texto(tramos):
    return ",".join(f"{c}{ms}" for c, ms in tramos)


def en_pedazos(tramos):
    """Divide en lineas cortas: C, A..., A..., E (maximo 48 tramos en total)."""
    lineas, actual = [], ""
    for c, ms in tramos:
        tok = f"{c}{ms}"
        if len(actual) + len(tok) + 1 > PEDAZO_MAX - 2:
            lineas.append(actual); actual = ""
        actual += ("," if actual else "") + tok
    if actual:
        lineas.append(actual)
    return ["C"] + ["A" + l for l in lineas] + ["E"]


# ======================================================== DIBUJO / TRAYECTORIA
def geometria():
    """Coordenadas clave (mm), origen en el punto de partida, y hacia la meta."""
    xi, xc, xd = 0.0, SEPARACION_IZQ_CEN, SEPARACION_IZQ_CEN + SEPARACION_CEN_DER
    y_sup = LARGO_IZQ                  # donde acaba el tramo izquierdo y empieza el retorno superior
    y_inf = LARGO_IZQ - LARGO_CEN      # donde acaba el central y empieza el retorno inferior
    y_meta = y_inf + LARGO_DER
    return xi, xc, xd, y_sup, y_inf, y_meta


def simular(ruta):
    """Trayectoria del centro del carro suponiendo que NO se desvia (lo rectifican los pasos L). Puntos (x, y)."""
    x = y = 0.0
    rumbo = 0.0                        # grados, 0 = hacia +y, positivo = a la derecha
    pts = [(x, y)]
    for c, ms in ruta:
        if c == "F":
            d = V_AVANCE * ms / 1000.0
            x += d * math.sin(math.radians(rumbo)); y += d * math.cos(math.radians(rumbo))
            pts.append((x, y))
        elif c == "B":
            d = V_AVANCE * ms / 1000.0
            x -= d * math.sin(math.radians(rumbo)); y -= d * math.cos(math.radians(rumbo))
            pts.append((x, y))
        elif c in ("L", "R"):
            # los pasos L de rectificacion (correccion corta) compensan el desvio real del carro: no se simulan
            if c == "L" and ms <= CORRECCION_IZQ_MS:
                continue
            rumbo += (90.0 * ms / T_GIRO90) * (1 if c == "R" else -1)
    return pts, rumbo


def verificar():
    av = []
    holgura = ANCHO_CARRIL - CARRO_ANCHO
    if holgura < 30:
        av.append(f"Holgura lateral {holgura:.0f} mm entre carro y borde: muy justa (conviene >= 30 mm por lado total).")
    giro = math.hypot(CARRO_ANCHO, CARRO_LARGO) / 2
    if 2 * giro > ANCHO_CARRIL:
        av.append(f"Al girar en su sitio el carro barre un circulo de {2*giro:.0f} mm de diametro y el carril mide "
                  f"{ANCHO_CARRIL:.0f} mm: en los retornos se sale un poco sobre el pasto "
                  "(no pasa nada si la alfombra es lisa, pero revisalo).")
    if OBSTACULOS:
        sobra = ANCHO_CARRIL / 2 - CARRO_ANCHO / 2          # juego del carro dentro del carril, por lado
        if DESPLAZAMIENTO > sobra:
            av.append(f"Para pasar el termo (entra {INTRUSION:.0f} mm en el carril) el carro debe correrse "
                      f"{DESPLAZAMIENTO:.0f} mm, pero dentro del carril solo tiene {sobra:.0f} mm de juego: "
                      f"pisara el pasto {DESPLAZAMIENTO - sobra:.0f} mm. Si no quieres eso, pon el termo mas hacia el "
                      f"borde (INTRUSION menor).")
        a_ = math.radians(ANGULO_ESQUIVE)
        inclinado = CARRO_ANCHO * math.cos(a_) + CARRO_LARGO * math.sin(a_)
        av.append(f"Durante la transicion (giro de {ANGULO_ESQUIVE:.0f} grados) el carro ocupa {inclinado:.0f} mm "
                  f"de ancho; el carril mide {ANCHO_CARRIL:.0f} mm.")
        av.append("En la ruta el freno por distancia baja a 8 cm (orden N8) para que NO se detenga antes de esquivar; "
                  "si esquivas mal, igual frena a 8 cm.")
    del PROBLEMAS_RECTO[:]
    ruta = construir_ruta()
    av += PROBLEMAS_RECTO
    n = len(ruta)
    if n > MAX_TRAMOS_FIRMWARE:
        av.append(f"La ruta tiene {n} tramos y el firmware admite {MAX_TRAMOS_FIRMWARE}: sube MAX_TRAMOS, "
                  "sube PASO_RECTO_MS o quita un esquive.")
    pts, _ = simular(ruta)
    xi, xc, xd, y_sup, y_inf, y_meta = geometria()
    err = math.hypot(pts[-1][0] - xd, pts[-1][1] - y_meta)
    if err > 40:
        av.append(f"En el plano la ruta termina a {err:.0f} mm de la meta (error de redondeo o medidas incoherentes).")
    r_ext = math.hypot(CARRO_ANCHO / 2, CARRO_LARGO / 2) + SEPARACION_IZQ_CEN / 2
    if r_ext > SEPARACION_IZQ_CEN / 2 + ANCHO_CARRIL / 2 + 20:
        av.append(f"En el retorno, la esquina exterior del carro llega a {r_ext:.0f} mm del centro de la U y el borde "
                  f"exterior del carril esta a {SEPARACION_IZQ_CEN/2 + ANCHO_CARRIL/2:.0f} mm: se sale un poco al pasto.")
    paso_ms = ms_giro(PASO_GIRO_GRADOS)
    if paso_ms < 120:
        av.append(f"Cada giro de {PASO_GIRO_GRADOS:.0f} grados dura solo {paso_ms} ms: los motores pueden no alcanzar a girar. "
                  "Usa PASO_GIRO_GRADOS = 45 o 60, o mide T_GIRO_PASO_MS.")
    av.append(f"Avance controlado: {PASO_RECTO_MS} ms recto + {CORRECCION_IZQ_MS} ms a la izquierda "
              f"(el carro se corrige ~{90.0 * CORRECCION_IZQ_MS / T_GIRO90:.1f} grados por ciclo).")
    if SEPARACION_IZQ_CEN < ANCHO_CARRIL or SEPARACION_CEN_DER < ANCHO_CARRIL:
        av.append("La separacion entre ejes es menor que el ancho del carril: revisa las medidas.")
    return av


def dibujar(ruta_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Wedge, Circle

    xi, xc, xd, y_sup, y_inf, y_meta = geometria()
    W = ANCHO_CARRIL
    R1, R2 = SEPARACION_IZQ_CEN / 2, SEPARACION_CEN_DER / 2
    fig, ax = plt.subplots(figsize=(7, 9))
    ax.set_facecolor("#3f8f3f")
    negro = "#222"
    ax.add_patch(Rectangle((xi - W/2, -MARGEN_ATRAS), W, y_sup + MARGEN_ATRAS, color=negro))
    ax.add_patch(Rectangle((xc - W/2, y_inf), W, y_sup - y_inf, color=negro))
    ax.add_patch(Rectangle((xd - W/2, y_inf), W, y_meta - y_inf, color=negro))
    ax.add_patch(Wedge((xi + R1, y_sup), R1 + W/2, 0, 180, width=W, color=negro))           # retorno superior
    ax.add_patch(Wedge((xc + R2, y_inf), R2 + W/2, 180, 360, width=W, color=negro))         # retorno inferior

    ruta = construir_ruta()
    pts, rumbo_final = simular(ruta)
    xs, ys = zip(*pts)
    ax.plot(xs, ys, "-", color="#ffd400", lw=2.2, label="trayectoria simulada del carro")
    ax.plot(*pts[0], "o", color="#00c8ff", ms=10, label="salida")
    ax.plot(xd, y_meta, "s", color="#ff4040", ms=10, label="meta esperada")
    ax.plot(*pts[-1], "x", color="white", ms=10, mew=2, label="donde termina la ruta")
    for k, (t, d, lado) in enumerate(OBSTACULOS, 1):
        x0 = (xi, xc, xd)[t - 1]
        y0 = (0.0, y_sup, y_inf)[t - 1]
        sentido = 1 if t in (1, 3) else -1                 # en el tramo central el carro va hacia abajo
        y = y0 + d * sentido
        lado_x = (1 if lado == "der" else -1) * sentido    # lado (respecto al carro) -> lado en el plano
        cx = x0 + lado_x * (W / 2 + OBSTACULO_DIAM / 2 - INTRUSION)
        ax.add_patch(Circle((cx, y), OBSTACULO_DIAM / 2, color="#ff7a00", zorder=3))
        ax.text(cx, y, str(k), ha="center", va="center", fontsize=9, color="black", weight="bold", zorder=4)
    ax.add_patch(Rectangle((xi - CARRO_ANCHO/2, -CARRO_LARGO/2), CARRO_ANCHO, CARRO_LARGO,
                           fill=False, ec="#00c8ff", lw=1.5))
    ax.set_aspect("equal")
    ax.set_xlim(xi - W, xd + W)
    ax.set_ylim(-MARGEN_ATRAS - 60, y_sup + R1 + W)
    ax.set_xlabel("mm"); ax.set_ylabel("mm")
    ax.set_title(f"Pista y trayectoria simulada ({len(ruta)} tramos, ~{sum(m for _, m in ruta)/1000:.0f} s)")
    ax.text(xi + W/2 + 12, y_sup/2, f"L1 = {LARGO_IZQ:.0f}", rotation=90, va="center", color="white", fontsize=8)
    ax.text(xc + W/2 + 12, (y_sup + y_inf)/2, f"L2 = {LARGO_CEN:.0f}", rotation=90, va="center", color="white", fontsize=8)
    ax.text(xd + W/2 + 12, (y_inf + y_meta)/2, f"L3 = {LARGO_DER:.0f}", rotation=90, va="center", color="white", fontsize=8)
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout()
    fig.savefig(ruta_png, dpi=120)
    plt.close(fig)


def simular_poses(ruta):
    """Poses (t_s, x_mm, y_mm, rumbo_grados) del centro del carro a lo largo de la ruta, para animaciones.
    Los pasos cortos L de rectificacion se ignoran igual que en simular() (compensan el desvio real)."""
    x = y = rumbo = t = 0.0
    poses = [(0.0, x, y, rumbo)]
    for c, ms in ruta:
        dt = ms / 1000.0
        if c in ("F", "B"):
            sgn = 1 if c == "F" else -1
            d = V_AVANCE * dt * sgn
            x += d * math.sin(math.radians(rumbo)); y += d * math.cos(math.radians(rumbo))
        elif c in ("L", "R"):
            if c == "L" and ms <= CORRECCION_IZQ_MS:
                t += dt
                poses.append((t, x, y, rumbo))
                continue
            rumbo += (90.0 * ms / T_GIRO90) * (1 if c == "R" else -1)
        t += dt
        poses.append((t, x, y, rumbo))
    return poses


def cli(argv=None):
    """python -m monedas.pista [--salida DIRECTORIO]   -> imprime la ruta y avisos; guarda plano y ordenes."""
    import argparse
    ap = argparse.ArgumentParser(description="Genera la ruta del carro a partir de las medidas de la pista.")
    ap.add_argument("--salida", default="docs", help="carpeta donde guardar pista_plano.png y pista_ordenes.txt")
    ap.add_argument("--sin-dibujo", action="store_true", help="no generar la imagen")
    args = ap.parse_args(argv)

    ruta = construir_ruta()
    total_ms = sum(ms for _, ms in ruta)
    print(f"Tramos: {len(ruta)}   tiempo estimado: {total_ms/1000:.1f} s")
    print("\nOrdenes para el Bluetooth (una por linea, en este orden):")
    for linea in en_pedazos(ruta):
        print(linea)
    print("\nRuta completa en una sola cadena (para pegar en el panel del carro):")
    print(a_texto(ruta))
    avisos = verificar()
    if avisos:
        print("\nAVISOS / DATOS:")
        for a in avisos:
            print(" -", a)
    os.makedirs(os.path.join(args.salida, "img"), exist_ok=True)
    with open(os.path.join(args.salida, "pista_ordenes.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(en_pedazos(ruta)) + "\n")
    if not args.sin_dibujo:
        png = os.path.join(args.salida, "img", "pista_plano.png")
        dibujar(png)
        print("\nPlano guardado en", png)
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
