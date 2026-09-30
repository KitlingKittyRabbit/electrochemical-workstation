#include <Arduino.h>
#include <SPI.h>

#include <initializer_list>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "display_config.h"

namespace {

constexpr uint16_t kBlack = 0x0000;
constexpr uint16_t kWhite = 0xFFFF;
constexpr uint16_t kRed = 0xF800;
constexpr uint16_t kGreen = 0x07E0;
constexpr uint16_t kBlue = 0x001F;
constexpr uint16_t kYellow = 0xFFE0;
constexpr uint16_t kCyan = 0x07FF;
constexpr uint16_t kMagenta = 0xF81F;
constexpr uint16_t kDarkBlue = 0x18C3;

constexpr uint8_t kMadctlByRotation[4] = {0x48, 0x88, 0xE8, 0x28};

constexpr uint8_t kCmdSleepOut = 0x11;
constexpr uint8_t kCmdDisplayOn = 0x29;
constexpr uint8_t kCmdMemoryAccess = 0x36;
constexpr uint8_t kCmdPixelFormat = 0x3A;
constexpr uint8_t kCmdColumnAddress = 0x2A;
constexpr uint8_t kCmdPageAddress = 0x2B;
constexpr uint8_t kCmdMemoryWrite = 0x2C;

constexpr uint8_t kXpt2046ReadX = 0xD0;
constexpr uint8_t kXpt2046ReadY = 0x90;

struct ScreenPoint {
  int16_t x;
  int16_t y;
};

struct RawTouchPoint {
  uint16_t x;
  uint16_t y;
};

class St7796s {
 public:
  explicit St7796s(SPIClass& spi) : spi_(spi) {}

  void begin() {
    pinMode(DisplayConfig::kLcdCs, OUTPUT);
    pinMode(DisplayConfig::kLcdDc, OUTPUT);
    pinMode(DisplayConfig::kLcdReset, OUTPUT);
    digitalWrite(DisplayConfig::kLcdCs, HIGH);
    digitalWrite(DisplayConfig::kLcdDc, HIGH);

    spi_.begin(DisplayConfig::kLcdSck, DisplayConfig::kLcdMiso,
               DisplayConfig::kLcdMosi, DisplayConfig::kLcdCs);

    digitalWrite(DisplayConfig::kLcdReset, HIGH);
    delay(1);
    digitalWrite(DisplayConfig::kLcdReset, LOW);
    delay(10);
    digitalWrite(DisplayConfig::kLcdReset, HIGH);
    delay(120);

    // 资料包 STC32_ST7796_IPS_4SPI Demo_V1 中的 ST7796 初始化序列。
    writeCommand(kCmdSleepOut);
    delay(120);
    writeCommandData(0xF0, {0xC3});
    writeCommandData(0xF0, {0x96});
    writeCommandData(0x36, {0x48});
    writeCommandData(kCmdPixelFormat, {0x55});
    writeCommandData(0xB4, {0x01});
    writeCommandData(0xB7, {0xC6});
    writeCommandData(0xE8, {0x40, 0x8A, 0x00, 0x00, 0x29, 0x19, 0xA5, 0x33});
    writeCommandData(0xC1, {0x06});
    writeCommandData(0xC2, {0xA7});
    writeCommandData(0xC5, {0x18});
    writeCommandData(0xE0, {0xF0, 0x09, 0x0B, 0x06, 0x04, 0x15, 0x2F,
                             0x54, 0x42, 0x3C, 0x17, 0x14, 0x18, 0x1B});
    writeCommandData(0xE1, {0xF0, 0x09, 0x0B, 0x06, 0x04, 0x03, 0x2D,
                             0x43, 0x42, 0x3B, 0x16, 0x14, 0x17, 0x1B});
    writeCommandData(0xF0, {0x3C});
    writeCommandData(0xF0, {0x69});
    writeCommand(0x21);
    delay(120);

    setRotation(DisplayConfig::kDisplayRotation);
    writeCommand(kCmdDisplayOn);
    delay(50);
  }

