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
constexpr int ULTRA_TRIG_PIN = 33;
constexpr int ULTRA_ECHO_PIN = 32;
constexpr bool MOTOR_A_INVERTED = false;
constexpr bool MOTOR_B_INVERTED = true;

constexpr int MOVE_SPEED = 220;
constexpr int TURN_SPEED = 180;
constexpr int RAMP_START_SPEED = 140;
constexpr int RAMP_STEP_COUNT = 4;
constexpr unsigned long RAMP_STEP_DELAY_MS = 25;
constexpr unsigned long SOFT_STOP_STEP_DELAY_MS = 20;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;
constexpr unsigned long PRESENT_FORWARD_MS = 2000;
constexpr unsigned long PRESENT_BACKWARD_MS = 1500;
constexpr int SERVO_REST_ANGLE = 140;
constexpr int SERVO_PICKUP_ANGLE = 0;
constexpr int SERVO_PARTIAL_RETURN_ANGLE = 90;
constexpr unsigned long ACTION_FORWARD_MS = 3000;
constexpr float ACTION_TURN_DEGREES = 90.0f;
constexpr unsigned long ACTION_POST_TURN_FORWARD_MS = 1000;
constexpr unsigned long SERVO_LOWER_DURATION_MS = 1800;
constexpr unsigned long SERVO_PICKUP_HOLD_MS = 1000;
constexpr float GYRO_Z_LSB_PER_DPS = 131.0f;
constexpr float PRESENT_TARGET_DEGREES = 360.0f;
constexpr float GYRO_ANGLE_SCALE = 1.0f;
constexpr unsigned long ROTATION_TIMEOUT_MS = 6000;
constexpr unsigned long GYRO_CALIBRATION_SAMPLES = 120;
constexpr unsigned long GYRO_SAMPLE_DELAY_MS = 5;
constexpr float GYRO_NOISE_FLOOR_DPS = 2.0f;
constexpr unsigned long GYRO_DEBUG_LOG_INTERVAL_MS = 250;
constexpr float ROTATION_SLOWDOWN_WINDOW_DEGREES = 45.0f;
constexpr int TURN_SLOW_SPEED = 140;
constexpr float ULTRA_TRIGGER_DISTANCE_CM = 6.0f;
constexpr float ULTRA_RELEASE_DISTANCE_CM = 10.0f;
constexpr unsigned long ULTRA_READ_INTERVAL_MS = 50;
constexpr unsigned long ULTRA_PULSE_TIMEOUT_US = 25000UL;

String serialBuffer;
String bluetoothBuffer;
bool isPresenting = false;
bool mpuReady = false;
bool bluetoothReady = false;
float gyroZBiasDps = 0.0f;
unsigned long lastUltraReadAtMs = 0;
bool ultraPresenceLatched = false;
Servo actionServo;
MPU6050 mpu;
#if COCOMAG_BT_AVAILABLE
BluetoothSerial SerialBT;
#endif

enum class LocalStage : uint8_t {
  READY_FOR_PRESENT = 0,
  READY_FOR_ACTION = 1,
  COMPLETED = 2,
};

LocalStage localStage = LocalStage::READY_FOR_PRESENT;

void setMotorA(bool forward, int speedValue);
void setMotorB(bool forward, int speedValue);
void applyDrive(bool motorAForward, int motorASpeed, bool motorBForward, int motorBSpeed);
void rampDrive(bool motorAForward, bool motorBForward, int targetSpeed);
void softStopDrive(bool motorAForward, bool motorBForward, int currentSpeed);
void moveForward();
void moveBackward();
void turnRight();
void turnRightAtSpeed(int speedValue);
void stopMotors();
bool runPresentation();
bool runAction();
void performPickupMotion();
bool initializeMpu();
bool calibrateGyroBias();
bool rotateDegrees(float targetDegrees);
void handleCommand(const String& command);
void readCommandStream(Stream& stream, String& buffer);
void emitLine(const char* message);
float readUltrasonicDistanceCm();
void handleUltrasonicFallback();
void executePresentationFrom(const char* origin);
void executeActionFrom(const char* origin);

void setup() {
  Serial.begin(115200);
  Serial.println("BOOT_1");
#if COCOMAG_BT_AVAILABLE
  bluetoothReady = SerialBT.begin("COCOMAG");
  Serial.println(bluetoothReady ? "BT_BEGIN_OK" : "BT_BEGIN_FAILED");
  delay(250);
#else
  Serial.println("BT_UNAVAILABLE");
#endif
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setTimeOut(50);
  Serial.println("WIRE_BEGIN_OK");

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ULTRA_TRIG_PIN, OUTPUT);
  pinMode(ULTRA_ECHO_PIN, INPUT);
  digitalWrite(ULTRA_TRIG_PIN, LOW);

  stopMotors();
  actionServo.setPeriodHertz(50);
  actionServo.attach(SERVO_PIN, 500, 2400);
  actionServo.write(SERVO_REST_ANGLE);
  Serial.println("SERVO_INIT_OK");
  mpuReady = initializeMpu();
  Serial.println(mpuReady ? "MPU_INIT_OK" : "MPU_INIT_FAILED");
  Serial.println("SETUP_DONE");
}

