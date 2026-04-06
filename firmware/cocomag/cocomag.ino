#include <Arduino.h>

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

String serialBuffer;
bool isPresenting = false;

void setMotorA(bool forward, int speedValue);
void setMotorB(bool forward, int speedValue);
void moveForward();
void moveBackward();
void turnRight();
void stopMotors();
void runPresentation();
void handleCommand(const String& command);

void setup() {
  Serial.begin(115200);

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  stopMotors();
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = static_cast<char>(Serial.read());
    if (incoming == '\n' || incoming == '\r') {
      if (!serialBuffer.isEmpty()) {
        handleCommand(serialBuffer);
        serialBuffer = "";
      }
      continue;
    }

    serialBuffer += incoming;
  }
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

  Serial.println("COCOMAG_DONE");
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
