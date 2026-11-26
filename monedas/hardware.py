"""
hardware.py - Conexion con el hardware: estacion (ESP32 por USB) y carro (Arduino por Bluetooth BLE).

Cada clase real tiene una gemela simulada para probar todo sin hardware:
    Estacion     -> EstacionSim / EstacionNula        (banda + servo + sensor de presencia)
    CarroBLE     -> CarroSim                           (recorre la ruta en tiempo acelerado)
"""
import queue
import threading
import time

from monedas import config as cfg

# =====================================================================
#  Estacion (ESP32): banda + canaleta + sensor de presencia
# =====================================================================
class EstacionSim:
    """Estacion simulada: solo imprime lo que haria el ESP32."""
    prefijo = "[estacion simulada]"

    def __init__(self, estado, silenciosa=False):
        self.estado = estado
        self.silenciosa = silenciosa
        self.ordenes = []

    def enviar(self, cmd):
        self.ordenes.append((time.time(), cmd))
        if not self.silenciosa:
            print(f"   {self.prefijo} -> {cmd}", flush=True)

    def banda(self, pct):
        self.estado.banda_pct = int(pct)
        self.enviar(f"B {int(pct)}")

    def cubiculo(self, k):
        self.estado.cubiculo_actual = int(k)
        self.enviar(f"C {int(k)}")

    def angulo(self, ang):
        """Canaleta a un angulo libre (para el rechazo, fuera de los vasos)."""
        self.estado.cubiculo_actual = None
        self.enviar(f"G {int(ang)}")

    def cerrar(self):
        self.banda(0)


class EstacionNula(EstacionSim):
    prefijo = "[SIN ESTACION]"


class Estacion(EstacionSim):
    """ESP32 real por USB (pyserial)."""
    prefijo = "[estacion]"

    def __init__(self, puerto, baudios, estado):
        super().__init__(estado, silenciosa=True)
        import serial
        from serial.tools import list_ports
        if puerto in (None, "auto"):
            puerto = self._buscar(list_ports)
        self.puerto = puerto
        self.ser = serial.Serial(puerto, baudios, timeout=0.1)
        self.lock = threading.Lock()
        self.activa = True
        time.sleep(2.0)                      # el ESP32 se reinicia al abrir el puerto
        self.ser.reset_input_buffer()
        threading.Thread(target=self._leer, daemon=True).start()
        estado.estacion_ok = True

    @staticmethod
    def _buscar(list_ports):
        pistas = ("CP210", "CH340", "CH910", "FTDI", "USB", "SILICON", "UART")
        candidatos = [p for p in list_ports.comports()
                      if any(s in (p.description or "").upper() + (p.manufacturer or "").upper() for s in pistas)]
        if not candidatos:
            raise RuntimeError("No encontre el ESP32 de la estacion. Conectalo por USB o usa --puerto COM5.")
        return candidatos[0].device

    def _leer(self):
        while self.activa:
            try:
                linea = self.ser.readline().decode("utf-8", "ignore").strip()
            except Exception:
                self.estado.estacion_ok = False
                time.sleep(0.5)
                continue
            if not linea:
                continue
            if linea == "P1":
                self.estado.presencia = True
            elif linea == "P0":
                self.estado.presencia = False
            elif linea.startswith("ERR"):
                print(f"   [estacion] {linea}", flush=True)

    def enviar(self, cmd):
        with self.lock:
            try:
                self.ser.write((cmd + "\n").encode())
            except Exception as e:
                self.estado.estacion_ok = False
                print(f"   [estacion] error al enviar '{cmd}': {e}", flush=True)

    def cerrar(self):
        try:
            self.banda(0)
            time.sleep(0.2)
        finally:
            self.activa = False
            self.ser.close()


# =====================================================================
#  Carro (Arduino UNO + JDY-16 por BLE)
# =====================================================================
def partir_ruta(texto, maximo=None):
    """'F1000,L450,...' -> ['C', 'AF1000,L450,...', 'A...', 'E']  (lineas cortas para el Bluetooth)."""
    maximo = maximo or cfg.CARRO_PEDAZO_MAX
    tramos = [t for t in texto.replace(" ", "").upper().split(",") if t]
    lineas, actual = [], ""
    for t in tramos:
        if actual and len("A" + actual + "," + t) > maximo:
            lineas.append("A" + actual)
            actual = ""
        actual += ("," if actual else "") + t
    if actual:
        lineas.append("A" + actual)
    return ["C"] + lineas + ["E"]


def duracion_ruta_s(texto):
    total = 0
    for t in texto.replace(" ", "").split(","):
        if len(t) > 1 and t[1:].isdigit():
            total += int(t[1:])
    return total / 1000.0


