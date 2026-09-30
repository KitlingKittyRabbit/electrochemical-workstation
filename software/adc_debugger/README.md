# Electrochemical ADC Debugger

Cross-platform AIN0 debugging tool for the ESP32-C3 and ADS1115 board.

## Install

```bash
python -m pip install -r requirements.txt
```

## Run the GUI

```bash
./run_linux.sh
```

The GUI discovers Linux `/dev/ttyACM*` and Windows `COM*` ports. The default ADC settings are 250 SPS and +/-4.096 V. The wider range is intentional because the board's analog output uses a 0-3.3 V single-ended signal.

On Ubuntu/Linux with an X11 desktop, install the Qt cursor library once if Qt reports that `libxcb-cursor.so.0` is missing:

```bash
sudo apt update
sudo apt install -y libxcb-cursor0
```

On first use, connect the board and click `一键初始化设备`. The GUI uploads the bundled MicroPython device program and reconnects automatically. No `mpremote` or terminal command is required.

`保存检测区 CSV` opens a save-file dialog where the folder and filename can be chosen. The displayed zeroed output is `AIN0 - 1.65 V`. Enter the measured R12 value to show `G = 1 + R12/10kΩ` and estimate the pre-amplification voltage. `清空检测区` only clears the visible plot and statistics.

## Build A Portable Windows/Linux Package

The target computer does not need Python or the Python dependencies after packaging.

On Linux:

```bash
./build_linux.sh
```

The executable is produced at `dist/ADC-Debugger/ADC-Debugger`.

Run the packaged Linux version with `dist/ADC-Debugger/run_linux.sh`.

On Windows, double-click `build_windows.bat`. The executable is produced at `dist\ADC-Debugger\ADC-Debugger.exe`.

Build on the same operating system as the target. The build output is a folder because this is more reliable for Qt applications than a single-file executable. The whole `dist/ADC-Debugger` folder is the portable package.

## Manual device installation (advanced)

The generic MicroPython firmware must be replaced by the device protocol program before the GUI can stream samples.

Linux example:

```bash
mpremote connect /dev/ttyACM0 fs cp firmware/main.py :main.py
mpremote connect /dev/ttyACM0 reset
```

Windows example:

```powershell
mpremote connect COM3 fs cp firmware/main.py :main.py
mpremote connect COM3 reset
```

The firmware uses I2C SCL=GPIO3 and SDA=GPIO10, and automatically detects ADS1115 addresses 0x48 through 0x4B.
