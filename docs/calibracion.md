# Calibración de la visión

Teclas en la ventana de video: `F` fondo (banda vacía) · `1–5` denominación · `A` actual/antigua · `M` modo ·
`D` sentido de la banda · `R` reiniciar · `B` banda · `T` probar servo · `Q`/`Esc` salir · `+`/`-` ajustes.

1. **Fondo:** con la banda vacía y bien iluminada, pulsa `F`.
2. **Cubierta:** la banda negra texturizada confunde la detección; cúbrela con cartulina lisa y mate (sin brillos).
3. **Monedas:** una a la vez, centrada, elige su denominación (`1–5`) y si es antigua (`A`) y guarda. El sistema guarda
   diámetro en píxeles y si el centro es dorado.
4. **Pares difíciles:** $100 antigua vs $500 antigua (2,4 % de diferencia) y $200 vs $500. Calibra primero estas y
   comprueba con 10 pasadas cada una; si se confunden, mejora la iluminación y la altura de la cámara (más píxeles por moneda).
5. La calibración se guarda en `datos/` (`MONEDAS_DATOS` cambia la carpeta).
6. La clasificación sintética acierta ~98 % con ±0,3 mm de error de medida; con monedas reales **valida tú**.
