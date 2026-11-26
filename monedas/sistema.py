"""
sistema.py - Programa principal: vision + conteo + calibracion + estacion + carro + estado.json.

Uso:
  python -m monedas                       sistema real (celular + ESP32 + carro)
  python -m monedas --demo                demo completa SIN hardware (video y carro simulados)
  python -m monedas --fuente http://IP:8080/video --puerto COM5 --carro-nombre JDY
  python -m monedas --sin-estacion --sin-carro      solo vision

Teclas (ventana de video seleccionada):
  F fondo (banda VACIA) | 1-5 calibrar (A: actual/antigua) | M modo | D direccion | R reiniciar | X borrar calibracion
  V mascara | + - umbral | S captura | Q salir
  B  enciende / apaga la banda          T  prueba del servo (recorre los 5 vasos)
"""
import argparse
import os
import sys
import threading
import time
from collections import Counter

import cv2
import numpy as np

from monedas import clases as mc
from monedas import config as cfg
from monedas import vision as vm
from monedas.estado import Estado
from monedas.hardware import CarroBLE, CarroSim, Estacion, EstacionNula, EstacionSim
from monedas.planificador import Despachador, Planificador

# =====================================================================
#  Sistema: vision + conteo + calibracion (la logica de vision_monedas.main, reutilizable)
# =====================================================================
class Sistema:
    def __init__(self, args, estado, estacion, planificador, clasificador):
        self.args, self.est, self.estacion, self.plan = args, estado, estacion, planificador
        self.clasif = clasificador
        self.rastreador = vm.Rastreador()
        self.fondo = None
        self.ver_mascara = False
        self.antigua = False                      # tecla A: las teclas 1-5 calibran ACTUALES o ANTIGUAS
        self.cal_muestras, self.cal_inicio = [], 0.0
        self.vm_estado = {
            "modo": "CONTEO", "direccion": vm.DIRECCION, "umbral": vm.UMBRAL_FONDO,
            "total": 0, "conteo": Counter(), "hay_fondo": False,
            "calibradas": clasificador.calibradas(), "calibrando": None,
            "mensaje": "", "mensaje_hasta": 0.0,
        }

    def avisar(self, msg, seg=2.5):
        print(f"[Info] {msg}", flush=True)
        self.vm_estado["mensaje"], self.vm_estado["mensaje_hasta"] = msg, time.time() + seg

    def procesar(self, crudo):
        """Un cuadro de video -> (imagen para mostrar, mascara)."""
        vs = self.vm_estado
        frame = vm.preparar(crudo)
        if self.fondo is not None and self.fondo.shape != frame.shape:
            self.fondo = None
        vs["hay_fondo"] = self.fondo is not None
        mascara = vm.segmentar(frame, self.fondo, vs["umbral"])
        monedas = vm.detectar(frame, mascara)

        refs = self.clasif.referencias()
        escala = self.clasif.mm_por_px()
        for m in monedas:
            if m["valida"]:
                m["valor"] = vm.Clasificador.clasificar(m["d"], m["oro"], refs) if refs else None
                m["mm"] = m["d"] * escala if escala else None

        # --- calibracion en curso
        if vs["calibrando"]:
            validas = [m for m in monedas if m["valida"]]
            if len(validas) == 1:
                self.cal_muestras.append((validas[0]["d"], validas[0]["oro"]))
            if len(self.cal_muestras) >= vm.MUESTRAS_CALIBRACION:
                d = float(np.median([s[0] for s in self.cal_muestras]))
                oro = float(np.median([s[1] for s in self.cal_muestras]))
                valor = vs["calibrando"]
                self.clasif.agregar(valor, d, oro)
                vs["calibradas"] = self.clasif.calibradas()
                self.avisar(f"{vm.pesos(valor)} calibrada: {d:.1f} px, dorado {oro:.0%}", 4)
                vs["calibrando"] = None
            elif time.time() - self.cal_inicio > vm.TIEMPO_MAX_CALIBRACION:
                self.avisar("Calibracion cancelada: debe haber UNA sola moneda en camara", 4)
                vs["calibrando"] = None

        # --- conteo al cruzar la linea
        if vs["modo"] == "CONTEO" and not vs["calibrando"]:
            eje, signo, linea = vm.parametros_linea(vs["direccion"], frame.shape[1], frame.shape[0])
            for valor in self.rastreador.actualizar(monedas, eje, signo, linea):
                self.moneda_detectada(valor)
        return frame, monedas, mascara

    def moneda_detectada(self, clave):
        vs = self.vm_estado
        valor = mc.valor_de(clave)
        if clave is None:
            vs["conteo"]["?"] += 1
            self.est.evento("Moneda no reconocida: ira a la bandeja de rechazo"
                            + ("" if vs["calibradas"] else " (calibra con las teclas 1-5)"))
        else:
            vs["total"] += valor
            vs["conteo"][clave] += 1
            self.est.evento(f"Camara: {vm.pesos(clave)} -> vaso {cfg.cubiculo_de_valor(valor)} "
                            f"(total camara {vm.pesos(vs['total'])})")
        k = cfg.cubiculo_de_valor(valor)
        self.est.registrar("camara", valor if valor is not None else "", "" if k is None else k, "cruzo la linea")
        self.plan.agregar(clave)

    def dibujar(self, frame, monedas):
        vista = vm.dibujar(frame, monedas, self.vm_estado)
        e = self.est
        lineas = [
            f"Banda: {'ON %d%%' % e.banda_pct if e.banda_pct else 'OFF'}   Canaleta: vaso {e.cubiculo_actual}",
            f"Estacion: {'OK' if e.estacion_ok else '--'}   Carro: {'OK' if e.carro_ok else '--'}   "
            f"En camino: {e.en_camino}",
            f"Carro: {e.carro['estado']}",
            f"Rechazo: {e.rechazadas}",
            f"Calibrar (1-5): monedas {'ANTIGUAS' if self.antigua else 'ACTUALES'}  [A cambia]",
        ]
        ancho = vista.shape[1]
        for i, t in enumerate(lineas):
            vm.texto(vista, t, (ancho - 430, 26 + 24 * i), 0.55, (255, 255, 255))
        return vista

    def tecla(self, k, frame):
        """Maneja una tecla; devuelve False para salir."""
        vs = self.vm_estado
        if k in (ord("q"), 27):
            return False
        if k == ord("f"):
            self.fondo = vm.suavizar(frame)
            self.avisar("Fondo capturado")
        elif k == ord("m"):
            vs["modo"] = "ESTATICO" if vs["modo"] == "CONTEO" else "CONTEO"
            self.rastreador.reiniciar()
            self.avisar(f"Modo {vs['modo']}")
        elif k == ord("d"):
            i = vm.DIRECCIONES.index(vs["direccion"])
            vs["direccion"] = vm.DIRECCIONES[(i + 1) % len(vm.DIRECCIONES)]
            self.rastreador.reiniciar()
            self.avisar(f"Direccion de la banda: {vs['direccion']}")
        elif k == ord("r"):
            vs["total"], vs["conteo"] = 0, Counter()
            self.rastreador.reiniciar()
            self.est.reiniciar_conteo()
            self.avisar("Conteo y vasos reiniciados")
        elif k == ord("x"):
            self.clasif.borrar()
            vs["calibradas"] = []
            self.avisar("Calibracion borrada")
        elif k == ord("v"):
            self.ver_mascara = not self.ver_mascara
            if not self.ver_mascara:
                cv2.destroyWindow("Mascara")
        elif k in (ord("+"), ord("=")):
            vs["umbral"] = min(150, vs["umbral"] + 5)
        elif k in (ord("-"), ord("_")):
            vs["umbral"] = max(5, vs["umbral"] - 5)
        elif k == ord("b"):
            if self.est.banda_pct:
                self.estacion.banda(0)
                self.avisar("Banda apagada")
            else:
                self.estacion.banda(cfg.BANDA_PCT)
                self.avisar(f"Banda encendida al {cfg.BANDA_PCT}%")
        elif k == ord("t"):
            threading.Thread(target=self._probar_servo, daemon=True).start()
        elif k == ord("a"):
            self.antigua = not self.antigua
            self.avisar("Calibrando monedas " + ("ANTIGUAS" if self.antigua else "ACTUALES") + " (teclas 1-5)")
        elif ord("1") <= k <= ord("5"):
            c = mc.clave(mc.DENOMINACIONES[k - ord("1")], self.antigua)
            if c in vm.MONEDAS:
                vs["calibrando"] = c
                self.cal_muestras, self.cal_inicio = [], time.time()
            else:
                self.avisar(f"No existe {vm.pesos(c)} en config.py")
        return True

    def _probar_servo(self):
        self.avisar("Prueba del servo: recorriendo los 5 vasos")
        for k in range(5):
            self.estacion.cubiculo(k)
            time.sleep(1.2)