  void setRotation(uint8_t rotation) {
    rotation_ = rotation & 0x03;
    if (rotation_ == 0 || rotation_ == 1) {
      width_ = 320;
      height_ = 480;
    } else {
      width_ = 480;
      height_ = 320;
    }
    writeCommandData(kCmdMemoryAccess, {kMadctlByRotation[rotation_]});
    setAddressWindow(0, 0, width_ - 1, height_ - 1);
  }

  uint16_t width() const { return width_; }
  uint16_t height() const { return height_; }
  uint8_t rotation() const { return rotation_; }

  void fillScreen(uint16_t color) { fillRect(0, 0, width_, height_, color); }

  void fillRect(int32_t x, int32_t y, int32_t width, int32_t height,
                uint16_t color) {
    if (width <= 0 || height <= 0) {
      return;
    }
    int32_t x1 = x + width - 1;
    int32_t y1 = y + height - 1;
    if (x1 < 0 || y1 < 0 || x >= width_ || y >= height_) {
      return;
    }
    if (x < 0) {
      x = 0;
    }
    if (y < 0) {
      y = 0;
    }
    if (x1 >= width_) {
      x1 = width_ - 1;
    }
    if (y1 >= height_) {
      y1 = height_ - 1;
    }

    setAddressWindow(static_cast<uint16_t>(x), static_cast<uint16_t>(y),
                     static_cast<uint16_t>(x1), static_cast<uint16_t>(y1));
    writeCommand(kCmdMemoryWrite);

    spi_.beginTransaction(SPISettings(DisplayConfig::kLcdSpiHz, MSBFIRST,
                                      SPI_MODE0));
    selectData();
    const uint32_t pixels = static_cast<uint32_t>(x1 - x + 1) *
                            static_cast<uint32_t>(y1 - y + 1);
    for (uint32_t i = 0; i < pixels; ++i) {
      spi_.transfer16(color);
    }
    deselect();
    spi_.endTransaction();
  }

  void drawPixel(int32_t x, int32_t y, uint16_t color) {
    fillRect(x, y, 1, 1, color);
  }

  void drawCross(int16_t x, int16_t y, uint16_t color) {
    fillRect(x - 12, y - 1, 25, 3, color);
    fillRect(x - 1, y - 12, 3, 25, color);
  }

  void drawText(int16_t x, int16_t y, const char* text, uint16_t color,
                uint8_t scale = 1) {
    int16_t cursorX = x;
    int16_t cursorY = y;
    while (*text != '\0') {
      if (*text == '\n') {
        cursorX = x;
        cursorY += static_cast<int16_t>(8 * scale);
        ++text;
        continue;
      }
      drawChar(cursorX, cursorY, *text, color, scale);
      cursorX += static_cast<int16_t>(6 * scale);
      ++text;
    }
  }

 private:
  SPIClass& spi_;
  uint16_t width_ = 320;
  uint16_t height_ = 480;
  uint8_t rotation_ = 0;

  void selectCommand() {
    digitalWrite(DisplayConfig::kLcdCs, LOW);
    digitalWrite(DisplayConfig::kLcdDc, LOW);
  }

  void selectData() {
    digitalWrite(DisplayConfig::kLcdCs, LOW);
    digitalWrite(DisplayConfig::kLcdDc, HIGH);
  }

  void deselect() { digitalWrite(DisplayConfig::kLcdCs, HIGH); }

  void writeCommand(uint8_t command) {
    spi_.beginTransaction(SPISettings(DisplayConfig::kLcdSpiHz, MSBFIRST,
                                      SPI_MODE0));
    selectCommand();
    spi_.transfer(command);
    deselect();
    spi_.endTransaction();
  }

  void writeCommandData(uint8_t command,
                        std::initializer_list<uint8_t> data) {
    spi_.beginTransaction(SPISettings(DisplayConfig::kLcdSpiHz, MSBFIRST,
                                      SPI_MODE0));
    selectCommand();
    spi_.transfer(command);
    selectData();
    for (const uint8_t value : data) {
      spi_.transfer(value);
    }
    deselect();
    spi_.endTransaction();
  }

