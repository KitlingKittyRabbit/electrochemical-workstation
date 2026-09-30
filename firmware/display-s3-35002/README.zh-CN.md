# ESP32-S3 SuperMini 与鸿讯 35002 最小验证固件

本工程只验证 ESP32-S3 与 3.5 英寸鸿讯 35002 SPI 模块的显示和电阻触摸，不接入 ESP32-C3、UART 检测端、标曲、浓度检测或 LVGL。

## 资料确认

实现依据主工作区资料：

- `3.5寸SPI接口模块35002数据手册(鸿讯电子).pdf`：35002 为 4 线 SPI 模块，分辨率为 `320x480`，工作电压为 `3.3V`，LED 背光控制脚为高电平点亮；接口第 3～9 脚为 LCD SPI、片选、复位、数据/命令和背光信号。
- `CL35BC219-40A_IPS_RTP&WithoutTP.rar` 中的 `ST7796S_SPEC_V1.0.pdf`、`ST7796_3.5IPS_Code.txt` 和 `CL35BC219-40A接线图.pdf`：显示控制器资料和 4-SPI 初始化序列对应 `ST7796S`。
- 同一资料包中的 `CL35BC219-40A_RTP_SPEC_V0 鸿讯电子.pdf` 以及 `STC32_ST7796_IPS_4SPI Demo_V1` 示例：电阻触摸方案使用 `XPT2046`。

35002 手册也列出 `FT6336U` 电容触摸作为可选配置。当前工程按随附 `RTP` 规格资料和 XPT2046 示例实现电阻触摸，不实现 FT6336U 的 I2C 触摸路径。

## 统一接线

开发板按用户确认的 `ESP32-S3 SuperMini` 统一布局接线。模块端编号和信号名称以 35002 手册为准，S3 端 GPIO 集中配置在 `src/display_config.h`。

| 35002 接口 | 模块信号 | ESP32-S3 GPIO | 说明 |
| ---: | --- | ---: | --- |
| 1 | VCC | 3V3 | 3.3 V 供电 |
| 2 | GND | GND | 共地 |
| 3 | CS | GPIO10 | LCD 片选，低有效 |
| 4 | RESET | GPIO8 | LCD 复位，低有效 |
| 5 | DC | GPIO9 | 数据/命令选择 |
| 6 | SDI/MOSI | GPIO11 | LCD 数据输入 |
| 7 | SCK | GPIO12 | LCD 时钟 |
| 8 | LED | GPIO7 | 手册规定高电平点亮背光 |
| 9 | SDO/MISO | GPIO13 | LCD 数据输出，当前仅保留接线 |
| 10 | T_CLK | GPIO4 | XPT2046 触摸时钟 |
| 11 | T_CS | GPIO5 | XPT2046 片选 |
| 12 | T_SDI | GPIO3 | XPT2046 数据输入 |
| 13 | T_SDO | GPIO2 | XPT2046 数据输出 |
| 14 | T_IRQ | GPIO6 | XPT2046 触摸中断，低有效 |

电源、背光和控制信号均按资料中的 3.3 V 逻辑使用。不要把 35002 的 VCC 接到 5 V。请直接按照上表的 GPIO 编号接线；该布局使用 GPIO2～13，避开 ESP32-S3 常见启动绑带 GPIO0、GPIO45 和 GPIO46。

## 固件行为

启动后固件会：

1. 拉高 LED 背光控制脚。
2. 复位并初始化 ST7796S，使用 RGB565（`0x55`）和 4-SPI 资料中的初始化序列。
3. 绘制彩色条带、边框、网格和 ASCII 测试文字，验证纯色、颜色顺序、文字和简单图案。
4. 显示中心和四角五个校准目标。每个目标需要用触控笔或手指点击一次；固件读取 XPT2046 原始 X/Y，并拟合轴交换、缩放和偏移。
5. 校准完成后，任意点击都会在屏幕底部显示映射后的 `TOUCH X=... Y=...` 和原始 `RAW X=... Y=...`，并在点击位置画十字。

默认 `kDisplayRotation = 0`，逻辑分辨率为 320x480 竖屏。资料包示例对应的方向寄存器值为：

| `kDisplayRotation` | 方向 | 逻辑分辨率 | ST7796S MADCTL |
| ---: | --- | --- | ---: |
| 0 | 竖屏 | 320x480 | `0x48` |
| 1 | 竖屏倒置 | 320x480 | `0x88` |
| 2 | 横屏 | 480x320 | `0xE8` |
| 3 | 横屏反向 | 480x320 | `0x28` |

要验证其他方向，修改 `src/display_config.h` 的 `kDisplayRotation` 后重新烧录。每次启动都会重新校准中心和四角，因此坐标映射会与当前方向同步验证。

## Flash、分区与 PSRAM

`platformio.ini` 已显式配置 4 MB Flash 和适用于 4 MB Flash 的 `default.csv` 分区表，避免沿用 `esp32-s3-devkitc-1` 的 8 MB 默认配置。本固件不启用也不依赖 PSRAM。

## 构建、烧录和运行

在本目录执行：

```bash
pio run -e esp32-s3-supermini
pio run -e esp32-s3-supermini -t upload
pio device monitor -b 115200
```

串口会输出控制器、方向、校准点原始值和每次触摸的原始/映射坐标。当前实现不保存校准参数，重启后会再次执行五点校准，这样可以直接检查重启后的重复性。

## 当前验证状态

- 资料核验：已根据 35002 手册、ST7796S 规格书、CL35BC219-40A 接线图和 XPT2046 示例确认控制器、分辨率、供电、背光和模块端引脚。
- 代码静态检查：已在临时 Arduino/SPI API 声明下通过 `g++ -std=c++17 -fsyntax-only`，用于检查 C++ 语法和类型调用。
- PlatformIO 构建：已使用 `PLATFORMIO_CORE_DIR=/tmp/electrochemical-pio-rabbit /tmp/electrochemical-pio-venv/bin/pio run -e esp32-s3-supermini` 完成真实构建，结果为 `SUCCESS`。RAM 使用 `18760/327680`（5.7%），Flash 使用 `271689/1310720`（20.7%）。
- 实机验证：当前环境没有连接 ESP32-S3 SuperMini 和 35002，背光、显示、五点触摸、旋转映射和重启重复性待上板执行；代码构建通过与实机验证待执行需区分记录。

## 验收记录模板

实机连接后应记录：

- 背光是否点亮；
- 彩色条带、文字和网格是否正常；
- 竖屏和其他方向的逻辑分辨率是否正确；
- 中心、左上、右上、左下、右下五个目标的原始坐标与映射坐标；
- 连续触摸、释放和重启后是否仍能重复读取。
