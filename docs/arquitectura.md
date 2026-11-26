# Arquitectura

## Flujo de una moneda

1. La moneda entra por la **tolva de entrada** y la banda (ESP32 + L298N) la lleva bajo la cámara.
2. `vision.py` la detecta (Hough), mide su diámetro en mm con la calibración y su color, y la clasifica en una de las
   9 clases (`tipos.py`). La clase se traduce a un **vaso** (`config.CUBICULO_DE_VALOR`).
3. `planificador.py` espera el instante justo (`DIST_LINEA_A_BORDE_MM / V_BANDA`, o al instante si
   `SERVO_INMEDIATO=True`) y manda `C <k>` a la estación: el servo gira la canaleta al vaso `k`.
   Una moneda no reconocida va al ángulo de rechazo (`G <ANGULO_RECHAZO>`).
4. `estado.py` cuenta la moneda, suma peso y valor y publica `datos/estado.json`.
5. El chatbot o el tablero escriben `datos/comando.json`. `Despachador` (en `planificador.py`) verifica que el vaso no
   esté vacío, envía al carro el enganche y la ruta de `pista.py` por Bluetooth y marca el vaso como despachado
   cuando el carro reporta `meta`.

## Módulos

| Módulo | Responsabilidad |
|---|---|
| `tipos.py` | Las 9 clases y las 5 denominaciones |
| `config.py` | Parámetros, rutas de archivos y overrides por entorno `MONEDAS_<NOMBRE>` |
| `clases.py` | Instala las 9 clases en el clasificador de `vision.py` |
| `vision.py` | Cámara, detección, calibración, clasificación |
| `estado.py` | Estado compartido y publicación atómica del JSON |
| `hardware.py` | `Estacion` (serie), `EstacionSim`, `CarroBLE` (bleak), `CarroSim` |
| `planificador.py` | `Planificador` (servo) y `Despachador` (carro) |
| `pista.py` | Geometría de la pista y generación de la ruta del carro |
| `chatbot.py` / `dashboard.py` | Interfaces |
| `demo.py` | Video sintético y demo completa sin hardware |

## Protocolos

**Estación (USB serie, 115200):** `B <0-100>` banda · `C <k>` canaleta al vaso k · `G <ang>` ángulo directo ·
`S <k> <ang>` guarda ángulo en RAM · `H` centro · `L` lista · `?` estado. Respuestas `READY`, `OK`, `ERR`, `P1/P0`
(sensor), `ST`, `ANG`.

**Carro (BLE JDY-16, 9600):** `M<izq>,<der>` · `S` · `K<izq>,<der>` factor de ruedas % (EEPROM) · `C`/`A<tramos>`/`E`
carga y ejecuta una ruta de hasta 120 tramos (letras `F B L R S` + milisegundos) · `U/W/G<n>` velocidades ·
`N<cm>` distancia de freno · `Q` estado. Respuestas `D<cm>`, `O`, `Z` (ruta completa), `X`.
El enlace BLE parte cada línea en trozos de 20 bytes (característica FFE1).