  void writeData16(uint16_t value) {
    spi_.transfer(static_cast<uint8_t>(value >> 8));
    spi_.transfer(static_cast<uint8_t>(value & 0xFF));
  }

  void setAddressWindow(uint16_t x0, uint16_t y0, uint16_t x1,
                        uint16_t y1) {
    spi_.beginTransaction(SPISettings(DisplayConfig::kLcdSpiHz, MSBFIRST,
                                      SPI_MODE0));
    selectCommand();
    spi_.transfer(kCmdColumnAddress);
    selectData();
    writeData16(x0);
    writeData16(x1);
    deselect();

    selectCommand();
    spi_.transfer(kCmdPageAddress);
    selectData();
    writeData16(y0);
    writeData16(y1);
    deselect();
    spi_.endTransaction();
  }

  static void glyphFor(char character, uint8_t glyph[5]) {
    static const uint8_t uppercase[26][5] = {
        {0x7E, 0x11, 0x11, 0x11, 0x7E},  // A
        {0x7F, 0x49, 0x49, 0x49, 0x36},  // B
        {0x3E, 0x41, 0x41, 0x41, 0x22},  // C
        {0x7F, 0x41, 0x41, 0x22, 0x1C},  // D
        {0x7F, 0x49, 0x49, 0x49, 0x41},  // E
        {0x7F, 0x09, 0x09, 0x09, 0x01},  // F
        {0x3E, 0x41, 0x49, 0x49, 0x7A},  // G
        {0x7F, 0x08, 0x08, 0x08, 0x7F},  // H
        {0x00, 0x41, 0x7F, 0x41, 0x00},  // I
        {0x20, 0x40, 0x41, 0x3F, 0x01},  // J
        {0x7F, 0x08, 0x14, 0x22, 0x41},  // K
        {0x7F, 0x40, 0x40, 0x40, 0x40},  // L
        {0x7F, 0x02, 0x0C, 0x02, 0x7F},  // M
        {0x7F, 0x04, 0x08, 0x10, 0x7F},  // N
        {0x3E, 0x41, 0x41, 0x41, 0x3E},  // O
        {0x7F, 0x09, 0x09, 0x09, 0x06},  // P
        {0x3E, 0x41, 0x51, 0x21, 0x5E},  // Q
        {0x7F, 0x09, 0x19, 0x29, 0x46},  // R
        {0x46, 0x49, 0x49, 0x49, 0x31},  // S
        {0x01, 0x01, 0x7F, 0x01, 0x01},  // T
        {0x3F, 0x40, 0x40, 0x40, 0x3F},  // U
        {0x1F, 0x20, 0x40, 0x20, 0x1F},  // V
        {0x3F, 0x40, 0x38, 0x40, 0x3F},  // W
        {0x63, 0x14, 0x08, 0x14, 0x63},  // X
        {0x07, 0x08, 0x70, 0x08, 0x07},  // Y
        {0x61, 0x51, 0x49, 0x45, 0x43},  // Z
    };
    static const uint8_t digits[10][5] = {
        {0x3E, 0x51, 0x49, 0x45, 0x3E},  // 0
        {0x00, 0x42, 0x7F, 0x40, 0x00},  // 1
        {0x42, 0x61, 0x51, 0x49, 0x46},  // 2
        {0x21, 0x41, 0x45, 0x4B, 0x31},  // 3
        {0x18, 0x14, 0x12, 0x7F, 0x10},  // 4
        {0x27, 0x45, 0x45, 0x45, 0x39},  // 5
        {0x3C, 0x4A, 0x49, 0x49, 0x30},  // 6
        {0x01, 0x71, 0x09, 0x05, 0x03},  // 7
        {0x36, 0x49, 0x49, 0x49, 0x36},  // 8
        {0x06, 0x49, 0x49, 0x29, 0x1E},  // 9
    };

    if (character >= 'A' && character <= 'Z') {
      memcpy(glyph, uppercase[character - 'A'], 5);
      return;
    }
    if (character >= '0' && character <= '9') {
      memcpy(glyph, digits[character - '0'], 5);
      return;
    }

    const uint8_t blank[5] = {0, 0, 0, 0, 0};
    const uint8_t minus[5] = {0x08, 0x08, 0x08, 0x08, 0x08};
    const uint8_t colon[5] = {0x00, 0x36, 0x36, 0x00, 0x00};
    const uint8_t dot[5] = {0x00, 0x00, 0x00, 0x60, 0x60};
    const uint8_t slash[5] = {0x20, 0x10, 0x08, 0x04, 0x02};
    const uint8_t equals[5] = {0x14, 0x14, 0x14, 0x14, 0x14};
    const uint8_t leftParen[5] = {0x00, 0x1C, 0x22, 0x41, 0x00};
    const uint8_t rightParen[5] = {0x00, 0x41, 0x22, 0x1C, 0x00};
    const uint8_t question[5] = {0x02, 0x01, 0x51, 0x09, 0x06};
    const uint8_t comma[5] = {0x00, 0x00, 0x00, 0x50, 0x30};
    const uint8_t underscore[5] = {0x40, 0x40, 0x40, 0x40, 0x40};

    switch (character) {
      case '-':
        memcpy(glyph, minus, 5);
        break;
      case ':':
        memcpy(glyph, colon, 5);
        break;
      case '.':
        memcpy(glyph, dot, 5);
        break;
      case '/':
        memcpy(glyph, slash, 5);
        break;
      case '=':
        memcpy(glyph, equals, 5);
        break;
      case '(':
        memcpy(glyph, leftParen, 5);
        break;
      case ')':
        memcpy(glyph, rightParen, 5);
        break;
      case '?':
        memcpy(glyph, question, 5);
        break;
      case ',':
        memcpy(glyph, comma, 5);
        break;
      case '_':
        memcpy(glyph, underscore, 5);
        break;
      default:
        memcpy(glyph, blank, 5);
        break;
    }
  }

