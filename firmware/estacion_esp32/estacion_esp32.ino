/*
 * estacion_esp32.ino - ESTACION FIJA del sistema de monedas (un solo ESP32):
 *     banda transportadora (motorreductor + L298N)  +  canaleta con servo SG90  +  sensor de presencia.
 * Se comunica con el PC por el cable USB (Serial 115200). Lo maneja sistema_monedas.py.
 *
 * Conexiones:
 *   L298N ENA -> GPIO 18 (PWM)   IN1 -> GPIO 19   IN2 -> GPIO 21      (jumper de ENA quitado)
 *   Servo SG90: senal naranja/amarillo -> GPIO 23 ; rojo -> +5V del cargador ; marron -> GND comun
 *   Sensor de presencia (opcional): salida -> GPIO 34 (solo entrada). Se asume ACTIVO EN BAJO; cambia ACTIVO_EN_BAJO.
 *   GND del ESP32, del L298N y del cargador unidos.
 *
 * Ordenes (una por linea, terminada en salto de linea):
 *   B <0-100>   banda hacia adelante a ese % (0 = parar)          ej: B 80
 *   C <k>       mueve la canaleta al cubiculo k (0..4)            ej: C 2
 *   G <ang>     mueve el servo a un angulo 0-180 (para calibrar)
 *   S <k> <ang> guarda el angulo del cubiculo k (solo en RAM; luego ponlo en ANGULOS[])
 *   H           canaleta al centro (90)
 *   L           lista los angulos          ?   estado
 * Respuestas:  READY, OK ..., ERR ..., P1 / P0 (sensor de presencia), ST ...
 *
 * El servo y la rampa de la banda se mueven sin bloquear el programa, asi que una orden C nunca espera a la banda.
 * Sin probar en tu placa: calibra ANGULOS, PWM_MIN y SENTIDO_INVERTIDO con el motor y la canaleta reales.
 */
#include <Arduino.h>

const int PIN_ENA = 18, PIN_IN1 = 19, PIN_IN2 = 21;
const int PIN_SERVO = 23;
const int PIN_PRESENCIA = 34;
const bool ACTIVO_EN_BAJO = true;

const bool SENTIDO_INVERTIDO = false;   // true si la banda corre al reves
const int  PWM_MIN = 90;                // duty minimo para que el motor arranque (con cargador de 5 V + L298N)
const int  CAN_BANDA = 0, CAN_SERVO = 2;   // canales LEDC (distintos pares => timers distintos)

const int N_CUBICULOS = 5;
int ANGULOS[N_CUBICULOS] = {20, 45, 90, 135, 160};   // CALIBRAR con tu canaleta
const int ANGULO_REPOSO = 90;
const int PASO_GRADOS = 2;
const unsigned long PASO_SERVO_MS = 12;
const unsigned long PASO_RAMPA_MS = 3;
const unsigned long DEBOUNCE_MS = 60;

int bandaPct = 0, dutyBanda = 0, dutyObjetivo = 0;
int servoActual = ANGULO_REPOSO, servoObjetivo = ANGULO_REPOSO, cubiculoActual = -1;
unsigned long tServo = 0, tRampa = 0, tPresencia = 0;
int presenciaEstable = 0, presenciaLeida = 0;

void pwmBandaInit() {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttachChannel(PIN_ENA, 1000, 8, CAN_BANDA);
  ledcAttachChannel(PIN_SERVO, 50, 14, CAN_SERVO);
#else
  ledcSetup(CAN_BANDA, 1000, 8);  ledcAttachPin(PIN_ENA, CAN_BANDA);
  ledcSetup(CAN_SERVO, 50, 14);   ledcAttachPin(PIN_SERVO, CAN_SERVO);
#endif
}
void escribirBanda(int duty) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_ENA, duty);
#else
  ledcWrite(CAN_BANDA, duty);
#endif
}
void escribirServo(int grados) {
  grados = constrain(grados, 0, 180);
  long pulso_us = 500L + (long)grados * (2400L - 500L) / 180L;       // SG90: 0.5-2.4 ms
  int duty = (int)(pulso_us * 16383L / 20000L);
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO, duty);
#else
  ledcWrite(CAN_SERVO, duty);
#endif
}

