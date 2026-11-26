"""
calculos.py - Calculos de ingenieria del sistema (autonomia del carro, consumo, banda, servo, vision).

    python -m monedas.calculos                 # imprime todo con los supuestos por defecto
    python -m monedas.calculos --bateria-mah 2600 --bateria-v 7.4 --motor-ma 300

TODO lo que sea SUPUESTO esta en la clase Supuestos y se marca asi: cambialo por lo que midas con un multimetro.
Los valores "tipicos" salen de hojas de datos genericas; los del proyecto, de config.py / pista.py / cad/parametros.py.
"""
import argparse
import math
from dataclasses import dataclass, fields

from monedas import config as cfg
from monedas import pista
from monedas.tipos import TIPOS


@dataclass
class Supuestos:
    # ---- carro (las celdas se ven en la foto; su capacidad REAL es un supuesto: mide con una prueba de descarga)
    bateria_mah: float = 1500.0          # 2 celdas 18650 UltraFire (foto del carro). Etiqueta: 6800 mAh (inflada); real ~1000-2000
    bateria_v: float = 7.4
    usable: float = 0.80                 # fraccion de la capacidad que se aprovecha (tension de corte, envejecimiento)
    motor_ma: float = 250.0              # corriente de cada motor TT con carga (tipico 150-250; atascado > 700)
    logica_ma: float = 70.0              # Arduino UNO (~45) + JDY-16 (~10) + sensor de distancia (~15)
    caida_puente_v: float = 1.4          # caida del puente H del shield (tipico 1,4-2 V)
    espera_entre_viajes_s: float = 60.0  # carro quieto entre dos despachos
    enganche_s: float = 0.8              # B800 de RUTA_ENGANCHE
    rueda_d_mm: float = 65.0             # TT tipica
    # ---- estacion (fuente de 5 V)
    fuente_a: float = 2.0
    servo_mov_ma: float = 250.0          # SG90 en movimiento (tipico 100-250)
    servo_stall_ma: float = 650.0        # SG90 bloqueado (tipico)
    banda_ma: float = 300.0              # motor TT de la banda con carga a ~3 V tras el L298N
    banda_stall_ma: float = 800.0
    esp32_ma: float = 80.0               # sin WiFi; hasta ~240 con WiFi
    l298_logica_ma: float = 36.0
    # ---- monedas / vision
    espesor_moneda_mm: float = 2.0       # SUPUESTO: mide con pie de rey
    llenado_vaso: float = 0.60           # fraccion de volumen realmente aprovechada (apilado irregular)
    fov_mm: float = 200.0                # ancho de banda que ve la camara
    pixeles_ancho: int = 1280
    fps: float = 25.0                    # IP Webcam real; sube a 30 si la red lo permite
    sigma_px: float = 0.5                # incertidumbre de medida del diametro (px), Hough


def autonomia_carro(s: Supuestos):
    """Tiempo de uso del carro y viajes por carga."""
    i_mov = 2 * s.motor_ma + s.logica_ma                       # mA mientras recorre
    cap = s.bateria_mah * s.usable
    t_ruta = pista.simular_poses(pista.construir_ruta())[-1][0]
    t_viaje = t_ruta + s.enganche_s
    mah_viaje = i_mov * t_viaje / 3600.0
    mah_espera = s.logica_ma * s.espera_entre_viajes_s / 3600.0
    return {
        "i_mov_ma": i_mov, "i_reposo_ma": s.logica_ma, "capacidad_util_mah": cap,
        "horas_moviendose": cap / i_mov, "horas_en_reposo": cap / s.logica_ma,
        "t_viaje_s": t_viaje, "mah_por_viaje": mah_viaje, "wh_por_viaje": mah_viaje * s.bateria_v / 1000.0,
        "viajes_por_carga": cap / (mah_viaje + mah_espera),
        "horas_con_ciclo": cap / (mah_viaje + mah_espera) * (t_viaje + s.espera_entre_viajes_s) / 3600.0,
        "tension_motor_v": s.bateria_v - s.caida_puente_v,
    }


def cinematica_carro(s: Supuestos):
    """Velocidades del carro implicadas por los tiempos provisionales de pista.py."""
    v = pista.V_AVANCE
    rpm = v / (math.pi * s.rueda_d_mm) * 60.0
    track = pista.CARRO_ANCHO
    w_teo = 2 * v / track                                       # giro en el sitio con ruedas a +-v (rad/s)
    t90_teo = (math.pi / 2) / w_teo
    w_prov = math.radians(90.0) / (pista.T_GIRO90 / 1000.0)
    corr = 90.0 * pista.CORRECCION_IZQ_MS / pista.T_GIRO90      # grados que gira cada correccion L40
    dif_equiv = math.radians(corr) / (pista.PASO_RECTO_MS / 1000.0) * track / v   # desajuste de ruedas que compensa
    ruta = pista.construir_ruta()
    poses = pista.simular_poses(ruta)
    camino = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(poses, poses[1:]))
    return {"rpm_rueda": rpm, "giro_teorico_90_ms": t90_teo * 1000, "giro_provisional_90_ms": pista.T_GIRO90,
            "velocidad_giro_prov_deg_s": math.degrees(w_prov), "correccion_por_paso_deg": corr,
            "desajuste_ruedas_compensado_pct": dif_equiv * 100, "camino_mm": camino,
            "tiempo_ruta_s": poses[-1][0], "velocidad_media_mm_s": camino / poses[-1][0],
            "tramos": len(ruta), "caracteres_ruta": len(pista.a_texto(ruta))}