  void drawChar(int16_t x, int16_t y, char character, uint16_t color,
                uint8_t scale) {
    uint8_t glyph[5];
    glyphFor(character, glyph);
    for (uint8_t column = 0; column < 5; ++column) {
      for (uint8_t row = 0; row < 7; ++row) {
        if ((glyph[column] & (1U << row)) != 0) {
          fillRect(x + column * scale, y + row * scale, scale, scale, color);
        }
      }
    }
  }
};

class Xpt2046 {
 public:
  void begin() {
    pinMode(DisplayConfig::kTouchCs, OUTPUT);
    pinMode(DisplayConfig::kTouchSck, OUTPUT);
    pinMode(DisplayConfig::kTouchMosi, OUTPUT);
    pinMode(DisplayConfig::kTouchMiso, INPUT);
    pinMode(DisplayConfig::kTouchIrq, INPUT_PULLUP);
    digitalWrite(DisplayConfig::kTouchCs, HIGH);
    digitalWrite(DisplayConfig::kTouchSck, LOW);
    digitalWrite(DisplayConfig::kTouchMosi, LOW);
  }

  bool isPressed() const {
    return digitalRead(DisplayConfig::kTouchIrq) == LOW;
  }

  bool readPoint(RawTouchPoint& point) {
    if (!isPressed()) {
      return false;
    }
    point.x = readAverage(kXpt2046ReadX);
    point.y = readAverage(kXpt2046ReadY);
    return true;
  }

  void waitForRelease(uint32_t timeoutMs) const {
    const uint32_t start = millis();
    while (isPressed() && millis() - start < timeoutMs) {
      delay(2);
    }
  }

 private:
  static constexpr uint8_t kSampleCount = 5;

