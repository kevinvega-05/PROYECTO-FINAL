"""
chatbot.py - Chatbot por consola del sistema de monedas.

Corre el sistema en una terminal (python -m monedas ...) y este chatbot en OTRA:

    python -m monedas.chatbot

Que hace:
  * "estado" / "vasos"      resume lo contado (lee datos/estado.json) y cuantas monedas hay en cada vaso.
  * "despacha el de 500"    escribe datos/comando.json; el sistema manda al carro a enganchar ese vaso, recorrer la
                            pista y el chatbot narra cada etapa hasta que llega a la meta.
  * Si instalas pyttsx3 (pip install pyttsx3) tambien habla.

Entiende texto libre: "despacha el de mil", "manda el vaso de 200", "$500", "cincuenta", etc. Cada vaso junta la moneda
ACTUAL y la ANTIGUA de su valor, asi que ya no hay que decir cual version.
"""
import argparse
import json
import os
import re
import time

from monedas import config as cfg

NUMEROS = {
    "50": 50, "cincuenta": 50,
    "100": 100, "cien": 100, "ciento": 100,
    "200": 200, "doscientos": 200, "doscientas": 200,
    "500": 500, "quinientos": 500, "quinientas": 500,
    "1000": 1000, "mil": 1000, "1.000": 1000,
}
_RE_NUM = re.compile(r"(?<![\w.])(?:\$\s*)?(1\.000|1000|500|200|100|50|mil|cincuenta|ciento|cien|doscientos|doscientas|"
                     r"quinientos|quinientas)(?![\w])", re.IGNORECASE)
PALABRAS_ESTADO = ("estado", "como vas", "cómo vas", "resumen", "cuanto llevamos", "cuánto llevamos")
PALABRAS_VASOS = ("vasos", "vaso", "cubiculos", "cubículos", "inventario")
PALABRAS_SALIR = ("salir", "adios", "adiós", "chao", "exit", "quit")
PALABRAS_DESPACHO = ("despacha", "despachar", "manda", "mandar", "envia", "envía", "lleva", "llevar", "saca", "trae")

_voz = None


def _iniciar_voz():
    global _voz
    try:
        import pyttsx3
        _voz = pyttsx3.init()
        _voz.setProperty("rate", 175)
    except Exception:
        _voz = None


def hablar(msg, voz=True):
    print(f"[chatbot] {msg}", flush=True)
    if voz and _voz is not None:
        try:
            _voz.say(msg)
            _voz.runAndWait()
        except Exception:
            pass


def leer_estado():
    try:
        with open(cfg.ESTADO_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def pesos(valor):
    return "$" + f"{valor:,}".replace(",", ".")


def interpretar_orden(texto):
    """Texto libre -> denominacion (50, 100, 200, 500 o 1000), o None si no se entiende."""
    m = _RE_NUM.search(texto.lower())
    if not m:
        return None
    return NUMEROS.get(m.group(1).lower())


def es_despacho(texto):
    t = texto.lower()
    return any(p in t for p in PALABRAS_DESPACHO)


def resumen_estado(est):
    return (f"Llevamos {est['cantidad_total']} moneda(s) en los vasos por un valor de {pesos(est['valor'])} COP "
            f"y un peso de {est['peso_g']} g. Etapa: {est['etapa']}.")


def narrar_vasos(est):
    vasos = est.get("vasos")
    if not vasos:                                    # estado antiguo (sin 'vasos'): sumar por denominacion
        vasos = {str(v): {"cantidad": sum(est["cubiculos"][i]["cantidad"] for i in ids),
                          "despachado": any(est["cubiculos"][i]["despachado"] for i in ids)}
                 for v, ids in cfg.IDS_DE_VALOR.items()}
    partes = []
    for valor, k in cfg.CUBICULO_DE_VALOR.items():
        v = vasos.get(str(valor), {"cantidad": 0, "despachado": False})
        txt = f"vaso {k} ({pesos(valor)}): {v['cantidad']}"
        if v["despachado"]:
            txt += " [despachado]"
        partes.append(txt)
    rechazo = est.get("rechazo", {}).get("cantidad", 0)
    if rechazo:
        partes.append(f"sin reconocer: {rechazo}")
    return "; ".join(partes)


def enviar_despacho(valor):
    tipo_id = cfg.IDS_DE_VALOR[valor][-1]            # cualquier id de esa denominacion sirve: el vaso es el mismo
    tmp = cfg.COMANDO_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"accion": "despachar", "tipo": tipo_id, "atendido": False}, fh)
    os.replace(tmp, cfg.COMANDO_PATH)