class CarroSim:
    """Carro simulado: 'recorre' la ruta en tiempo acelerado."""

    def __init__(self, estado, aceleracion=10.0):
        self.estado = estado
        self.aceleracion = aceleracion
        self.ordenes = []
        estado.carro_ok = True

    def ejecutar_ruta(self, texto, timeout=None):
        self.ordenes.append(texto)
        s = duracion_ruta_s(texto)
        print(f"   [carro simulado] ruta de {len(texto.split(','))} tramos (~{s:.0f} s reales, "
              f"{s / self.aceleracion:.1f} s simulados)", flush=True)
        time.sleep(s / self.aceleracion)
        return "Z"

    def cerrar(self):
        pass


class CarroBLE:
    """Carro real por Bluetooth BLE (bleak) en un hilo asyncio propio."""

    def __init__(self, nombre, direccion, estado):
        import asyncio
        self.asyncio = asyncio
        self.nombre, self.direccion, self.estado = nombre, direccion, estado
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.client = None
        self.char = None
        self.sin_respuesta = True
        self.eventos = queue.Queue()
        self._buf = ""
        self.lock = threading.Lock()

    def _correr(self, coro, timeout):
        return self.asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def conectar(self, timeout=40):
        return self._correr(self._conectar(), timeout)

    async def _conectar(self):
        from bleak import BleakClient, BleakScanner
        print(f"[carro] Buscando por Bluetooth '{self.direccion or self.nombre}'...", flush=True)
        if self.direccion:
            dispositivo = await BleakScanner.find_device_by_address(self.direccion, timeout=15)
        else:
            dispositivo = await BleakScanner.find_device_by_filter(
                lambda d, ad: (d.name or ad.local_name or "").upper().startswith(self.nombre.upper()), timeout=15)
        if dispositivo is None:
            raise RuntimeError("No encontre el carro por Bluetooth. ¿Esta encendido (boton ON) y libre "
                               "(sin otra app conectada)?")
        self.client = BleakClient(dispositivo, disconnected_callback=self._al_desconectar)
        await self.client.connect()
        chars = [c for s in self.client.services for c in s.characteristics]
        pref = [c for c in chars if c.uuid.lower() == cfg.UUID_CARRO]
        escribibles = pref or [c for c in chars if {"write", "write-without-response"} & set(c.properties)]
        notificables = pref or [c for c in chars if {"notify", "indicate"} & set(c.properties)]
        if not escribibles:
            raise RuntimeError("El Bluetooth del carro no tiene una caracteristica donde escribir.")
        self.char = escribibles[0]
        self.sin_respuesta = "write-without-response" in self.char.properties
        if notificables:
            await self.client.start_notify(notificables[0], self._on_notify)
        self.estado.carro_ok = True
        print(f"[carro] Conectado a {dispositivo.name or dispositivo.address}", flush=True)

    def _al_desconectar(self, _client):
        self.estado.carro_ok = False
        print("[carro] Bluetooth desconectado.", flush=True)

    def _on_notify(self, _sender, data):
        self._buf += bytes(data).decode("utf-8", "ignore")
        while "\n" in self._buf or "\r" in self._buf:
            i = min(x for x in (self._buf.find("\n"), self._buf.find("\r")) if x >= 0)
            linea, self._buf = self._buf[:i].strip(), self._buf[i + 1:]
            if not linea:
                continue
            if linea.startswith("D") and linea[1:].isdigit():
                self.estado.dist_cm = int(linea[1:])
            else:
                self.eventos.put(linea)
        if len(self._buf) > 200:
            self._buf = ""

    async def _escribir(self, txt):
        datos = (txt + "\n").encode()
        for i in range(0, len(datos), 20):
            await self.client.write_gatt_char(self.char, datos[i:i + 20], response=not self.sin_respuesta)
            await self.asyncio.sleep(0.015)

    def enviar(self, txt):
        self._correr(self._escribir(txt), 8)

    def ejecutar_ruta(self, texto, timeout=None):
        """Envia la ruta y espera el resultado: 'Z' completa, 'O' obstaculo, 'X' cancelada, 'R?' invalida, 'timeout'."""
        timeout = timeout or cfg.CARRO_TIMEOUT_RUTA_S
        if not self.estado.carro_ok:
            return "desconectado"
        with self.lock:
            while not self.eventos.empty():
                self.eventos.get_nowait()
            for linea in partir_ruta(texto):
                self.enviar(linea)
                time.sleep(0.12)
            limite = time.time() + timeout
            while time.time() < limite:
                try:
                    r = self.eventos.get(timeout=0.5)
                except queue.Empty:
                    if not self.estado.carro_ok:
                        return "desconectado"
                    continue
                if r in ("Z", "O", "X"):
                    return r
                if r in ("R?", "A?"):
                    return "R?"
            try:
                self.enviar("X")
            except Exception:
                pass
            return "timeout"

    def cerrar(self):
        try:
            if self.client and self.client.is_connected:
                self.enviar("X")
                self._correr(self.client.disconnect(), 5)
        except Exception:
            pass