def estacion_electrica(s: Supuestos):
    """Presupuesto de corriente de la fuente de 5 V de la estacion."""
    tipica = s.esp32_ma + s.l298_logica_ma + s.banda_ma + s.servo_mov_ma
    pico = s.esp32_ma + s.l298_logica_ma + s.banda_ma + s.servo_stall_ma
    peor = s.esp32_ma + s.l298_logica_ma + s.banda_stall_ma + s.servo_stall_ma
    return {"tipica_ma": tipica, "pico_servo_ma": pico, "peor_caso_ma": peor,
            "potencia_tipica_w": 5.0 * tipica / 1000.0, "potencia_peor_w": 5.0 * peor / 1000.0,
            "margen_fuente_pct": 100.0 * (s.fuente_a * 1000 - peor) / (s.fuente_a * 1000)}


def banda(s: Supuestos):
    v = cfg.V_BANDA_MM_S
    largo = 660.0
    sep_min = max(t["diam_mm"] for t in TIPOS) + 14.0                          # separacion de seguridad entre monedas
    paso_s = sep_min / v
    return {"v_mm_s": v, "recorrido_total_s": largo / v, "linea_a_borde_s": cfg.DIST_LINEA_A_BORDE_MM / v,
            "separacion_min_mm": sep_min, "caudal_max_monedas_s": 1.0 / paso_s,
            "monedas_por_hora": 3600.0 / paso_s,
            "frames_por_moneda": (s.fov_mm / v) * s.fps,
            "v_max_por_frames_mm_s": s.fov_mm * s.fps / 10.0}                  # >= 10 cuadros por moneda


def servo(s: Supuestos):
    angulos = (20, 45, 90, 135, 160)
    peor = max(angulos) - min(angulos)
    t_60 = 0.10                                                                # SG90 tipico sin carga a 4,8 V
    return {"peor_salto_deg": peor, "t_peor_salto_s": peor / 60.0 * t_60,
            "t_peor_con_rampa_s": peor / 60.0 * t_60 + cfg.TIEMPO_SERVO_S,
            "torque_nm": 1.8 * 0.0980665}


def vasos(s: Supuestos):
    di, h, fondo = 36.0, 45.0, 3.0
    vol_int = math.pi * (di / 2) ** 2 * (h - fondo) / 1000.0                   # cm3
    out = {"volumen_interno_cm3": vol_int}
    for t in TIPOS:
        v_moneda = math.pi * (t["diam_mm"] / 2) ** 2 * s.espesor_moneda_mm / 1000.0
        out[t["id"]] = {"n_max": int(vol_int * s.llenado_vaso / v_moneda), "masa_g": t["masa_g"]}
    peor = max(out[t["id"]]["n_max"] * t["masa_g"] for t in TIPOS)
    out["masa_max_monedas_g"] = peor
    return out


def vision(s: Supuestos):
    mm_px = s.fov_mm / s.pixeles_ancho
    delta = 21.0 - 20.5                                                         # $500 antigua vs $100 antigua
    sigma_mm = s.sigma_px * mm_px
    return {"mm_por_px": mm_px, "dif_par_critico_mm": delta, "dif_par_critico_px": delta / mm_px,
            "sigma_mm": sigma_mm, "separacion_sigmas": delta / sigma_mm if sigma_mm else float("inf"),
            "px_ancho_minimo_para_4sigma": 4 * s.sigma_px * s.fov_mm / delta}


def fuerza_remolque(s: Supuestos, mu: float = 0.4):
    masa_kg = (20.0 + vasos(s)["masa_max_monedas_g"]) / 1000.0                  # vaso ~20 g (PLA) + monedas
    return {"masa_kg": masa_kg, "fuerza_n": mu * masa_kg * 9.81}


def todo(s: Supuestos | None = None):
    s = s or Supuestos()
    return {"autonomia": autonomia_carro(s), "cinematica": cinematica_carro(s), "estacion": estacion_electrica(s),
            "banda": banda(s), "servo": servo(s), "vasos": vasos(s), "vision": vision(s), "remolque": fuerza_remolque(s)}


def imprimir(r):
    def sec(t):
        print(f"\n== {t} ==")
    def kv(d):
        for k, v in d.items():
            if isinstance(v, dict):
                print(f"  {k}: " + ", ".join(f"{a}={b:.2f}" if isinstance(b, float) else f"{a}={b}" for a, b in v.items()))
            elif isinstance(v, float):
                print(f"  {k}: {v:.3g}")
            else:
                print(f"  {k}: {v}")
    for t, d in r.items():
        sec(t)
        kv(d)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Calculos de ingenieria del sistema de monedas")
    for f in fields(Supuestos):
        ap.add_argument("--" + f.name.replace("_", "-"), type=type(f.default), default=f.default)
    a = ap.parse_args(argv)
    imprimir(todo(Supuestos(**{f.name: getattr(a, f.name) for f in fields(Supuestos)})))


if __name__ == "__main__":
    main()
