#pragma once

#include <stdint.h>

// ESP32-S3 SuperMini 的统一接线布局。所有屏幕相关 GPIO 集中在此处。
namespace DisplayConfig {

// 35002 显示接口（4 线 SPI）。
constexpr uint8_t kLcdSck = 12;
constexpr uint8_t kLcdMosi = 11;
constexpr uint8_t kLcdMiso = 13;
constexpr uint8_t kLcdCs = 10;
constexpr uint8_t kLcdDc = 9;
constexpr uint8_t kLcdReset = 8;
constexpr uint8_t kLcdLed = 7;

// 35002 电阻触摸接口（XPT2046），与 LCD SPI 信号分开接线。
constexpr uint8_t kTouchIrq = 6;
constexpr uint8_t kTouchCs = 5;
constexpr uint8_t kTouchSck = 4;
constexpr uint8_t kTouchMosi = 3;
constexpr uint8_t kTouchMiso = 2;

// 0：竖屏 320x480；1：竖屏 180 度；2/3：横屏 480x320。
// 修改此值后，固件启动时会按新的方向重新进行五点触摸校准。
constexpr uint8_t kDisplayRotation = 0;

constexpr uint32_t kLcdSpiHz = 40000000;
constexpr uint32_t kCalibrationPointTimeoutMs = 12000;
constexpr bool kBacklightActiveHigh = true;

}  // namespace DisplayConfig
