#include <Arduino.h>
#include <BluetoothSerial.h>
#include <Wire.h>
#include <Adafruit_TCS34725.h>
#include <MPU6050.h>

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
constexpr int MOVE_SPEED = 220;
constexpr int TURN_SPEED = 210;
constexpr int RAMP_START_SPEED = 140;
constexpr int RAMP_STEP_COUNT = 4;
constexpr unsigned long RAMP_STEP_DELAY_MS = 25;
constexpr unsigned long SOFT_STOP_STEP_DELAY_MS = 20;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;
constexpr unsigned long PRESENT_FORWARD_MS = 2000;
constexpr unsigned long PRESENT_BACKWARD_MS = 2000;
constexpr unsigned long ACTION_FORWARD_MS = 1500;
constexpr unsigned long RETURN_BACKWARD_MS = 1500;
constexpr float GYRO_Z_LSB_PER_DPS = 131.0f;
constexpr float PRESENT_TARGET_DEGREES = 360.0f;
constexpr float GYRO_ANGLE_SCALE = 0.75f;
constexpr unsigned long ROTATION_TIMEOUT_MS = 6000;
constexpr unsigned long GYRO_CALIBRATION_SAMPLES = 120;
constexpr unsigned long GYRO_SAMPLE_DELAY_MS = 5;
constexpr float GYRO_NOISE_FLOOR_DPS = 2.0f;

Adafruit_TCS34725 tcs =
    Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_50MS, TCS34725_GAIN_4X);

String lastColor = "";
String serialBuffer = "";
String bluetoothBuffer = "";
unsigned long lastSentAt = 0;
bool isPresenting = false;
bool sensorActive = false;
bool mpuReady = false;
float gyroZBiasDps = 0.0f;
MPU6050 mpu;
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
bool initializeMpu();
bool calibrateGyroBias();
bool rotateDegrees(float targetDegrees);
void applyDrive(bool motorAForward, int motorASpeed, bool motorBForward, int motorBSpeed);
void rampDrive(bool motorAForward, bool motorBForward, int targetSpeed);
void softStopDrive(bool motorAForward, bool motorBForward, int currentSpeed);
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
  Wire.setTimeOut(50);
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
  Serial.println("TCS34725_READY");

  mpuReady = initializeMpu();
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

  Serial.print("COCOVISION_CMD=");
  Serial.println(normalized);

  if (normalized == "COCOVISION:PRESENT") {
    Serial.println("COCOVISION_RUN_PRESENT");
    isPresenting = true;
    runPresentation();
    isPresenting = false;
    return;
  }

  if (normalized == "COCOVISION:ACTION") {
    Serial.println("COCOVISION_RUN_ACTION");
    isPresenting = true;
    runAction();
    isPresenting = false;
    return;
  }

  if (normalized == "COCOVISION:RETURN") {
    Serial.println("COCOVISION_RUN_RETURN");
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
  delay(PRESENT_FORWARD_MS);

  softStopDrive(true, true, MOVE_SPEED);
  delay(STOP_MS);

  rotateDegrees(PRESENT_TARGET_DEGREES);
  delay(STOP_MS);

  moveBackward();
  delay(PRESENT_BACKWARD_MS);

  softStopDrive(false, false, MOVE_SPEED);
  delay(STOP_MS);

  emitLine("COCOVISION_DONE");
}

void runAction() {
  moveForward();
  delay(ACTION_FORWARD_MS);

  softStopDrive(true, true, MOVE_SPEED);
  delay(STOP_MS);

  sensorActive = true;
  lastColor = "";
  lastSentAt = 0;
  emitLine("COCOVISION_DONE");
}

void runReturn() {
  sensorActive = false;
  moveBackward();
  delay(RETURN_BACKWARD_MS);

  softStopDrive(false, false, MOVE_SPEED);
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

bool initializeMpu() {
  mpu.initialize();
  mpu.setFullScaleGyroRange(MPU6050_GYRO_FS_250);
  if (!mpu.testConnection()) {
    emitLine("COCOVISION_MPU_NOT_FOUND");
    return false;
  }

  if (!calibrateGyroBias()) {
    emitLine("COCOVISION_MPU_CALIBRATION_FAILED");
    return false;
  }

  emitLine("COCOVISION_MPU_READY");
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
    emitLine("COCOVISION_MPU_UNAVAILABLE");
    return false;
  }

  stopMotors();
  delay(STOP_MS);
  if (!calibrateGyroBias()) {
    emitLine("COCOVISION_MPU_RECALIBRATION_FAILED");
    return false;
  }

  unsigned long startedAt = millis();
  unsigned long lastSampleAt = micros();
  float accumulatedDegrees = 0.0f;

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

    if (millis() - startedAt > ROTATION_TIMEOUT_MS) {
      softStopDrive(true, false, TURN_SPEED);
      emitLine("COCOVISION_MPU_ROTATION_TIMEOUT");
      return false;
    }

    delay(2);
  }

  softStopDrive(true, false, TURN_SPEED);
  return true;
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

void softStopDrive(bool motorAForward, bool motorBForward, int currentSpeed) {
  for (int step = RAMP_STEP_COUNT; step >= 1; --step) {
    int speedValue = RAMP_START_SPEED + ((currentSpeed - RAMP_START_SPEED) * step) / RAMP_STEP_COUNT;
    applyDrive(motorAForward, speedValue, motorBForward, speedValue);
    delay(SOFT_STOP_STEP_DELAY_MS);
  }
  stopMotors();
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