  void writeByte(uint8_t value) {
    for (uint8_t bit = 0; bit < 8; ++bit) {
      digitalWrite(DisplayConfig::kTouchMosi,
                   (value & 0x80U) != 0 ? HIGH : LOW);
      value <<= 1;
      digitalWrite(DisplayConfig::kTouchSck, LOW);
      delayMicroseconds(1);
      digitalWrite(DisplayConfig::kTouchSck, HIGH);
      delayMicroseconds(1);
    }
  }

  uint16_t readAxis(uint8_t command) {
    digitalWrite(DisplayConfig::kTouchCs, LOW);
    writeByte(command);
    delayMicroseconds(6);

    uint16_t value = 0;
    for (uint8_t bit = 0; bit < 16; ++bit) {
      digitalWrite(DisplayConfig::kTouchSck, LOW);
      delayMicroseconds(1);
      digitalWrite(DisplayConfig::kTouchSck, HIGH);
      value = static_cast<uint16_t>((value << 1) |
                                    (digitalRead(DisplayConfig::kTouchMiso) ? 1 : 0));
      delayMicroseconds(1);
    }
    digitalWrite(DisplayConfig::kTouchSck, LOW);
    digitalWrite(DisplayConfig::kTouchCs, HIGH);
    return value >> 4;
  }

  uint16_t readAverage(uint8_t command) {
    uint16_t samples[kSampleCount];
    for (uint8_t i = 0; i < kSampleCount; ++i) {
      samples[i] = readAxis(command);
    }
    for (uint8_t i = 0; i < kSampleCount - 1; ++i) {
      for (uint8_t j = i + 1; j < kSampleCount; ++j) {
        if (samples[j] < samples[i]) {
          const uint16_t temporary = samples[i];
          samples[i] = samples[j];
          samples[j] = temporary;
        }
      }
    }
    return static_cast<uint16_t>((samples[1] + samples[2] + samples[3]) / 3);
  }
};

struct LinearFit {
  float slope = 0.0f;
  float intercept = 0.0f;
  float squaredError = INFINITY;
  bool valid = false;
};

struct TouchCalibration {
  float xSlope = 1.0f;
  float xIntercept = 0.0f;
  float ySlope = 1.0f;
  float yIntercept = 0.0f;
  bool swapped = false;
  bool valid = false;

