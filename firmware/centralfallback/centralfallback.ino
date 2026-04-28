constexpr int TRIG_PIN = 9;
constexpr int ECHO_PIN = 10;

constexpr float TRIGGER_DISTANCE_CM = 6.0f;
constexpr float RELEASE_DISTANCE_CM = 10.0f;
constexpr unsigned long READ_INTERVAL_MS = 50;
constexpr unsigned long SERIAL_BAUD = 115200;
constexpr unsigned long PULSE_TIMEOUT_US = 25000UL;

// Keep disabled during presentation so only the fallback trigger reaches Python.
constexpr bool ENABLE_DEBUG_LOGS = false;

unsigned long lastReadAtMs = 0;
bool presenceLatched = false;

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long pulseDurationUs = pulseIn(ECHO_PIN, HIGH, PULSE_TIMEOUT_US);
  if (pulseDurationUs == 0) {
    return -1.0f;
  }

  return pulseDurationUs / 58.0f;
}

void maybeDebugDistance(float distanceCm) {
  if (!ENABLE_DEBUG_LOGS) {
    return;
  }

  Serial.print("DIST_CM=");
  Serial.println(distanceCm);
}

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  Serial.begin(SERIAL_BAUD);
}

void loop() {
  unsigned long nowMs = millis();
  if (nowMs - lastReadAtMs < READ_INTERVAL_MS) {
    return;
  }
  lastReadAtMs = nowMs;

  float distanceCm = readDistanceCm();
  maybeDebugDistance(distanceCm);

  if (distanceCm < 0.0f) {
    return;
  }

  if (!presenceLatched && distanceCm <= TRIGGER_DISTANCE_CM) {
    presenceLatched = true;
    Serial.println("CENTRAL_FALLBACK_TRIGGER");
    return;
  }

  if (presenceLatched && distanceCm >= RELEASE_DISTANCE_CM) {
    presenceLatched = false;
  }
}
