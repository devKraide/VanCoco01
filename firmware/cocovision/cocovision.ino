#include <Wire.h>
#include <Adafruit_TCS34725.h>

constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr unsigned long DETECTION_DEBOUNCE_MS = 1200;
constexpr float MIN_CLEAR_VALUE = 120.0f;
constexpr float DOMINANCE_RATIO = 1.18f;

Adafruit_TCS34725 tcs =
    Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_50MS, TCS34725_GAIN_4X);

String lastColor = "";
unsigned long lastSentAt = 0;

String detectDominantColor(uint16_t red, uint16_t green, uint16_t blue, uint16_t clear);
void publishColorIfNeeded(const String& colorName);

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  Wire.begin();

  if (!tcs.begin()) {
    Serial.println("TCS34725_NOT_FOUND");
    while (true) {
      delay(1000);
    }
  }
}

void loop() {
  uint16_t red = 0;
  uint16_t green = 0;
  uint16_t blue = 0;
  uint16_t clear = 0;

  tcs.getRawData(&red, &green, &blue, &clear);
  String colorName = detectDominantColor(red, green, blue, clear);
  publishColorIfNeeded(colorName);
  delay(80);
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

  Serial.println(colorName);
  lastColor = colorName;
  lastSentAt = now;
}