  ScreenPoint map(const RawTouchPoint& raw, uint16_t width,
                  uint16_t height) const {
    const float rawForX = swapped ? raw.y : raw.x;
    const float rawForY = swapped ? raw.x : raw.y;
    const int32_t mappedX = lroundf(xSlope * rawForX + xIntercept);
    const int32_t mappedY = lroundf(ySlope * rawForY + yIntercept);
    ScreenPoint point;
    point.x = static_cast<int16_t>(constrain(mappedX, 0, width - 1));
    point.y = static_cast<int16_t>(constrain(mappedY, 0, height - 1));
    return point;
  }
};

LinearFit fitAxis(const RawTouchPoint* raw, const ScreenPoint* target,
                  uint8_t count, bool useRawY, bool useTargetY) {
  float rawMean = 0.0f;
  float targetMean = 0.0f;
  for (uint8_t i = 0; i < count; ++i) {
    rawMean += useRawY ? raw[i].y : raw[i].x;
    targetMean += useTargetY ? target[i].y : target[i].x;
  }
  rawMean /= count;
  targetMean /= count;

  float denominator = 0.0f;
  float numerator = 0.0f;
  for (uint8_t i = 0; i < count; ++i) {
    const float rawValue = (useRawY ? raw[i].y : raw[i].x) - rawMean;
    const float targetValue = (useTargetY ? target[i].y : target[i].x) - targetMean;
    denominator += rawValue * rawValue;
    numerator += rawValue * targetValue;
  }
  LinearFit fit;
  if (denominator < 0.001f) {
    return fit;
  }
  fit.slope = numerator / denominator;
  fit.intercept = targetMean - fit.slope * rawMean;
  fit.squaredError = 0.0f;
  for (uint8_t i = 0; i < count; ++i) {
    const float rawValue = useRawY ? raw[i].y : raw[i].x;
    const float targetValue = useTargetY ? target[i].y : target[i].x;
    const float error = targetValue - (fit.slope * rawValue + fit.intercept);
    fit.squaredError += error * error;
  }
  fit.valid = true;
  return fit;
}

TouchCalibration fitCalibration(const RawTouchPoint* raw,
                                const ScreenPoint* target, uint8_t count) {
  const LinearFit directX = fitAxis(raw, target, count, false, false);
  const LinearFit directY = fitAxis(raw, target, count, true, true);
  const LinearFit swappedX = fitAxis(raw, target, count, true, false);
  const LinearFit swappedY = fitAxis(raw, target, count, false, true);

  TouchCalibration result;
  const float directError = directX.squaredError + directY.squaredError;
  const float swappedError = swappedX.squaredError + swappedY.squaredError;
  if (directX.valid && directY.valid && directError <= swappedError) {
    result.xSlope = directX.slope;
    result.xIntercept = directX.intercept;
    result.ySlope = directY.slope;
    result.yIntercept = directY.intercept;
    result.swapped = false;
    result.valid = true;
  } else if (swappedX.valid && swappedY.valid) {
    result.xSlope = swappedX.slope;
    result.xIntercept = swappedX.intercept;
    result.ySlope = swappedY.slope;
    result.yIntercept = swappedY.intercept;
    result.swapped = true;
    result.valid = true;
  }
  return result;
}

ScreenPoint calibrationTarget(uint8_t index, uint16_t width, uint16_t height) {
  const int16_t margin = 20;
  const ScreenPoint targets[5] = {
      {static_cast<int16_t>(width / 2), static_cast<int16_t>(height / 2)},
      {margin, margin},
      {static_cast<int16_t>(width - margin - 1), margin},
      {margin, static_cast<int16_t>(height - margin - 1)},
      {static_cast<int16_t>(width - margin - 1),
       static_cast<int16_t>(height - margin - 1)},
  };
  return targets[index];
}

void drawTestPattern(St7796s& display) {
  const uint16_t width = display.width();
  const uint16_t height = display.height();
  display.fillScreen(kDarkBlue);
  display.fillRect(0, 70, width / 4, 70, kRed);
  display.fillRect(width / 4, 70, width / 4, 70, kGreen);
  display.fillRect(width / 2, 70, width / 4, 70, kBlue);
  display.fillRect((width * 3) / 4, 70, width - (width * 3) / 4, 70, kYellow);
  display.fillRect(12, 160, width - 24, height - 240, kBlack);
  display.fillRect(20, 168, width - 40, height - 256, kMagenta);
  display.fillRect(28, 176, width - 56, height - 272, kCyan);
  display.fillRect(36, 184, width - 72, height - 288, kDarkBlue);
  display.drawText(8, 8, "ESP32-S3", kWhite, 2);
  display.drawText(8, 32, "ST7796S 320X480", kWhite, 1);
  char rotationText[24];
  snprintf(rotationText, sizeof(rotationText), "ROTATION %u", display.rotation());
  display.drawText(8, 48, rotationText, kWhite, 1);
  display.drawText(8, height - 58, "TOUCH CALIBRATION", kWhite, 1);
}

bool runTouchCalibration(St7796s& display, Xpt2046& touch,
                         TouchCalibration& calibration) {
  constexpr uint8_t kTargetCount = 5;
  RawTouchPoint raw[kTargetCount]{};
  ScreenPoint target[kTargetCount]{};

  Serial.println("开始五点触摸校准：中心、左上、右上、左下、右下");
  display.fillScreen(kBlack);
  display.drawText(8, 8, "TOUCH CALIBRATION", kWhite, 1);
  display.drawText(8, 24, "PRESS EACH CROSS", kWhite, 1);

  for (uint8_t i = 0; i < kTargetCount; ++i) {
    target[i] = calibrationTarget(i, display.width(), display.height());
    display.drawCross(target[i].x, target[i].y, kYellow);
    touch.waitForRelease(1000);

    const uint32_t start = millis();
    bool captured = false;
    while (millis() - start < DisplayConfig::kCalibrationPointTimeoutMs) {
      if (touch.readPoint(raw[i])) {
        captured = true;
        break;
      }
      delay(10);
    }
    if (!captured) {
      Serial.printf("校准点 %u 超时，使用默认映射\n", i + 1);
      touch.waitForRelease(1000);
      return false;
    }

    Serial.printf("校准点 %u: target=(%d,%d), raw=(%u,%u)\n", i + 1,
                  target[i].x, target[i].y, raw[i].x, raw[i].y);
    display.drawCross(target[i].x, target[i].y, kGreen);
    touch.waitForRelease(2000);
    delay(150);
  }

  calibration = fitCalibration(raw, target, kTargetCount);
  if (!calibration.valid) {
    Serial.println("校准拟合失败，使用默认映射");
    return false;
  }
  Serial.printf("校准完成：axis_swap=%s x_slope=%.5f y_slope=%.5f\n",
                calibration.swapped ? "yes" : "no", calibration.xSlope,
                calibration.ySlope);
  return true;
}

void useFallbackCalibration(TouchCalibration& calibration, uint16_t width,
                            uint16_t height) {
  // XPT2046 常见有效范围的保守默认值。实机应优先完成启动五点校准。
  constexpr float kRawMin = 200.0f;
  constexpr float kRawMax = 3800.0f;
  calibration.xSlope = (width - 1.0f) / (kRawMax - kRawMin);
  calibration.xIntercept = -kRawMin * calibration.xSlope;
  calibration.ySlope = (height - 1.0f) / (kRawMax - kRawMin);
  calibration.yIntercept = -kRawMin * calibration.ySlope;
  calibration.swapped = false;
  calibration.valid = false;
}

void showTouchResult(St7796s& display, const RawTouchPoint& raw,
                     const TouchCalibration& calibration) {
  const ScreenPoint mapped =
      calibration.map(raw, display.width(), display.height());
  display.drawCross(mapped.x, mapped.y, kWhite);
  display.fillRect(0, display.height() - 52, display.width(), 52, kBlack);

  char line[32];
  snprintf(line, sizeof(line), "TOUCH X=%d Y=%d", mapped.x, mapped.y);
  display.drawText(4, display.height() - 48, line, kWhite, 1);
  snprintf(line, sizeof(line), "RAW X=%u Y=%u", raw.x, raw.y);
  display.drawText(4, display.height() - 34, line, kYellow, 1);

  Serial.printf("触摸 raw=(%u,%u) mapped=(%d,%d) rotation=%u\n", raw.x,
                raw.y, mapped.x, mapped.y, display.rotation());
}

St7796s display(SPI);
Xpt2046 touch;
TouchCalibration calibration;
bool touchWasPressed = false;

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("ESP32-S3 SuperMini / 35002 ST7796S + XPT2046");

  pinMode(DisplayConfig::kLcdLed, OUTPUT);
  digitalWrite(DisplayConfig::kLcdLed,
               DisplayConfig::kBacklightActiveHigh ? HIGH : LOW);

  display.begin();
  touch.begin();
  drawTestPattern(display);

  if (!runTouchCalibration(display, touch, calibration)) {
    useFallbackCalibration(calibration, display.width(), display.height());
    display.fillRect(0, 0, display.width(), 60, kBlack);
    display.drawText(8, 8, "CAL TIMEOUT", kYellow, 2);
    display.drawText(8, 32, "DEFAULT MAP", kYellow, 1);
    delay(800);
  }
  drawTestPattern(display);
  display.drawText(8, display.height() - 58, "TOUCH READY", kWhite, 1);
  Serial.println("显示和触摸测试已进入运行状态");
}

void loop() {
  if (touch.isPressed()) {
    RawTouchPoint raw;
    if (!touchWasPressed && touch.readPoint(raw)) {
      showTouchResult(display, raw, calibration);
    }
    touchWasPressed = true;
    delay(30);
  } else {
    touchWasPressed = false;
  }
  delay(5);
}
