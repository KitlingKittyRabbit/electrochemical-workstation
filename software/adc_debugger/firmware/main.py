import sys
import time
import ubinascii
import ujson
import uselect
from machine import I2C, Pin


I2C_ID = 0
SCL_PIN = 3
SDA_PIN = 10
DEFAULT_ADDRESS = 0x48
RATES = {8: 0, 16: 1, 32: 2, 64: 3, 128: 4, 250: 5, 475: 6, 860: 7}
FSRS = {6.144: 0, 4.096: 1, 2.048: 2, 1.024: 3, 0.512: 4, 0.256: 5}


class ADS1115:
    def __init__(self):
        self.i2c = I2C(I2C_ID, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=100000)
        devices = self.i2c.scan()
        candidates = [address for address in (0x48, 0x49, 0x4A, 0x4B) if address in devices]
        if not candidates:
            raise OSError("ADS1115 not found")
        self.address = candidates[0]
        self.rate = 250
        self.fsr = 4.096

    def configure(self, rate=250, fsr=4.096):
        rate = int(rate)
        fsr = float(fsr)
        if rate not in RATES:
            raise ValueError("unsupported rate")
        if fsr not in FSRS:
            raise ValueError("unsupported fsr")
        self.rate = rate
        self.fsr = fsr

    def sample(self):
        config = (
            (1 << 15)
            | (4 << 12)
            | (FSRS[self.fsr] << 9)
            | (1 << 8)
            | (RATES[self.rate] << 5)
            | 0x03
        )
        self.i2c.writeto(self.address, bytes((0x01, config >> 8, config & 0xFF)))
        time.sleep_ms(max(2, int(1000 / self.rate) + 2))
        self.i2c.writeto(self.address, b"\x00")
        data = self.i2c.readfrom(self.address, 2)
        raw = (data[0] << 8) | data[1]
        if raw & 0x8000:
            raw -= 0x10000
        voltage = raw * self.fsr / 32768.0
        return raw, voltage


def emit(message):
    sys.stdout.write(ujson.dumps(message) + "\n")


def info(adc):
    emit(
        {
            "type": "info",
            "firmware": "ain0-debug-0.1",
            "mac": ubinascii.hexlify(machine.unique_id()).decode(),
            "address": "0x%02X" % adc.address,
            "scl": SCL_PIN,
            "sda": SDA_PIN,
            "channel": "AIN0-GND",
            "rate": adc.rate,
            "fsr": adc.fsr,
        }
    )


import machine


try:
    adc = ADS1115()
except Exception as exc:
    emit({"type": "error", "message": "ADS1115初始化失败: " + str(exc)})
    adc = None

poller = uselect.poll()
poller.register(sys.stdin, uselect.POLLIN)
running = False
sequence = 0

if adc is not None:
    info(adc)

while True:
    events = poller.poll(0)
    if events:
        line = sys.stdin.readline()
        try:
            command = ujson.loads(line)
            name = command.get("cmd")
            if name == "info" and adc is not None:
                info(adc)
            elif name == "scan" and adc is not None:
                emit({"type": "scan", "devices": ["0x%02X" % value for value in adc.i2c.scan()]})
            elif name == "config" and adc is not None:
                adc.configure(command.get("rate", adc.rate), command.get("fsr", adc.fsr))
                emit({"type": "config", "rate": adc.rate, "fsr": adc.fsr})
            elif name == "start" and adc is not None:
                adc.configure(command.get("rate", adc.rate), command.get("fsr", adc.fsr))
                running = True
                sequence = 0
                emit({"type": "state", "running": True})
            elif name == "stop":
                running = False
                emit({"type": "state", "running": False})
            elif name == "sample" and adc is not None:
                raw, voltage = adc.sample()
                emit({"type": "sample", "seq": sequence, "t_ms": time.ticks_ms(), "raw": raw, "voltage": voltage})
                sequence += 1
            elif name == "ping":
                emit({"type": "pong"})
            else:
                emit({"type": "error", "message": "unknown command or ADC unavailable"})
        except Exception as exc:
            emit({"type": "error", "message": str(exc)})

    if running and adc is not None:
        try:
            raw, voltage = adc.sample()
            emit({"type": "sample", "seq": sequence, "t_ms": time.ticks_ms(), "raw": raw, "voltage": voltage})
            sequence += 1
        except Exception as exc:
            running = False
            emit({"type": "error", "message": "采样失败: " + str(exc)})
    else:
        time.sleep_ms(2)
