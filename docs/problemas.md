# Problemas encontrados y soluciones

| Síntoma | Causa | Solución |
|---|---|---|
| `pip` no se reconoce | Anaconda sin PATH / carpeta equivocada | `python -m pip ...` y `cd` a la carpeta del proyecto |
| ▶ ejecuta un archivo viejo | El botón corre el archivo abierto | Ejecuta `python -m monedas ...` desde la terminal |
| IP Webcam no conecta | Se usó una IP pública | Usa la IP local `192.168.x.x` y la misma WiFi |
| No detecta la moneda | Banda negra texturizada / brillos | Cubierta de cartulina mate; recalibra con `F` |
| Tarda en guardar el tipo | Pocas muestras estables | Moneda quieta unos segundos; luz pareja |
| El carro gira en círculos | `K100,50` guardado en EEPROM | `K100,100` y afinar; mira `K?` |
| El carro se va a un lado | Ruedas de distinta velocidad | Factor `K` y `CORRECCION_IZQ_MS` en `pista.py` |
| Panel: «Formato no válido» | Se pegó `pista_ordenes.txt` completo | El panel acepta el formato `C/A…/E` (ya soportado) |
| El obstáculo 2 no cabe | Tramo central de 66 cm | Se movió a 330 mm y se avisa en `PROBLEMAS_RECTO` |
| La banda no arrastra | Motor/PWM mínimo | `PWM_MIN` y `SENTIDO_INVERTIDO` en el `.ino` (pendiente) |