void direccionBanda(bool adelante) {
  bool f = adelante != SENTIDO_INVERTIDO;
  digitalWrite(PIN_IN1, f ? HIGH : LOW);
  digitalWrite(PIN_IN2, f ? LOW : HIGH);
}

void ponerBanda(int pct) {
  bandaPct = constrain(pct, 0, 100);
  if (bandaPct == 0) dutyObjetivo = 0;
  else dutyObjetivo = map(bandaPct, 1, 100, PWM_MIN, 255);
}

void ponerServo(int ang) { servoObjetivo = constrain(ang, 0, 180); }

void actualizarBanda() {
  if (dutyBanda == dutyObjetivo || millis() - tRampa < PASO_RAMPA_MS) return;
  tRampa = millis();
  dutyBanda += (dutyObjetivo > dutyBanda) ? 1 : -1;
  if (dutyBanda == 0) { digitalWrite(PIN_IN1, LOW); digitalWrite(PIN_IN2, LOW); }
  else direccionBanda(true);
  escribirBanda(dutyBanda);
}

void actualizarServo() {
  if (servoActual == servoObjetivo || millis() - tServo < PASO_SERVO_MS) return;
  tServo = millis();
  int d = servoObjetivo - servoActual;
  servoActual += (abs(d) < PASO_GRADOS) ? d : (d > 0 ? PASO_GRADOS : -PASO_GRADOS);
  escribirServo(servoActual);
}

void actualizarPresencia() {
  int v = digitalRead(PIN_PRESENCIA);
  int activo = ACTIVO_EN_BAJO ? (v == LOW) : (v == HIGH);
  if (activo != presenciaLeida) { presenciaLeida = activo; tPresencia = millis(); }
  if (presenciaLeida != presenciaEstable && millis() - tPresencia >= DEBOUNCE_MS) {
    presenciaEstable = presenciaLeida;
    Serial.println(presenciaEstable ? "P1" : "P0");
  }
}

void procesar(char *s) {
  while (*s == ' ') s++;
  char c = *s;
  int a = 0, b = 0;
  if (c >= 'a' && c <= 'z') c -= 32;
  int n = sscanf(s + 1, "%d %d", &a, &b);
  switch (c) {
    case 'B':
      if (n >= 1) { ponerBanda(a); Serial.printf("OK B %d\n", bandaPct); } else Serial.println("ERR B <0-100>");
      break;
    case 'C':
      if (n >= 1 && a >= 0 && a < N_CUBICULOS) { cubiculoActual = a; ponerServo(ANGULOS[a]); Serial.printf("OK C %d\n", a); }
      else Serial.println("ERR C <0-4>");
      break;
    case 'G':
      if (n >= 1) { ponerServo(a); Serial.printf("OK G %d\n", servoObjetivo); } else Serial.println("ERR G <0-180>");
      break;
    case 'S':
      if (n >= 2 && a >= 0 && a < N_CUBICULOS) { ANGULOS[a] = constrain(b, 0, 180); Serial.printf("OK S %d %d\n", a, ANGULOS[a]); }
      else Serial.println("ERR S <k> <ang>");
      break;
    case 'H': cubiculoActual = -1; ponerServo(ANGULO_REPOSO); Serial.println("OK H"); break;
    case 'L':
      for (int k = 0; k < N_CUBICULOS; k++) Serial.printf("ANG %d %d\n", k, ANGULOS[k]);
      break;
    case '?':
      Serial.printf("ST belt=%d cup=%d ang=%d pres=%d\n", bandaPct, cubiculoActual, servoActual, presenciaEstable);
      break;
    default: Serial.println("ERR comando");
  }
}

void leerSerial() {
  static char buf[48]; static int n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (n > 0) { buf[n] = 0; procesar(buf); n = 0; } }
    else if (n < (int)sizeof(buf) - 1) buf[n++] = c;
    else n = 0;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_IN1, OUTPUT); pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_PRESENCIA, INPUT);
  digitalWrite(PIN_IN1, LOW); digitalWrite(PIN_IN2, LOW);
  pwmBandaInit();
  escribirBanda(0);
  escribirServo(ANGULO_REPOSO);
  Serial.println("READY");
}

void loop() {
  leerSerial();
  actualizarBanda();
  actualizarServo();
  actualizarPresencia();
}
