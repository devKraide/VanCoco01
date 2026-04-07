#include <Arduino.h>
#include <BluetoothSerial.h>
#include <ESP32Servo.h>

#if defined(CONFIG_BT_ENABLED) && defined(CONFIG_BLUEDROID_ENABLED)
#define COCOMAG_BT_AVAILABLE 1
#else
#define COCOMAG_BT_AVAILABLE 0
#endif

constexpr int ENA = 5;
constexpr int IN1 = 18;
constexpr int IN2 = 19;
constexpr int ENB = 25;
constexpr int IN3 = 26;
constexpr int IN4 = 27;
constexpr int SERVO_PIN = 13;

constexpr int MOTOR_SPEED = 180;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;
constexpr int SERVO_REST_ANGLE = 0;
constexpr int SERVO_ACTION_ANGLE = 90;
constexpr unsigned long SERVO_HOLD_MS = 700;

String serialBuffer;
String bluetoothBuffer;
bool isPresenting = false;
Servo actionServo;
#if COCOMAG_BT_AVAILABLE
BluetoothSerial SerialBT;
#endif

void setMotorA(bool forward, int speedValue);
void setMotorB(bool forward, int speedValue);
void moveForward();
void moveBackward();
void turnRight();
void stopMotors();
void runPresentation();
void runAction();
void handleCommand(const String& command);
void readCommandStream(Stream& stream, String& buffer);
void emitLine(const char* message);

void setup() {
  Serial.begin(115200);
#if COCOMAG_BT_AVAILABLE
  SerialBT.begin("COCOMAG");
#else
  Serial.println("COCOMAG_BT_UNAVAILABLE");
#endif

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  stopMotors();
  actionServo.setPeriodHertz(50);
  actionServo.attach(SERVO_PIN, 500, 2400);
  actionServo.write(SERVO_REST_ANGLE);
}

void loop() {
  readCommandStream(Serial, serialBuffer);
#if COCOMAG_BT_AVAILABLE
  readCommandStream(SerialBT, bluetoothBuffer);
#endif
}

void handleCommand(const String& command) {
  String normalized = command;
  normalized.trim();

  if (normalized.isEmpty()) {
    return;
  }

  if (isPresenting) {
    return;
  }

  if (normalized == "COCOMAG:PRESENT") {
    isPresenting = true;
    runPresentation();
    isPresenting = false;
    return;
  }

  if (normalized == "COCOMAG:ACTION") {
    isPresenting = true;
    runAction();
    isPresenting = false;
  }
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

  emitLine("COCOMAG_DONE");
}

void runAction() {
  moveForward();
  delay(FORWARD_MS);

  stopMotors();
  delay(STOP_MS);

  actionServo.write(SERVO_ACTION_ANGLE);
  delay(SERVO_HOLD_MS);

  actionServo.write(SERVO_REST_ANGLE);
  delay(STOP_MS);

  emitLine("COCOMAG_DONE");
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
#if COCOMAG_BT_AVAILABLE
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
