# Open Electrochemical Workstation

An open research prototype for cyclic-voltammetry (CV) and open-circuit
potential (OCPT) experiments. The repository contains the editable board
project, an ESP32-S3 display prototype, and a desktop ADC debugging tool for an
ESP32-C3/ADS1115 acquisition board.

This is laboratory prototype hardware. It is not a certified medical,
industrial, or safety instrument.

## Repository contents

```text
hardware/board/                 Editable board project, schematic, and BOM
hardware/display/               Display-module sourcing notes
firmware/display-s3-35002/      ESP32-S3 display and resistive-touch firmware
software/adc_debugger/          Desktop GUI and MicroPython device program
```

Vendor datasheets and original vendor archives are intentionally not
redistributed. Obtain the documents for the Hongxun 35002 display,
CL35BC219-40A panel, ST7796S controller, and XPT2046 touch controller from the
manufacturer or your supplier.

The private development repository also contains contributed calibration data.
That data is omitted from this release until its redistribution permission is
documented.

## ADC debugger

The desktop application streams AIN0 readings from an ESP32-C3 connected to an
ADS1115.

```bash
cd software/adc_debugger
python -m pip install -r requirements.txt
./run_linux.sh
```

See [`software/adc_debugger/README.md`](software/adc_debugger/README.md) for
device installation, Windows packaging, and troubleshooting.

## ESP32-S3 display firmware

Install [PlatformIO](https://platformio.org/), connect an ESP32-S3 SuperMini,
and run:

```bash
cd firmware/display-s3-35002
pio run -e esp32-s3-supermini
pio run -e esp32-s3-supermini -t upload
pio device monitor -b 115200
```

The firmware initializes an ST7796S display, draws a visual test pattern, and
performs a five-point XPT2046 resistive-touch calibration. Wiring and validation
details are documented in the firmware directory.

## Hardware status

- Board design files and the exported schematic are included.
- Display firmware builds under PlatformIO.
- Desktop software supports Linux and Windows packaging.
- Hardware behavior still requires validation on the exact assembled board and
  display revision used by the reader.

Please document board revisions, component substitutions, measurement setup,
and firmware commits when reporting results.

## Licensing

Different artifact types use different licenses:

- software and firmware: Apache-2.0;
- original hardware design files: CERN-OHL-P-2.0;
- original documentation and photographs: CC-BY-4.0.

See [LICENSES.md](LICENSES.md). Third-party names and specifications remain the
property of their respective owners and are not relicensed by this repository.

## Safety and research disclaimer

Review input protection, grounding, isolation, electrode compatibility, and
power limits before connecting the prototype to a cell or external instrument.
The maintainers make no claim of measurement accuracy, regulatory compliance,
or fitness for a particular purpose.

A Chinese snapshot of the original project overview is retained at
[`docs/README.zh-CN.md`](docs/README.zh-CN.md).
