"""
planificador.py - Logica de tiempo real del sistema.

Planificador : mueve la canaleta (servo) al vaso correcto justo cuando la moneda llega al borde de la banda.
Despachador  : atiende las ordenes de despacho (datos/comando.json) que escriben el chatbot y el dashboard
               y le pide al carro enganchar el vaso y recorrer la pista.
"""
import itertools
import json
import os
import queue
import threading
import time

from monedas import clases as mc
from monedas import config as cfg
from monedas import vision as vm

# =====================================================================
#  Planificador: gira la canaleta justo a tiempo para cada moneda
# =====================================================================
class Planificador(threading.Thread):
    def __init__(self, estacion, estado, v_banda_mm_s):
        super().__init__(daemon=True)
        self.estacion, self.estado = estacion, estado
        self.v = v_banda_mm_s
        self.q = queue.PriorityQueue()
        self.cuenta = itertools.count()
        self.activo = True

    def agregar(self, clave):
        espera = cfg.TIEMPO_SERVO_S if cfg.SERVO_INMEDIATO else cfg.tiempo_hasta_borde_s(self.v)
        llegada = time.time() + espera
        with self.estado.lock:
            self.estado.en_camino += 1
        self.q.put((llegada, next(self.cuenta), clave))

    def _esperar_hasta(self, t):
        while self.activo and time.time() < t:
            time.sleep(min(0.02, max(0.0, t - time.time())))

    def run(self):
        while self.activo:
            try:
                llegada, _, clave = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            k = cfg.cubiculo_de_valor(mc.valor_de(clave))
            destino = f"el vaso {k}" if k is not None else "la bandeja de rechazo"
            self._esperar_hasta(llegada - cfg.TIEMPO_SERVO_S)
            tarde = time.time() - (llegada - cfg.TIEMPO_SERVO_S)
            if tarde > 0.4:
                self.estado.evento(f"Aviso: monedas muy pegadas; la canaleta llega {tarde:.1f} s tarde a {destino}")
            if k is None:
                self.estacion.angulo(cfg.ANGULO_RECHAZO)
            else:
                self.estacion.cubiculo(k)
            self._esperar_hasta(max(llegada, time.time()) + cfg.TIEMPO_CAIDA_S)
            self.estado.moneda_llego(clave, k)
            nombre = vm.pesos(clave) if clave is not None else "no reconocida"
            self.estado.evento(f"Cayo {nombre} en {destino}")


# =====================================================================
#  Despachador: atiende comando.json (chatbot / dashboard) con el carro
# =====================================================================
class Despachador(threading.Thread):
    def __init__(self, carro, estado):
        super().__init__(daemon=True)
        self.carro, self.estado = carro, estado
        self.activo = True

    @staticmethod
    def _leer_comando():
        if not os.path.exists(cfg.COMANDO_PATH):
            return None
        try:
            with open(cfg.COMANDO_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("accion") == "despachar" and not data.get("atendido"):
            data["atendido"] = True
            try:
                with open(cfg.COMANDO_PATH, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
            except OSError:
                pass
            return data.get("tipo")
        return None

    def run(self):
        while self.activo:
            tipo = self._leer_comando()
            if tipo:
                try:
                    self.despachar(tipo)
                except Exception as e:                     # nunca matar el hilo
                    self.estado.carro["estado"] = "error"
                    self.estado.evento(f"Error al despachar {tipo}: {e}")
            time.sleep(0.3)

    def despachar(self, tipo):
        est = self.estado
        valor = cfg.VALOR_DE_TIPO_ID.get(tipo)
        if valor is None:
            est.evento(f"No hay un vaso fisico para '{tipo}'. Los tipos validos son: "
                       + ", ".join(cfg.VALOR_DE_TIPO_ID))
            return
        k = cfg.CUBICULO_DE_VALOR[valor]          # actual y antigua comparten vaso
        if est.cantidad_vaso(valor) == 0 and not cfg.DESPACHAR_VACIOS:
            est.evento(f"El vaso de {vm.pesos(valor)} esta vacio: no se despacha.")
            return
        if self.carro is None or not est.carro_ok:
            est.evento("El carro no esta conectado por Bluetooth: no puedo despachar.")
            return

        est.etapa = f"carro: enganchando el vaso de {tipo}"
        est.carro["estado"] = "enganchando"
        est.evento(f"Despacho del vaso de {vm.pesos(valor)} (vaso {k}): el carro va a engancharlo")
        est.registrar("despacho", valor, k, "inicio")
        r = self.carro.ejecutar_ruta(cfg.RUTA_ENGANCHE[k])
        if r != "Z":
            self._fallo(tipo, f"enganche: {r}")
            return
        est.carro["enganchado"] = True
        est.etapa = f"carro: recorriendo la pista con el vaso de {tipo}"
        est.carro["estado"] = "recorriendo"
        est.evento("Enganchado. El carro recorre la pista")
        r = self.carro.ejecutar_ruta(cfg.ruta_pista())
        if r == "Z":
            est.carro["estado"] = "meta"
            est.carro["enganchado"] = False
            est.marcar_despachado(valor)
            est.etapa = "esperando orden del chatbot (comando.json)"
            est.evento(f"El carro llego a la meta con el vaso de {vm.pesos(valor)}")
            est.registrar("despacho", valor, k, "meta")
        else:
            self._fallo(tipo, f"recorrido: {r}")

    def _fallo(self, tipo, motivo):
        est = self.estado
        est.carro["estado"] = "detenido por obstaculo" if "O" == motivo.split(": ")[-1] else "detenido"
        est.carro["obstaculos_tocados"] += 1 if motivo.endswith("O") else 0
        est.etapa = "esperando orden del chatbot (comando.json)"
        est.evento(f"El despacho de {tipo} se detuvo ({motivo})")
        est.registrar("despacho", "", "", f"fallo {motivo}")