void loop() {
  readCommandStream(Serial, serialBuffer);
#if COCOMAG_BT_AVAILABLE
  if (bluetoothReady) {
    readCommandStream(SerialBT, bluetoothBuffer);
  }
#endif
  handleUltrasonicFallback();
}

void handleCommand(const String& command) {
  String normalized = command;
  normalized.trim();

  if (normalized.isEmpty()) {
    return;
  }

  Serial.print("COCOMAG_CMD=");
  Serial.println(normalized);

  if (isPresenting) {
    Serial.println("COCOMAG_BT_IGNORED_BUSY");
    return;
  }

  if (normalized == "COCOMAG:PRESENT") {
    if (localStage == LocalStage::READY_FOR_PRESENT) {
      executePresentationFrom("BT");
    } else {
      Serial.println("COCOMAG_BT_IGNORED_PRESENT");
    }
    return;
  }

  if (normalized == "COCOMAG:ACTION") {
    if (localStage == LocalStage::READY_FOR_ACTION) {
      executeActionFrom("BT");
    } else {
      Serial.println("COCOMAG_BT_IGNORED_ACTION");
    }
  }
}

void executePresentationFrom(const char* origin) {
  Serial.print("COCOMAG_");
  Serial.print(origin);
  Serial.println("_PRESENT");
  isPresenting = true;
  bool completed = runPresentation();
  isPresenting = false;
  if (completed) {
    localStage = LocalStage::READY_FOR_ACTION;
    return;
  }

  Serial.print("COCOMAG_");
  Serial.print(origin);
  Serial.println("_PRESENT_FAILED");
}

void executeActionFrom(const char* origin) {
  Serial.print("COCOMAG_");
  Serial.print(origin);
  Serial.println("_ACTION");
  isPresenting = true;
  bool completed = runAction();
  isPresenting = false;
  if (completed) {
    localStage = LocalStage::COMPLETED;
    return;
  }

  Serial.print("COCOMAG_");
  Serial.print(origin);
  Serial.println("_ACTION_FAILED");
}

bool runPresentation() {
  moveForward();
  delay(PRESENT_FORWARD_MS);

  softStopDrive(true, true, MOVE_SPEED);
  delay(STOP_MS);

  if (!rotateDegrees(PRESENT_TARGET_DEGREES)) {
    return false;
  }
  delay(STOP_MS);

  moveBackward();
  delay(PRESENT_BACKWARD_MS);

  softStopDrive(false, false, MOVE_SPEED);
  delay(STOP_MS);

  emitLine("COCOMAG_DONE");
  return true;
}

bool runAction() {
  moveForward();
  delay(ACTION_FORWARD_MS);

  softStopDrive(true, true, MOVE_SPEED);
  delay(STOP_MS);

  if (!rotateDegrees(ACTION_TURN_DEGREES)) {
    return false;
  }
  delay(STOP_MS);

  moveForward();
  delay(ACTION_POST_TURN_FORWARD_MS);

  softStopDrive(true, true, MOVE_SPEED);
  delay(STOP_MS);

  emitLine("COCOMAG_DONE");
  return true;
}

