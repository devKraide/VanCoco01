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
constexpr int ULTRASONIC_ECHO_PIN = 32;
constexpr int ULTRASONIC_TRIG_PIN = 33;
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
constexpr unsigned long ACTION_FORWARD_MS = 1500;
constexpr unsigned long RETURN_BACKWARD_MS = 1500;
constexpr float GYRO_Z_LSB_PER_DPS = 131.0f;
constexpr float PRESENT_TARGET_DEGREES = 360.0f;
constexpr float GYRO_ANGLE_SCALE = 1.125f;
constexpr float ROTATION_COMPLETION_TOLERANCE_DEGREES = 3.0f;
constexpr unsigned long ROTATION_TIMEOUT_MS = 6000;
constexpr unsigned long PRESENT_ROTATION_TIMEOUT_MS = 12000;
constexpr unsigned long GYRO_STATIONARY_DIAGNOSTIC_MS = 1000;
constexpr unsigned long GYRO_CALIBRATION_SAMPLES = 120;
constexpr unsigned long GYRO_SAMPLE_DELAY_MS = 5;
constexpr float GYRO_NOISE_FLOOR_DPS = 2.0f;
constexpr unsigned long GYRO_DEBUG_LOG_INTERVAL_MS = 250;
constexpr unsigned long GYRO_STATIONARY_LOG_INTERVAL_MS = 250;
constexpr float ULTRASONIC_TRIGGER_DISTANCE_CM = 6.0f;
constexpr float ULTRASONIC_RELEASE_DISTANCE_CM = 10.0f;
constexpr unsigned long ULTRASONIC_PULSE_TIMEOUT_US = 25000UL;
constexpr unsigned long ULTRASONIC_SAMPLE_INTERVAL_MS = 60;

Adafruit_TCS34725 tcs =
    Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_50MS, TCS34725_GAIN_4X);

String lastColor = "";
String bluetoothBuffer = "";
unsigned long lastSentAt = 0;
unsigned long lastUltrasonicSampleAt = 0;
bool isPresenting = false;
bool sensorActive = false;
bool resetRequested = false;
bool mpuReady = false;
bool ultrasonicPresenceLatched = false;
bool colorAlreadySent = false;
float gyroZBiasDps = 0.0f;
MPU6050 mpu;
#if COCOVISION_BT_AVAILABLE
BluetoothSerial SerialBT;
#endif

enum class LocalStage : uint8_t {
  READY_FOR_PRESENT = 0,
  READY_FOR_ACTION = 1,
  WAITING_FOR_COLOR = 2,
  READY_FOR_RETURN = 3,
  COMPLETED = 4,
};

enum class RequestedCommand : uint8_t {
  ANY = 0,
  PRESENT = 1,
  ACTION = 2,
  RETURN = 3,
  COLOR_BLUE = 4,
  COLOR_CONFIRMED = 5,
};

LocalStage localStage = LocalStage::READY_FOR_PRESENT;

String detectDominantColor(uint16_t red, uint16_t green, uint16_t blue, uint16_t clear);
void publishColorIfNeeded(const String& colorName);
void handleCommand(const String& command);
void readCommandStream(Stream& stream, String& buffer);
void emitLine(const char* message);
const char* stageToString(LocalStage stage);
void logIgnoredTrigger(const char* source);
void handleTrigger(const char* source, RequestedCommand requestedCommand);
void handleResetCommand();
bool applyReset();
bool pollBluetoothCommands();
bool delayWithReset(unsigned long durationMs);
bool shouldAbortForReset();
void executePresentationFrom(const char* origin);
void executeActionFrom(const char* origin);
void executeReturnFrom(const char* origin);
bool runPresentation();
bool runAction();
bool runReturn();
bool initializeMpu();
bool calibrateGyroBias();
bool rotateDegrees(float targetDegrees);
bool rotateDegrees(float targetDegrees, unsigned long timeoutMs, bool logStationaryDiagnostic);
void logStationaryGyro(unsigned long durationMs);
void applyDrive(bool motorAForward, int motorASpeed, bool motorBForward, int motorBSpeed);
void rampDrive(bool motorAForward, bool motorBForward, int targetSpeed);
void softStopDrive(bool motorAForward, bool motorBForward, int currentSpeed);
void moveForward();
void moveBackward();
void turnRight();
void turnRightAtSpeed(int speedValue);
void stopMotors();
void setMotorA(bool forward, int speedValue);
void setMotorB(bool forward, int speedValue);
float readUltrasonicDistanceCm();
void handleUltrasonicFallback();

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
  pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ULTRASONIC_ECHO_PIN, INPUT);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
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
  while (Serial.available() > 0) {
    Serial.read();
  }