# =====================================================================
#  Programa principal
# =====================================================================
def construir_hardware(args, estado):
    if args.demo or args.simulado:
        estacion = EstacionSim(estado)
        estacion.banda(cfg.BANDA_PCT)
        estado.estacion_ok = True
        carro = None if args.sin_carro else CarroSim(estado, cfg.DEMO_ACELERACION_CARRO)
        return estacion, carro

    if args.sin_estacion:
        estacion = EstacionNula(estado)
    else:
        try:
            estacion = Estacion(args.puerto or cfg.ESTACION_PUERTO, cfg.ESTACION_BAUDIOS, estado)
            print(f"[estacion] Conectada en {estacion.puerto}", flush=True)
        except Exception as e:
            print(f"[estacion] No pude conectar ({e}). Sigo SIN estacion (solo vision).", flush=True)
            estacion = EstacionNula(estado)

    carro = None
    if not args.sin_carro:
        try:
            carro = CarroBLE(args.carro_nombre or cfg.CARRO_NOMBRE, args.carro_direccion or cfg.CARRO_DIRECCION, estado)
            carro.conectar()
        except Exception as e:
            print(f"[carro] No pude conectar ({e}). Sigo SIN carro: no se podran despachar vasos.", flush=True)
            carro = None
    return estacion, carro


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sistema logistico de monedas inteligentes")
    ap.add_argument("--fuente", default=vm.FUENTE, help="URL de IP Webcam (.../video) o numero de camara")
    ap.add_argument("--imagen", help="Probar con una foto en vez de video")
    ap.add_argument("--puerto", help="Puerto del ESP32 de la estacion (COM5, /dev/ttyUSB0 o auto)")
    ap.add_argument("--carro-nombre", help="Nombre Bluetooth del carro (por defecto 'JDY')")
    ap.add_argument("--carro-direccion", help="Direccion Bluetooth exacta del carro")
    ap.add_argument("--sin-estacion", action="store_true", help="No usar la estacion (banda y servo)")
    ap.add_argument("--sin-carro", action="store_true", help="No usar el carro")
    ap.add_argument("--simulado", action="store_true", help="Estacion y carro simulados (con camara real)")
    ap.add_argument("--demo", action="store_true", help="Demo completa sin hardware: video, estacion y carro simulados")
    ap.add_argument("--sin-ventana", action="store_true", help="No abrir ventanas (para pruebas)")
    ap.add_argument("--duracion", type=float, default=0, help="Salir solo despues de N segundos (0 = nunca)")
    ap.add_argument("--v-banda", type=float, help="Velocidad de la banda en mm/s (por defecto config_proyecto.py)")
    args = ap.parse_args(argv)

    mc.instalar()
    estado = Estado()
    v_banda = args.v_banda or (cfg.DEMO_V_BANDA_MM_S if args.demo else cfg.V_BANDA_MM_S)

    # --- video
    camara, imagen_fija = None, None
    if args.demo:
        from monedas import demo as demo_sintetico
        camara = demo_sintetico.FuenteSintetica(v_banda)
        clasificador = vm.Clasificador(ruta=os.path.join(cfg.DATOS, "calibracion_demo.json"))
        demo_sintetico.calibrar_clasificador(clasificador)
    else:
        clasificador = vm.Clasificador()
        if args.imagen:
            imagen_fija = cv2.imread(args.imagen)
            if imagen_fija is None:
                sys.exit(f"No pude abrir la imagen {args.imagen}")
        else:
            fuente = vm.interpretar_fuente(args.fuente)
            print(f"[camara] Conectando a {fuente} ...", flush=True)
            camara = vm.Camara(fuente)

    estacion, carro = construir_hardware(args, estado)
    plan = Planificador(estacion, estado, v_banda)
    plan.start()
    despachador = Despachador(carro, estado)
    despachador.start()
    sistema = Sistema(args, estado, estacion, plan, clasificador)
    if args.demo:
        sistema.vm_estado["calibradas"] = clasificador.calibradas()

    if os.path.exists(cfg.COMANDO_PATH):
        os.remove(cfg.COMANDO_PATH)                     # no atender ordenes viejas
    estado.etapa = "esperando orden del chatbot (comando.json)"
    estado.evento(f"Sistema listo. Banda a {v_banda:g} mm/s; la moneda tarda "
                  f"{cfg.tiempo_hasta_borde_s(v_banda):.1f} s de la linea al borde.")
    if not args.sin_ventana:
        cv2.namedWindow(vm.VENTANA, cv2.WINDOW_NORMAL)
        print("[Listo] Selecciona la ventana de video y usa las teclas (Q para salir).", flush=True)

    inicio, ultimo_pub, fondo_demo = time.time(), 0.0, False
    try:
        while True:
            if args.duracion and time.time() - inicio > args.duracion:
                break
            crudo = imagen_fija.copy() if imagen_fija is not None else camara.leer()
            if crudo is None:
                if not args.sin_ventana:
                    espera = np.zeros((360, 760, 3), np.uint8)
                    vm.texto(espera, "Esperando video del celular...", (20, 170), 0.9, (0, 255, 255), 2)
                    vm.texto(espera, f"Fuente: {args.fuente}", (20, 210), 0.6)
                    cv2.imshow(vm.VENTANA, espera)
                    if cv2.waitKey(100) & 0xFF in (ord("q"), 27):
                        break
                else:
                    time.sleep(0.1)
                continue

            if args.demo and not fondo_demo:                # la demo arranca con la banda vacia: captura el fondo
                sistema.fondo = vm.suavizar(vm.preparar(crudo))
                fondo_demo = True

            frame, monedas, mascara = sistema.procesar(crudo)

            if time.time() - ultimo_pub > 0.25:
                estado.publicar()
                ultimo_pub = time.time()

            if args.sin_ventana:
                time.sleep(0.03)
                continue
            cv2.imshow(vm.VENTANA, sistema.dibujar(frame, monedas))
            if sistema.ver_mascara:
                cv2.imshow("Mascara", mascara)
            k = cv2.waitKey(30 if imagen_fija is not None else 1) & 0xFF
            if k != 255 and not sistema.tecla(k, frame):
                break
            if k == ord("s"):
                nombre = os.path.join(cfg.DATOS, f"captura_{time.strftime('%H%M%S')}.png")
                cv2.imwrite(nombre, sistema.dibujar(frame, monedas))
                sistema.avisar(f"Captura guardada: {os.path.basename(nombre)}")
    except KeyboardInterrupt:
        pass
    finally:
        plan.activo = False
        despachador.activo = False
        estado.etapa = "apagado"
        estado.publicar()
        if camara:
            camara.cerrar()
        try:
            estacion.cerrar()
        finally:
            if carro:
                carro.cerrar()
        cv2.destroyAllWindows()
    print("\n=== RESUMEN ===")
    print(f"Contadas por la camara: {sistema.vm_estado['total']} pesos "
          f"({dict(sistema.vm_estado['conteo'])})")
    print(f"Cayeron en vasos: {estado.total} monedas, {estado.valor} pesos, rechazadas: {estado.rechazadas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
