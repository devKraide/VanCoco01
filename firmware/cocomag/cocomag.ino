#include <Arduino.h>
#include <BluetoothSerial.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <MPU6050.h>

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
constexpr int I2C_SDA_PIN = 21;
constexpr int I2C_SCL_PIN = 22;
constexpr bool MOTOR_A_INVERTED = false;
constexpr bool MOTOR_B_INVERTED = true;

constexpr int MOTOR_SPEED = 180;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;
constexpr unsigned long PRESENT_FORWARD_MS = 2000;
constexpr unsigned long PRESENT_BACKWARD_MS = 2000;
constexpr int SERVO_REST_ANGLE = 0;
constexpr int SERVO_LEFT_ANGLE = 20;
constexpr int SERVO_RIGHT_ANGLE = 160;
constexpr unsigned long ACTION_FORWARD_MS = 3000;
constexpr unsigned long ACTION_BACKWARD_MS = 3000;
constexpr unsigned long SERVO_SWING_HOLD_MS = 450;
constexpr unsigned long SERVO_HOLD_MS = 700;
constexpr float GYRO_Z_LSB_PER_DPS = 131.0f;
constexpr float PRESENT_TARGET_DEGREES = 360.0f;
constexpr float GYRO_ANGLE_CORRECTION = 1.33f;
constexpr unsigned long ROTATION_TIMEOUT_MS = 6000;
constexpr unsigned long GYRO_CALIBRATION_SAMPLES = 120;
constexpr unsigned long GYRO_SAMPLE_DELAY_MS = 5;
constexpr float GYRO_NOISE_FLOOR_DPS = 2.0f;
constexpr unsigned long GYRO_DEBUG_LOG_INTERVAL_MS = 250;

String serialBuffer;
String bluetoothBuffer;
bool isPresenting = false;
bool mpuReady = false;
float gyroZBiasDps = 0.0f;
Servo actionServo;
MPU6050 mpu;
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
void swingServoBetweenExtremes(unsigned int cycles);
bool initializeMpu();
bool calibrateGyroBias();
bool rotateDegrees(float targetDegrees);
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
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

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
  mpuReady = initializeMpu();
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
  delay(PRESENT_FORWARD_MS);

  stopMotors();
  delay(STOP_MS);

  rotateDegrees(PRESENT_TARGET_DEGREES);

  stopMotors();
  delay(STOP_MS);

  moveBackward();
  delay(PRESENT_BACKWARD_MS);

  stopMotors();
  delay(STOP_MS);

  emitLine("COCOMAG_DONE");
}

void runAction() {
  moveForward();
  delay(ACTION_FORWARD_MS);

  stopMotors();
  delay(STOP_MS);

  swingServoBetweenExtremes(2);

  actionServo.write(SERVO_REST_ANGLE);
  delay(STOP_MS);

  moveBackward();
  delay(ACTION_BACKWARD_MS);

  stopMotors();
  delay(STOP_MS);

  emitLine("COCOMAG_DONE");
}

void swingServoBetweenExtremes(unsigned int cycles) {
  for (unsigned int cycle = 0; cycle < cycles; ++cycle) {
    actionServo.write(SERVO_LEFT_ANGLE);
    delay(SERVO_SWING_HOLD_MS);

    actionServo.write(SERVO_RIGHT_ANGLE);
    delay(SERVO_SWING_HOLD_MS);
  }
}

bool initializeMpu() {
  mpu.initialize();
  mpu.setFullScaleGyroRange(MPU6050_GYRO_FS_250);
  if (!mpu.testConnection()) {
    emitLine("COCOMAG_MPU_NOT_FOUND");
    return false;
  }

  if (!calibrateGyroBias()) {
    emitLine("COCOMAG_MPU_CALIBRATION_FAILED");
    return false;
  }

  emitLine("COCOMAG_MPU_READY");
  return true;
}

bool calibrateGyroBias() {
  long accumulatedZ = 0;
  for (unsigned long index = 0; index < GYRO_CALIBRATION_SAMPLES; ++index) {
    accumulatedZ += mpu.getRotationZ();
    delay(GYRO_SAMPLE_DELAY_MS);
  }

  gyroZBiasDps = (accumulatedZ / static_cast<float>(GYRO_CALIBRATION_SAMPLES)) / GYRO_Z_LSB_PER_DPS;
  return true;
}

bool rotateDegrees(float targetDegrees) {
  if (!mpuReady) {
    emitLine("COCOMAG_MPU_UNAVAILABLE");
    return false;
  }

  stopMotors();
  delay(STOP_MS);
  if (!calibrateGyroBias()) {
    emitLine("COCOMAG_MPU_RECALIBRATION_FAILED");
    return false;
  }

  unsigned long startedAt = millis();
  unsigned long lastSampleAt = micros();
  unsigned long lastDebugLogAt = millis();
  float accumulatedDegrees = 0.0f;

  turnRight();
  while (accumulatedDegrees < targetDegrees) {
    unsigned long nowMicros = micros();
    float deltaSeconds = (nowMicros - lastSampleAt) / 1000000.0f;
    lastSampleAt = nowMicros;

    float gyroZDps = (mpu.getRotationZ() / GYRO_Z_LSB_PER_DPS) - gyroZBiasDps;
    if (fabsf(gyroZDps) >= GYRO_NOISE_FLOOR_DPS) {
      float deltaDegrees = fabsf(gyroZDps) * deltaSeconds * GYRO_ANGLE_CORRECTION;
      accumulatedDegrees += deltaDegrees;
    }

    if (millis() - lastDebugLogAt >= GYRO_DEBUG_LOG_INTERVAL_MS) {
      lastDebugLogAt = millis();
      Serial.print("COCOMAG_MPU_Z_DPS=");
      Serial.print(gyroZDps, 1);
      Serial.print(" ANGLE=");
      Serial.println(accumulatedDegrees, 1);
#if COCOMAG_BT_AVAILABLE
      if (SerialBT.hasClient()) {
        SerialBT.print("COCOMAG_MPU_Z_DPS=");
        SerialBT.print(gyroZDps, 1);
        SerialBT.print(" ANGLE=");
        SerialBT.println(accumulatedDegrees, 1);
      }
#endif
    }

    if (millis() - startedAt > ROTATION_TIMEOUT_MS) {
      stopMotors();
      emitLine("COCOMAG_MPU_ROTATION_TIMEOUT");
      return false;
    }

    delay(2);
  }

  stopMotors();
  Serial.print("COCOMAG_MPU_ROTATION_DEGREES=");
  Serial.println(accumulatedDegrees, 1);
#if COCOMAG_BT_AVAILABLE
  if (SerialBT.hasClient()) {
    SerialBT.print("COCOMAG_MPU_ROTATION_DEGREES=");
    SerialBT.println(accumulatedDegrees, 1);
  }
#endif
  return true;
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
  bool physicalForward = MOTOR_A_INVERTED ? !forward : forward;
  digitalWrite(IN1, physicalForward ? HIGH : LOW);
  digitalWrite(IN2, physicalForward ? LOW : HIGH);
  analogWrite(ENA, speedValue);
}

void setMotorB(bool forward, int speedValue) {
  bool physicalForward = MOTOR_B_INVERTED ? !forward : forward;
  digitalWrite(IN3, physicalForward ? HIGH : LOW);
  digitalWrite(IN4, physicalForward ? LOW : HIGH);
  analogWrite(ENB, speedValue);
}