def esperar_resultado(timeout=240, voz=True):
    t0, ultimo = time.time(), None
    while time.time() - t0 < timeout:
        est = leer_estado()
        if est:
            txt = est["carro"]["estado"]
            if txt != ultimo:
                hablar(f"Carro: {txt}.", voz)
                ultimo = txt
            if txt == "meta":
                hablar("Listo, el carro llego a la meta con el vaso.", voz)
                return True
            if txt.startswith("detenido") or txt in ("error", "desconectado"):
                hablar(f"El despacho no termino ({txt}). Revisa el carro y la pista.", voz)
                return False
        time.sleep(1.0)
    hablar("No vi que el carro llegara a la meta en el tiempo esperado.", voz)
    return False


def responder(texto, voz=True, esperar=True):
    """Procesa una frase del usuario. Devuelve False si hay que salir."""
    t = texto.strip().lower()
    if not t:
        return True
    if t in PALABRAS_SALIR:
        hablar("Hasta luego.", voz)
        return False
    if t in ("ayuda", "help", "?"):
        hablar("Puedes decir: 'estado', 'vasos', o 'despacha el de 500' (50, 100, 200, 500 o mil). 'salir' termina.", voz)
        return True
    est = leer_estado()
    if any(p == t or t.startswith(p) for p in PALABRAS_ESTADO):
        if not est:
            hablar("Todavia no veo datos/estado.json: ¿ya arrancaste el sistema (python -m monedas)?", voz)
        else:
            hablar(resumen_estado(est), voz)
            hablar(narrar_vasos(est), voz)
        return True
    if t in PALABRAS_VASOS:
        hablar(narrar_vasos(est) if est else "Todavia no veo datos/estado.json.", voz)
        return True

    valor = interpretar_orden(t)
    if valor is None:
        hablar("No entendi. Prueba con 'despacha el de 500' o escribe 'ayuda'.", voz)
        return True
    if est:
        vaso = est.get("vasos", {}).get(str(valor))
        if vaso is not None and vaso["cantidad"] == 0:
            hablar(f"El vaso de {pesos(valor)} esta vacio, no lo voy a despachar.", voz)
            return True
        if est["carro"]["estado"] in ("enganchando", "recorriendo"):
            hablar("El carro todavia esta ocupado con otro despacho.", voz)
            return True
    hablar(f"Entendido: despachando el vaso de {pesos(valor)}. El carro va a engancharlo.", voz)
    enviar_despacho(valor)
    if esperar:
        esperar_resultado(voz=voz)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Chatbot del sistema de monedas")
    ap.add_argument("--sin-voz", action="store_true", help="no usar pyttsx3 aunque este instalado")
    ap.add_argument("--orden", help="ejecuta una sola orden y termina (para pruebas), ej. --orden 'despacha el de 500'")
    ap.add_argument("--sin-esperar", action="store_true", help="con --orden: no esperar a que el carro llegue")
    args = ap.parse_args(argv)
    if not args.sin_voz:
        _iniciar_voz()
    voz = not args.sin_voz
    if args.orden:
        responder(args.orden, voz=voz, esperar=not args.sin_esperar)
        return 0
    hablar("Chatbot del sistema de monedas listo. Escribe 'estado', 'vasos' o dime que vaso despachar, "
           "por ejemplo: 'despacha el de 500'.", voz)
    while True:
        try:
            texto = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not responder(texto, voz=voz):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