#if COCOVISION_BT_AVAILABLE
  readCommandStream(SerialBT, bluetoothBuffer);
#endif
  handleUltrasonicFallback();

  if (isPresenting) {
    return;
  }

  if (!sensorActive || localStage != LocalStage::WAITING_FOR_COLOR) {
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

  if (normalized.isEmpty()) {
    return;
  }

  Serial.print("COCOVISION_CMD=");
  Serial.println(normalized);

  if (normalized == "COCOVISION:PRESENT") {
    handleTrigger("BT", RequestedCommand::PRESENT);
    return;
  }

  if (normalized == "COCOVISION:ACTION") {
    handleTrigger("BT", RequestedCommand::ACTION);
    return;
  }

  if (normalized == "COCOVISION:RETURN") {
    handleTrigger("BT", RequestedCommand::RETURN);
    return;
  }

  if (normalized == "COCOVISION:COLOR_CONFIRMED") {
    handleTrigger("BT", RequestedCommand::COLOR_CONFIRMED);
    return;
  }

  if (normalized == "COCOVISION:RESET") {
    handleResetCommand();
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
  if (colorName != "COLOR_BLUE") {
    return;
  }

  if (colorAlreadySent) {
    return;
  }

  unsigned long now = millis();
  bool isDebounced = colorName == lastColor && (now - lastSentAt) < DETECTION_DEBOUNCE_MS;
  if (isDebounced) {
    return;
  }

  handleTrigger("COLOR", RequestedCommand::COLOR_BLUE);
  lastColor = colorName;
  lastSentAt = now;
}

const char* stageToString(LocalStage stage) {
  switch (stage) {
    case LocalStage::READY_FOR_PRESENT:
      return "READY_FOR_PRESENT";
    case LocalStage::READY_FOR_ACTION:
      return "READY_FOR_ACTION";
    case LocalStage::WAITING_FOR_COLOR:
      return "WAITING_FOR_COLOR";
    case LocalStage::READY_FOR_RETURN:
      return "READY_FOR_RETURN";
    case LocalStage::COMPLETED:
      return "COMPLETED";
  }

  return "UNKNOWN";
}

void logIgnoredTrigger(const char* source) {
  Serial.print(source);
  Serial.print("_IGNORED_STATE=");
  Serial.println(stageToString(localStage));
  Serial.print("IGNORED_STATE=");
  Serial.println(stageToString(localStage));
}

void handleTrigger(const char* source, RequestedCommand requestedCommand) {
  Serial.print("STATE_CURRENT=");
  Serial.println(stageToString(localStage));
  Serial.print("TRIGGER_SOURCE=");
  Serial.println(source);

  if (requestedCommand == RequestedCommand::COLOR_CONFIRMED && localStage != LocalStage::WAITING_FOR_COLOR) {
    Serial.println("COLOR_CONFIRMED_IGNORED_STATE");
    logIgnoredTrigger(source);
    return;
  }

  if (isPresenting) {
    logIgnoredTrigger(source);
    return;
  }

  if (localStage == LocalStage::READY_FOR_PRESENT) {
    if (requestedCommand == RequestedCommand::ACTION || requestedCommand == RequestedCommand::RETURN || requestedCommand == RequestedCommand::COLOR_BLUE) {
      logIgnoredTrigger(source);
      return;
    }

    executePresentationFrom(source);
    return;
  }

  if (localStage == LocalStage::READY_FOR_ACTION) {
    if (requestedCommand == RequestedCommand::PRESENT || requestedCommand == RequestedCommand::RETURN || requestedCommand == RequestedCommand::COLOR_BLUE) {
      logIgnoredTrigger(source);
      return;
    }

    executeActionFrom(source);
    return;
  }

  if (localStage == LocalStage::WAITING_FOR_COLOR) {
    if (requestedCommand == RequestedCommand::COLOR_CONFIRMED) {
      sensorActive = false;
      colorAlreadySent = true;
      localStage = LocalStage::READY_FOR_RETURN;
      Serial.println("COLOR_CONFIRMED_ACCEPTED");
      emitLine("COCOVISION_COLOR_CONFIRMED_DONE");
      return;
    }

    if (requestedCommand != RequestedCommand::COLOR_BLUE && requestedCommand != RequestedCommand::ANY) {
      logIgnoredTrigger(source);
      return;
    }

    if (colorAlreadySent) {
      logIgnoredTrigger(source);
      return;
    }

    Serial.println("COLOR_DETECTED");
    emitLine("COLOR_BLUE");
    colorAlreadySent = true;
    sensorActive = false;
    localStage = LocalStage::READY_FOR_RETURN;
    return;
  }

  if (localStage == LocalStage::READY_FOR_RETURN) {
    if (requestedCommand == RequestedCommand::PRESENT || requestedCommand == RequestedCommand::ACTION || requestedCommand == RequestedCommand::COLOR_BLUE) {
      logIgnoredTrigger(source);
      return;
    }

    executeReturnFrom(source);
    return;
  }

  logIgnoredTrigger(source);
}

void handleResetCommand() {
  Serial.println("RESET_RECEIVED");
  bool resetCompleted = applyReset();
  if (resetCompleted) {
    emitLine("COCOVISION_RESET_DONE");
    Serial.println("RESET_DONE");
    return;
  }

  emitLine("COCOVISION_RESET_REQUESTED");
  Serial.println("RESET_REQUESTED");
}

bool applyReset() {
  stopMotors();
  ultrasonicPresenceLatched = false;

  if (isPresenting) {
    resetRequested = true;
    Serial.println("RESET_REQUESTED");
    return false;
  }

  resetRequested = false;
  isPresenting = false;
  sensorActive = false;
  colorAlreadySent = false;
  lastColor = "";
  lastSentAt = 0;
  localStage = LocalStage::READY_FOR_PRESENT;
  Serial.println("RESET_DONE");
  return true;
}

bool pollBluetoothCommands() {
#if COCOVISION_BT_AVAILABLE
  readCommandStream(SerialBT, bluetoothBuffer);
#endif
  return resetRequested;
}

bool delayWithReset(unsigned long durationMs) {
  unsigned long startedAt = millis();
  while (millis() - startedAt < durationMs) {
    if (pollBluetoothCommands()) {
      stopMotors();
      return false;
    }
    delay(5);
  }

  return true;
}

bool shouldAbortForReset() {
  if (!resetRequested) {
    pollBluetoothCommands();
  }

  if (!resetRequested) {
    return false;
  }

  stopMotors();
  return true;
}

void executePresentationFrom(const char* origin) {
  Serial.print("COCOVISION_");
  Serial.print(origin);
  Serial.println("_PRESENT");
  resetRequested = false;
  isPresenting = true;
  bool completed = runPresentation();
  isPresenting = false;
  if (resetRequested) {
    Serial.println("PRESENT_ABORTED_BY_RESET");
    resetRequested = false;
    localStage = LocalStage::READY_FOR_PRESENT;
    emitLine("COCOVISION_RESET_DONE");
    Serial.println("RESET_DONE");
    return;
  }

  if (completed) {
    localStage = LocalStage::READY_FOR_ACTION;
    return;
  }

  Serial.print("COCOVISION_");
  Serial.print(origin);
  Serial.println("_PRESENT_FAILED");
}

void executeActionFrom(const char* origin) {
  Serial.print("COCOVISION_");
  Serial.print(origin);
  Serial.println("_ACTION");
  resetRequested = false;
  isPresenting = true;
  bool completed = runAction();
  isPresenting = false;
  if (resetRequested) {
    Serial.println("ACTION_ABORTED_BY_RESET");
    resetRequested = false;
    localStage = LocalStage::READY_FOR_PRESENT;
    emitLine("COCOVISION_RESET_DONE");
    Serial.println("RESET_DONE");
    return;
  }

  if (completed) {
    localStage = LocalStage::WAITING_FOR_COLOR;
    return;
  }

  Serial.print("COCOVISION_");
  Serial.print(origin);
  Serial.println("_ACTION_FAILED");
}

void executeReturnFrom(const char* origin) {
  Serial.print("COCOVISION_");
  Serial.print(origin);
  Serial.println("_RETURN");
  resetRequested = false;
  isPresenting = true;
  bool completed = runReturn();
  isPresenting = false;
  if (resetRequested) {
    Serial.println("RETURN_ABORTED_BY_RESET");
    resetRequested = false;
    localStage = LocalStage::READY_FOR_PRESENT;
    emitLine("COCOVISION_RESET_DONE");
    Serial.println("RESET_DONE");
    return;
  }

  if (completed) {
    localStage = LocalStage::COMPLETED;
    return;
  }

  Serial.print("COCOVISION_");
  Serial.print(origin);
  Serial.println("_RETURN_FAILED");
}

bool runPresentation() {
  Serial.println("PRESENT_START");
  Serial.println("PRESENT_FORWARD_START");
  moveForward();
  if (!delayWithReset(PRESENT_FORWARD_MS)) {
    return false;
  }
  Serial.println("PRESENT_FORWARD_END");

  softStopDrive(true, true, MOVE_SPEED);
  if (!delayWithReset(STOP_MS)) {
    return false;
  }

  Serial.println("PRESENT_ROTATION_START");
  if (!rotateDegrees(PRESENT_TARGET_DEGREES, PRESENT_ROTATION_TIMEOUT_MS, true)) {
    if (resetRequested) {
      return false;
    }
    Serial.println("PRESENT_ROTATION_FAILED_CONTINUING");
  }
  Serial.println("PRESENT_ROTATION_END");
  if (!delayWithReset(STOP_MS)) {
    return false;
  }

  Serial.println("PRESENT_BACKWARD_START");
  moveBackward();
  if (!delayWithReset(PRESENT_BACKWARD_MS)) {
    return false;
  }
  Serial.println("PRESENT_BACKWARD_END");

  softStopDrive(false, false, MOVE_SPEED);
  if (!delayWithReset(STOP_MS)) {
    return false;
  }

  emitLine("COCOVISION_DONE");
  Serial.println("DONE_SENT");
  Serial.println("PRESENT_END");
  return true;
}

bool runAction() {
  Serial.println("ACTION_START");
  moveForward();
  if (!delayWithReset(ACTION_FORWARD_MS)) {
    return false;
  }

  softStopDrive(true, true, MOVE_SPEED);
  if (!delayWithReset(STOP_MS)) {
    return false;
  }

  sensorActive = true;
  colorAlreadySent = false;
  lastColor = "";
  lastSentAt = 0;
  emitLine("COCOVISION_DONE");
  Serial.println("DONE_SENT");
  Serial.println("ACTION_END");
  return true;
}

bool runReturn() {
  Serial.println("RETURN_START");
  sensorActive = false;
  moveBackward();
  if (!delayWithReset(RETURN_BACKWARD_MS)) {
    return false;
  }

  softStopDrive(false, false, MOVE_SPEED);
  if (!delayWithReset(STOP_MS)) {
    return false;
  }

  emitLine("COCOVISION_DONE");
  Serial.println("DONE_SENT");
  Serial.println("RETURN_END");
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
  return rotateDegrees(targetDegrees, ROTATION_TIMEOUT_MS, false);
}

bool rotateDegrees(float targetDegrees, unsigned long timeoutMs, bool logStationaryDiagnostic) {
  if (!mpuReady) {
    emitLine("COCOVISION_MPU_UNAVAILABLE");
    return false;
  }

  stopMotors();
  if (!delayWithReset(STOP_MS)) {
    return false;
  }
  if (logStationaryDiagnostic) {
    logStationaryGyro(GYRO_STATIONARY_DIAGNOSTIC_MS);
    if (resetRequested) {
      return false;
    }
  }

  if (!calibrateGyroBias()) {
    emitLine("COCOVISION_MPU_RECALIBRATION_FAILED");
    return false;
  }
  Serial.print("GYRO_Z_BIAS_DPS=");
  Serial.println(gyroZBiasDps, 4);
  Serial.print("GYRO_UNIT_INFO range=FS_250 raw_lsb_per_dps=");
  Serial.print(GYRO_Z_LSB_PER_DPS, 1);
  Serial.print(" unit=deg_per_sec angle_scale=");
  Serial.println(GYRO_ANGLE_SCALE, 3);

  unsigned long startedAt = millis();
  unsigned long lastSampleAt = micros();
  unsigned long lastDebugLogAt = millis();
  float accumulatedDegrees = 0.0f;
  float completionTargetDegrees = targetDegrees - ROTATION_COMPLETION_TOLERANCE_DEGREES;
  if (completionTargetDegrees < 0.0f) {
    completionTargetDegrees = 0.0f;
  }

  Serial.print("ROTATION_START target=");
  Serial.println(targetDegrees, 1);
  Serial.print("ROTATION_TIMEOUT_MS=");
  Serial.println(timeoutMs);
  Serial.print("ROTATION_COMPLETION_TARGET=");
  Serial.println(completionTargetDegrees, 1);
  Serial.println("ROTATION_ANGLE_RESET=0.0");
  Serial.print("MOTOR_SPIN_START left=FORWARD right=BACKWARD speed=");
  Serial.println(TURN_SPEED);
  turnRightAtSpeed(TURN_SPEED);
  while (accumulatedDegrees < completionTargetDegrees) {
    if (shouldAbortForReset()) {
      Serial.println("ROTATION_ABORTED_BY_RESET");
      return false;
    }

    unsigned long nowMicros = micros();
    float deltaSeconds = (nowMicros - lastSampleAt) / 1000000.0f;
    lastSampleAt = nowMicros;
    unsigned long elapsedMs = millis() - startedAt;

    float gyroZDps = (mpu.getRotationZ() / GYRO_Z_LSB_PER_DPS) - gyroZBiasDps;
    if (fabsf(gyroZDps) >= GYRO_NOISE_FLOOR_DPS) {
      float deltaDegrees = fabsf(gyroZDps) * deltaSeconds * GYRO_ANGLE_SCALE;
      accumulatedDegrees += deltaDegrees;
    }

    if (millis() - lastDebugLogAt >= GYRO_DEBUG_LOG_INTERVAL_MS) {
      lastDebugLogAt = millis();
      Serial.print("ROTATION_PROGRESS angle=");
      Serial.print(accumulatedDegrees, 1);
      Serial.print(" gyroZ=");
      Serial.print(gyroZDps, 2);
      Serial.print(" dt=");
      Serial.print(deltaSeconds, 4);
      Serial.print(" elapsed=");
      Serial.println(elapsedMs);
    }

    if (elapsedMs > timeoutMs) {
      stopMotors();
      Serial.println("MOTOR_STOP");
      Serial.print("ROTATION_TIMEOUT angle=");
      Serial.print(accumulatedDegrees, 1);
      Serial.print(" target=");
      Serial.print(targetDegrees, 1);
      Serial.print(" elapsed=");
      Serial.println(elapsedMs);
      if (accumulatedDegrees >= completionTargetDegrees) {
        Serial.println("ROTATION_REACHED_BY_TOLERANCE");
        Serial.println("ROTATION_STOP_REASON=TARGET_REACHED");
        Serial.println("ROTATION_STOP");
        return true;
      }
      emitLine("COCOVISION_MPU_ROTATION_TIMEOUT");
      Serial.println("ROTATION_STOP_REASON=TIMEOUT");
      Serial.println("ROTATION_STOP");
      return false;
    }

    delay(2);
  }

  Serial.print("ROTATION_REACHED angle=");
  Serial.println(accumulatedDegrees, 1);
  stopMotors();
  Serial.println("MOTOR_STOP");
  Serial.println("ROTATION_STOP_REASON=TARGET_REACHED");
  Serial.println("ROTATION_STOP");
  Serial.print("COCOVISION_MPU_ROTATION_DEGREES=");
  Serial.println(accumulatedDegrees, 1);
#if COCOVISION_BT_AVAILABLE
  if (SerialBT.hasClient()) {
    SerialBT.print("COCOVISION_MPU_ROTATION_DEGREES=");
    SerialBT.println(accumulatedDegrees, 1);
  }
#endif
  return true;
}

void logStationaryGyro(unsigned long durationMs) {
  Serial.print("GYRO_STATIONARY_DIAGNOSTIC_START duration=");
  Serial.println(durationMs);
  unsigned long startedAt = millis();
  unsigned long lastLogAt = 0;
  while (millis() - startedAt < durationMs) {
    if (shouldAbortForReset()) {
      return;
    }

    unsigned long nowMs = millis();
    if (lastLogAt == 0 || nowMs - lastLogAt >= GYRO_STATIONARY_LOG_INTERVAL_MS) {
      lastLogAt = nowMs;
      float rawGyroZDps = mpu.getRotationZ() / GYRO_Z_LSB_PER_DPS;
      Serial.print("GYRO_STATIONARY gyroZ=");
      Serial.print(rawGyroZDps, 4);
      Serial.print(" elapsed=");
      Serial.println(nowMs - startedAt);
    }
    if (!delayWithReset(5)) {
      return;
    }
  }
  Serial.println("GYRO_STATIONARY_DIAGNOSTIC_END");
}

float readUltrasonicDistanceCm() {
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);

  unsigned long durationUs = pulseIn(ULTRASONIC_ECHO_PIN, HIGH, ULTRASONIC_PULSE_TIMEOUT_US);
  if (durationUs == 0) {
    return -1.0f;
  }

  return durationUs / 58.0f;
}

void handleUltrasonicFallback() {
  if (isPresenting) {
    return;
  }

  unsigned long now = millis();
  if (now - lastUltrasonicSampleAt < ULTRASONIC_SAMPLE_INTERVAL_MS) {
    return;
  }
  lastUltrasonicSampleAt = now;

  float distanceCm = readUltrasonicDistanceCm();
  bool triggerActive = distanceCm > 0.0f && distanceCm <= ULTRASONIC_TRIGGER_DISTANCE_CM;
  bool releaseActive = distanceCm < 0.0f || distanceCm >= ULTRASONIC_RELEASE_DISTANCE_CM;

  if (releaseActive) {
    ultrasonicPresenceLatched = false;
  }

  if (!triggerActive || ultrasonicPresenceLatched) {
    return;
  }
  ultrasonicPresenceLatched = true;

  handleTrigger("ULTRA", RequestedCommand::ANY);
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
