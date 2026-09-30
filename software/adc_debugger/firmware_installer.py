from __future__ import annotations

import base64
import struct
import time
from pathlib import Path

import serial
from PySide6.QtCore import QThread, Signal


class FirmwareInstaller(QThread):
    """Install the bundled main.py through MicroPython's raw REPL."""

    progress = Signal(str)
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, port: str, firmware_path: Path) -> None:
        super().__init__()
        self.port = port
        self.firmware_path = firmware_path

    def run(self) -> None:
        device: serial.Serial | None = None
        try:
            code = self.firmware_path.read_bytes()
            self.progress.emit("正在连接设备")
            device = serial.Serial(self.port, 115200, timeout=0.2, write_timeout=1.0)
            self._enter_raw_repl(device)
            self.progress.emit("正在写入设备程序")
            self._write_file(device, code)
            self.progress.emit("正在重启设备")
            device.write(b"\x04")
            time.sleep(1.0)
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if device is not None:
                device.close()

    @staticmethod
    def _read_until(device: serial.Serial, marker: bytes, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        data = bytearray()
        while time.monotonic() < deadline:
            if device.in_waiting:
                data.extend(device.read(device.in_waiting))
                if marker in data:
                    return bytes(data)
            else:
                time.sleep(0.01)
        raise TimeoutError(f"等待设备响应超时: {marker!r}")

    @staticmethod
    def _read_exact(device: serial.Serial, length: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        data = bytearray()
        while len(data) < length and time.monotonic() < deadline:
            chunk = device.read(length - len(data))
            if chunk:
                data.extend(chunk)
            else:
                time.sleep(0.01)
        if len(data) != length:
            raise TimeoutError("读取设备响应超时")
        return bytes(data)

    def _enter_raw_repl(self, device: serial.Serial) -> None:
        device.write(b"\x03\x03")
        time.sleep(0.2)
        device.reset_input_buffer()
        device.write(b"\r\x01")
        self._read_until(device, b"raw REPL; CTRL-B to exit\r\n>", 5.0)

    def _write_file(self, device: serial.Serial, content: bytes) -> None:
        encoded = base64.b64encode(content).decode("ascii")
        chunks = [encoded[index : index + 360] for index in range(0, len(encoded), 360)]
        script = [
            "import ubinascii",
            "f=open('main.py','wb')",
        ]
        script.extend(
            "f.write(ubinascii.a2b_base64(%r))" % chunk for chunk in chunks
        )
        script.extend(["f.close()", "print('INSTALL_OK')"])
        command = ("exec(" + repr("\n".join(script)) + ")\n").encode("utf-8")

        device.write(b"\x05A\x01")
        response = self._read_exact(device, 2, 2.0)
        if response == b"R\x01":
            window_size = struct.unpack("<H", self._read_exact(device, 2, 2.0))[0]
            window_remaining = window_size
            offset = 0
            while offset < len(command):
                if window_remaining == 0:
                    token = self._read_exact(device, 1, 5.0)
                    if token == b"\x01":
                        window_remaining = window_size
                    elif token == b"\x04":
                        raise RuntimeError("设备中止写入")
                    else:
                        raise RuntimeError(f"设备返回未知数据: {token!r}")
                chunk = command[offset : offset + window_remaining]
                device.write(chunk)
                offset += len(chunk)
                window_remaining -= len(chunk)
            device.write(b"\x04")
            self._read_until(device, b"\x04", 10.0)
        else:
            for offset in range(0, len(command), 256):
                device.write(command[offset : offset + 256])
                time.sleep(0.01)
            device.write(b"\x04")
            if self._read_exact(device, 2, 5.0) != b"OK":
                raise RuntimeError("设备未确认文件写入")
