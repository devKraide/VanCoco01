#include <Arduino.h>
#include <BluetoothSerial.h>
#include <Wire.h>
#include <Adafruit_TCS34725.h>

#if defined(CONFIG_BT_ENABLED) && defined(CONFIG_BLUEDROID_ENABLED)
#define COCOVISION_BT_AVAILABLE 1
#else
#define COCOVISION_BT_AVAILABLE 0
#endif

constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr unsigned long DETECTION_DEBOUNCE_MS = 1200;
constexpr float MIN_CLEAR_VALUE = 120.0f;
constexpr float DOMINANCE_RATIO = 1.18f;
constexpr int I2C_SDA_PIN = 21;
constexpr int I2C_SCL_PIN = 22;
constexpr int ENA = 5;
constexpr int IN1 = 18;
constexpr int IN2 = 19;
constexpr int ENB = 25;
constexpr int IN3 = 26;
constexpr int IN4 = 27;
constexpr int MOTOR_SPEED = 180;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;

Adafruit_TCS34725 tcs =
    Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_50MS, TCS34725_GAIN_4X);

String lastColor = "";
String serialBuffer = "";
String bluetoothBuffer = "";
unsigned long lastSentAt = 0;
bool isPresenting = false;
bool sensorActive = false;
#if COCOVISION_BT_AVAILABLE
BluetoothSerial SerialBT;
#endif

String detectDominantColor(uint16_t red, uint16_t green, uint16_t blue, uint16_t clear);
void publishColorIfNeeded(const String& colorName);
void handleCommand(const String& command);
void readCommandStream(Stream& stream, String& buffer);
void emitLine(const char* message);
void runPresentation();
void runAction();
void runReturn();
void moveForward();
void moveBackward();
void turnRight();
void stopMotors();
void setMotorA(bool forward, int speedValue);
void setMotorB(bool forward, int speedValue);

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
#if COCOVISION_BT_AVAILABLE
  SerialBT.begin("COCOVISION");
#else
  Serial.println("COCOVISION_BT_UNAVAILABLE");
#endif
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  stopMotors();

  if (!tcs.begin()) {
    Serial.println("TCS34725_NOT_FOUND");
    while (true) {
      delay(1000);
    }
  }
}

void loop() {
  readCommandStream(Serial, serialBuffer);
#if COCOVISION_BT_AVAILABLE
  readCommandStream(SerialBT, bluetoothBuffer);
#endif

  if (isPresenting) {
    return;
  }

  if (!sensorActive) {
    delay(80);
    return;
  }

  uint16_t red = 0;
  uint16_t green = 0;
  uint16_t blue = 0;
  uint16_t clear = 0;
  tcs.getRawData(&red, &green, &blue, &clear);
  String colorName = detectDominantColor(red, green, blue, clear);
  publishColorIfNeeded(colorName);
  delay(80);
}

void handleCommand(const String& command) {
  String normalized = command;
  normalized.trim();

  if (normalized.isEmpty() || isPresenting) {
    return;
  }

  if (normalized == "COCOVISION:PRESENT") {
    isPresenting = true;
    runPresentation();
    isPresenting = false;
    return;
  }

  if (normalized == "COCOVISION:ACTION") {
    isPresenting = true;
    runAction();
    isPresenting = false;
    return;
  }

  if (normalized == "COCOVISION:RETURN") {
    isPresenting = true;
    runReturn();
    isPresenting = false;
  }
}

String detectDominantColor(uint16_t red, uint16_t green, uint16_t blue, uint16_t clear) {
  if (clear < MIN_CLEAR_VALUE) {
    return "";
  }

  float redRatio = static_cast<float>(red) / clear;
  float greenRatio = static_cast<float>(green) / clear;
  float blueRatio = static_cast<float>(blue) / clear;

  if (redRatio > greenRatio * DOMINANCE_RATIO && redRatio > blueRatio * DOMINANCE_RATIO) {
    return "COLOR_RED";
  }

  if (greenRatio > redRatio * DOMINANCE_RATIO && greenRatio > blueRatio * DOMINANCE_RATIO) {
    return "COLOR_GREEN";
  }

  if (blueRatio > redRatio * DOMINANCE_RATIO && blueRatio > greenRatio * DOMINANCE_RATIO) {
    return "COLOR_BLUE";
  }

  return "";
}

void publishColorIfNeeded(const String& colorName) {
  if (colorName.isEmpty()) {
    return;
  }

  unsigned long now = millis();
  bool isDebounced = colorName == lastColor && (now - lastSentAt) < DETECTION_DEBOUNCE_MS;
  if (isDebounced) {
    return;
  }

  emitLine(("COCOVISION_COLOR=" + colorName).c_str());
  emitLine(colorName.c_str());
  lastColor = colorName;
  lastSentAt = now;
}

void runPresentation() {
  moveForward();
  delay(FORWARD_MS);

  stopMotors();
  delay(STOP_MS);

  turnRight();
  delay(TURN_MS);

  stopMotors();
  delay(STOP_MS);

  moveBackward();
  delay(BACKWARD_MS);

  stopMotors();
  delay(STOP_MS);

  emitLine("COCOVISION_DONE");
}

void runAction() {
  moveForward();
  delay(FORWARD_MS);

  stopMotors();
  delay(STOP_MS);

  sensorActive = true;
  lastColor = "";
  lastSentAt = 0;
  emitLine("COCOVISION_DONE");
}

void runReturn() {
  sensorActive = false;
  moveBackward();
  delay(FORWARD_MS);

  stopMotors();
  delay(STOP_MS);

  emitLine("COCOVISION_DONE");
}

void readCommandStream(Stream& stream, String& buffer) {
  while (stream.available() > 0) {
    char incoming = static_cast<char>(stream.read());
    if (incoming == '\n' || incoming == '\r') {
      if (!buffer.isEmpty()) {
        handleCommand(buffer);
        buffer = "";
      }
      continue;
    }

    buffer += incoming;
  }
}

void emitLine(const char* message) {
  Serial.println(message);
#if COCOVISION_BT_AVAILABLE
  if (SerialBT.hasClient()) {
    SerialBT.println(message);
  }
#endif
}

void moveForward() {
  setMotorA(true, MOTOR_SPEED);
  setMotorB(true, MOTOR_SPEED);
}

void moveBackward() {
  setMotorA(false, MOTOR_SPEED);
  setMotorB(false, MOTOR_SPEED);
}

void turnRight() {
  setMotorA(true, MOTOR_SPEED);
  setMotorB(false, MOTOR_SPEED);
}

void stopMotors() {
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}

void setMotorA(bool forward, int speedValue) {
  digitalWrite(IN1, forward ? HIGH : LOW);
  digitalWrite(IN2, forward ? LOW : HIGH);
  analogWrite(ENA, speedValue);
}

void setMotorB(bool forward, int speedValue) {
  digitalWrite(IN3, forward ? HIGH : LOW);
  digitalWrite(IN4, forward ? LOW : HIGH);
  analogWrite(ENB, speedValue);
}
