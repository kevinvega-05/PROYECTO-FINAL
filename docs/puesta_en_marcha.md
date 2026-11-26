# Puesta en marcha paso a paso

## 1. Software
1. Instala Python 3.10+ (Anaconda sirve). Abre la terminal **en la carpeta del proyecto**.
2. `pip install -r requirements.txt` (si `pip` no se reconoce: `python -m pip install -r requirements.txt`).
3. `python -m monedas --demo` debe abrir las ventanas y mostrar monedas cayendo. Si funciona, el software está bien.

## 2. Cámara del celular
1. Instala **IP Webcam** (Android), conecta celular y PC a la **misma WiFi** y pulsa *Iniciar servidor*.
2. Usa la IP **local** que muestra la app (`192.168.x.x:8080`), nunca una IP pública.
3. Prueba: `python -m monedas --fuente http://192.168.x.x:8080/video --sin-estacion --sin-carro`.
4. Cancelar un comando en la terminal: `Ctrl+C`.

## 3. Estación (ESP32)
1. Abre `firmware/estacion_esp32/estacion_esp32.ino` en el IDE de Arduino (placa *ESP32 Dev Module*) y súbelo.
2. Conexiones: L298N ENA→GPIO18, IN1→19, IN2→21 (sin el jumper de ENA) · servo SG90 señal→GPIO23, rojo→5 V,
   marrón→GND · sensor de presencia→GPIO34 · **todas las tierras unidas**.
3. En el monitor serie (115200) prueba `B 60`, `C 0`…`C 4`, `G 90`. Ajusta `ANGULOS[]` (por defecto 20/45/90/135/160),
   `SENTIDO_INVERTIDO` y `PWM_MIN`.
4. Si cambias `ANGULOS[]`, cámbialos también en `cad/parametros.py` (`ANGULOS_SERVO`) y regenera el CAD.

## 4. Carro
1. Sube `firmware/carro_diagnostico` primero: comprueba que las dos ruedas avanzan en el mismo sentido y a la misma
   velocidad. Después sube `firmware/carro_monedas`.
2. Fija el factor de ruedas: `K100,100`; si se desvía, baja la rueda que va más rápida (`K100,96`…) y mira con `K?`.
3. Mide `V_AVANCE` (manda `RF2000` y mide mm/2) y `T_GIRO90` (prueba `RR400`, `RR450`… hasta 90°) y ponlos en
   `monedas/pista.py`. Regenera con `python -m monedas.pista`.
4. Prueba el panel `herramientas/panel_carro.html` en Chrome (Web Bluetooth): conecta el JDY-16 y manda la ruta.

## 5. Todo junto
```bash
python -m monedas --fuente http://192.168.x.x:8080/video --puerto COM5 --carro-nombre JDY
streamlit run monedas/dashboard.py
python -m monedas.chatbot
```
