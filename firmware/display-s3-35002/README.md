# ESP32-S3 / Hongxun 35002 validation firmware

This PlatformIO project validates an ESP32-S3 SuperMini with the 3.5-inch
Hongxun 35002 SPI display and resistive-touch option. It is intentionally a
standalone display test; it does not implement the electrochemical measurement
workflow.

## Wiring

| Module pin | Signal | ESP32-S3 pin |
| ---: | --- | ---: |
| 1 | 3.3 V | 3V3 |
| 2 | Ground | GND |
| 3 | LCD CS | GPIO10 |
| 4 | LCD reset | GPIO8 |
| 5 | LCD data/command | GPIO9 |
| 6 | LCD MOSI | GPIO11 |
| 7 | LCD clock | GPIO12 |
| 8 | Backlight enable | GPIO7 |
| 9 | LCD MISO | GPIO13 |
| 10 | Touch clock | GPIO4 |
| 11 | Touch CS | GPIO5 |
| 12 | Touch MOSI | GPIO3 |
| 13 | Touch MISO | GPIO2 |
| 14 | Touch interrupt | GPIO6 |

The tested module uses 3.3 V power and logic. Verify your own module revision
before wiring it; do not infer electrical limits solely from this table.

## Build and upload

```bash
pio run -e esp32-s3-supermini
pio run -e esp32-s3-supermini -t upload
pio device monitor -b 115200
```

At startup, the firmware initializes the ST7796S, draws a color and text test
pattern, and requests five calibration touches for the XPT2046. Calibration is
not persisted and therefore runs again after every reset.

`src/display_config.h` centralizes the pin map and display rotation. The project
targets a 4 MB flash ESP32-S3 configuration and does not require PSRAM.

## Validation status

The source has passed a PlatformIO build. Display output, touch mapping,
rotation, and repeatability must still be validated on the reader's exact
hardware. Record the module revision, raw calibration points, mapped points,
and firmware commit when reporting a hardware test.

The original Chinese validation notes are retained in `README.zh-CN.md`.