void performPickupMotion() {
  actionServo.write(SERVO_REST_ANGLE);
  delay(STOP_MS);
  actionServo.write(SERVO_PICKUP_ANGLE);
  delay(SERVO_PICKUP_HOLD_MS);
  actionServo.write(SERVO_PARTIAL_RETURN_ANGLE);
  delay(STOP_MS);
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
  int currentTurnSpeed = TURN_SPEED;

  Serial.print("ROTATION_START target=");
  Serial.println(targetDegrees, 1);
  turnRight();
  while (accumulatedDegrees < targetDegrees) {
    unsigned long nowMicros = micros();
    float deltaSeconds = (nowMicros - lastSampleAt) / 1000000.0f;
    lastSampleAt = nowMicros;

    float gyroZDps = (mpu.getRotationZ() / GYRO_Z_LSB_PER_DPS) - gyroZBiasDps;
    if (fabsf(gyroZDps) >= GYRO_NOISE_FLOOR_DPS) {
      float deltaDegrees = fabsf(gyroZDps) * deltaSeconds * GYRO_ANGLE_SCALE;
      accumulatedDegrees += deltaDegrees;
    }

    float remainingDegrees = targetDegrees - accumulatedDegrees;
    if (currentTurnSpeed == TURN_SPEED && remainingDegrees <= ROTATION_SLOWDOWN_WINDOW_DEGREES) {
      currentTurnSpeed = TURN_SLOW_SPEED;
      turnRightAtSpeed(currentTurnSpeed);
    }

    if (millis() - lastDebugLogAt >= GYRO_DEBUG_LOG_INTERVAL_MS) {
      lastDebugLogAt = millis();
      Serial.print("ROTATION_PROGRESS angle=");
      Serial.print(accumulatedDegrees, 1);
      Serial.print(" gyroZ=");
      Serial.println(gyroZDps, 1);
    }

    if (millis() - startedAt > ROTATION_TIMEOUT_MS) {
      softStopDrive(true, false, currentTurnSpeed);
      Serial.print("ROTATION_TIMEOUT angle=");
      Serial.print(accumulatedDegrees, 1);
      Serial.print(" target=");
      Serial.print(targetDegrees, 1);
      Serial.print(" elapsed=");
      Serial.println(millis() - startedAt);
      emitLine("COCOMAG_MPU_ROTATION_TIMEOUT");
      Serial.println("ROTATION_STOP");
      return false;
    }

    delay(2);
  }

  Serial.print("ROTATION_REACHED angle=");
  Serial.println(accumulatedDegrees, 1);
  softStopDrive(true, false, currentTurnSpeed);
  Serial.println("ROTATION_STOP");
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
  if (bluetoothReady && SerialBT.hasClient()) {
    SerialBT.println(message);
  }
#endif
}

void moveForward() {
  rampDrive(true, true, MOVE_SPEED);
}

void moveBackward() {
  rampDrive(false, false, MOVE_SPEED);
}

void turnRight() {
  rampDrive(true, false, TURN_SPEED);
}

void turnRightAtSpeed(int speedValue) {
  applyDrive(true, speedValue, false, speedValue);
}

void stopMotors() {
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}

void applyDrive(bool motorAForward, int motorASpeed, bool motorBForward, int motorBSpeed) {
  setMotorA(motorAForward, motorASpeed);
  setMotorB(motorBForward, motorBSpeed);
}

void rampDrive(bool motorAForward, bool motorBForward, int targetSpeed) {
  for (int step = 1; step <= RAMP_STEP_COUNT; ++step) {
    int speedValue = RAMP_START_SPEED + ((targetSpeed - RAMP_START_SPEED) * step) / RAMP_STEP_COUNT;
    applyDrive(motorAForward, speedValue, motorBForward, speedValue);
    delay(RAMP_STEP_DELAY_MS);
  }
}

float readUltrasonicDistanceCm() {
  digitalWrite(ULTRA_TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRA_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRA_TRIG_PIN, LOW);

  unsigned long pulseDurationUs = pulseIn(ULTRA_ECHO_PIN, HIGH, ULTRA_PULSE_TIMEOUT_US);
  if (pulseDurationUs == 0) {
    return -1.0f;
  }

  return pulseDurationUs / 58.0f;
}

void handleUltrasonicFallback() {
  if (isPresenting) {
    return;
  }

  unsigned long nowMs = millis();
  if (nowMs - lastUltraReadAtMs < ULTRA_READ_INTERVAL_MS) {
    return;
  }
  lastUltraReadAtMs = nowMs;

  float distanceCm = readUltrasonicDistanceCm();
  bool triggerActive = distanceCm > 0.0f && distanceCm <= ULTRA_TRIGGER_DISTANCE_CM;
  bool releaseActive = distanceCm < 0.0f || distanceCm >= ULTRA_RELEASE_DISTANCE_CM;

  if (releaseActive) {
    ultraPresenceLatched = false;
  }

  if (!triggerActive || ultraPresenceLatched) {
    return;
  }
  ultraPresenceLatched = true;

  if (localStage == LocalStage::READY_FOR_PRESENT) {
    executePresentationFrom("ULTRA");
    return;
  }

  if (localStage == LocalStage::READY_FOR_ACTION) {
    executeActionFrom("ULTRA");
    return;
  }

  Serial.println("ULTRA_IGNORED_COMPLETED");
}

void softStopDrive(bool motorAForward, bool motorBForward, int currentSpeed) {
  for (int step = RAMP_STEP_COUNT; step >= 1; --step) {
    int speedValue = RAMP_START_SPEED + ((currentSpeed - RAMP_START_SPEED) * step) / RAMP_STEP_COUNT;
    applyDrive(motorAForward, speedValue, motorBForward, speedValue);
    delay(SOFT_STOP_STEP_DELAY_MS);
  }
  stopMotors();
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
