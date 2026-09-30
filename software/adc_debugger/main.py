from __future__ import annotations

import csv
import json
import math
import os
import queue
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

if sys.platform.startswith("linux"):
    local_qt_lib = Path(__file__).resolve().parent / "runtime" / "linux" / "usr" / "lib" / "x86_64-linux-gnu"
    if local_qt_lib.is_dir():
        os.environ["LD_LIBRARY_PATH"] = str(local_qt_lib) + (
            os.pathsep + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else ""
        )

import serial
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCloseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from firmware_installer import FirmwareInstaller


APP_NAME = "Electrochemical ADC Debugger"
DEFAULT_FSR = 4.096
DEFAULT_RATE = 250
BIAS_VOLTAGE = 1.65
R13_KOHM = 10.0
WINDOW_SECONDS = 10.0


def discover_ports() -> list[tuple[str, str]]:
    """Return serial ports with a useful label and the actual device path."""
    ports: list[tuple[str, str]] = []
    for item in sorted(list_ports.comports(), key=lambda value: value.device):
        is_usb_serial = item.vid is not None and item.pid is not None
        if os.name != "nt" and not is_usb_serial and not item.device.startswith(("/dev/ttyACM", "/dev/ttyUSB")):
            continue
        description = item.description or "串口设备"
        if item.vid is not None and item.pid is not None:
            description = f"{description} [{item.vid:04X}:{item.pid:04X}]"
        if item.vid == 0x303A and item.pid == 0x1001:
            description = f"ESP32-C3 USB JTAG/串口，{description}"
        ports.append((f"{item.device}  {description}", item.device))
    return ports


class SerialWorker(QThread):
    connected = Signal(str)
    disconnected = Signal()
    sample_received = Signal(dict)
    info_received = Signal(dict)
    log_message = Signal(str)
    error_message = Signal(str)

    def __init__(self, port: str) -> None:
        super().__init__()
        self.port = port
        self._commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop_event = threading.Event()
        self._serial: serial.Serial | None = None

    def send(self, command: dict[str, Any]) -> None:
        self._commands.put(command)

    def stop(self) -> None:
        self._stop_event.set()
        if self._serial is not None:
            self._serial.cancel_read()
        self.wait(1500)

    def run(self) -> None:
        try:
            self._serial = serial.Serial(
                self.port,
                baudrate=115200,
                timeout=0.1,
                write_timeout=0.5,
            )
            self.connected.emit(self.port)
            self._send_now({"cmd": "info"})
        except (serial.SerialException, OSError) as exc:
            self.error_message.emit(f"打开串口失败: {exc}")
            return

        try:
            while not self._stop_event.is_set():
                self._flush_commands()
                raw_line = self._serial.readline()
                if raw_line:
                    self._handle_line(raw_line)
        finally:
            if self._serial is not None:
                self._serial.close()
            self._serial = None
            self.disconnected.emit()

    def _flush_commands(self) -> None:
        if self._serial is None:
            return
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            self._send_now(command)

    def _send_now(self, command: dict[str, Any]) -> None:
        if self._serial is None:
            return
        payload = (json.dumps(command, separators=(",", ":")) + "\n").encode()
        try:
            self._serial.write(payload)
        except (serial.SerialException, OSError) as exc:
            self.error_message.emit(f"发送失败: {exc}")

    def _handle_line(self, raw_line: bytes) -> None:
        text = raw_line.decode("utf-8", errors="replace").strip()
        if not text:
            return
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            self.log_message.emit(text)
            return

        message_type = message.get("type")
        if message_type == "sample":
            self.sample_received.emit(message)
        elif message_type == "samples":
            for sample in message.get("data", []):
                if isinstance(sample, dict):
                    self.sample_received.emit(sample)
        elif message_type == "info":
            self.info_received.emit(message)
        elif message_type == "error":
            self.error_message.emit(str(message.get("message", message)))
        else:
            self.log_message.emit(text)


class PlotCanvas(QWidget):
    """Small dependency-free scrolling plot for the portable build."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(620, 420)
        self._x: list[float] = []
        self._y: list[float] = []
        self._y_min = -1.65
        self._y_max = 1.65

    def set_data(self, x_values: list[float], y_values: list[float]) -> None:
        self._x = x_values
        self._y = y_values
        self.update()

    def clear(self) -> None:
        self._x = []
        self._y = []
        self.update()

    def set_y_range(self, minimum: float, maximum: float) -> None:
        self._y_min = minimum
        self._y_max = maximum
        self.update()

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111827"))

        left, top, right, bottom = 64, 32, 20, 48
        plot_width = max(1, self.width() - left - right)
        plot_height = max(1, self.height() - top - bottom)

        grid_pen = QPen(QColor("#334155"), 1)
        painter.setPen(grid_pen)
        for index in range(7):
            x = left + plot_width * index / 6
            painter.drawLine(int(x), top, int(x), top + plot_height)
        for index in range(5):
            y = top + plot_height * index / 4
            painter.drawLine(left, int(y), left + plot_width, int(y))

        axis_pen = QPen(QColor("#94a3b8"), 1)
        painter.setPen(axis_pen)
        painter.drawRect(left, top, plot_width, plot_height)
        painter.drawText(8, 20, "放大后输出 - BIAS")
        painter.drawText(8, top + plot_height // 2, "V")
        painter.drawText(left, self.height() - 12, "-10 s")
        painter.drawText(left + plot_width - 36, self.height() - 12, "0 s")
        painter.drawText(left - 58, top + plot_height + 4, f"{self._y_min:g}")
        painter.drawText(left - 12, top + plot_height // 2 + 4, "0")
        painter.drawText(left - 48, top + 4, f"{self._y_max:g}")

        if len(self._x) < 2:
            return
        x_min = self._x[0]
        x_max = self._x[-1]
        x_span = x_max - x_min
        if x_span <= 0:
            x_span = 1.0

        path = QPainterPath()
        for index, (x_value, y_value) in enumerate(zip(self._x, self._y)):
            x = left + (x_value - x_min) / x_span * plot_width
            normalized = (y_value - self._y_min) / (self._y_max - self._y_min)
            y = top + (1.0 - max(0.0, min(1.0, normalized))) * plot_height
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.setPen(QPen(QColor("#55d6be"), 2))
        painter.drawPath(path)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 780)

        self.worker: SerialWorker | None = None
        self.installer: FirmwareInstaller | None = None
        self.samples: deque[tuple[float, float, int, float, float, float]] = deque(maxlen=5000)
        self.session_start = time.monotonic()
        self.total_samples = 0
        self.current_fsr = DEFAULT_FSR
        self.current_rate = DEFAULT_RATE
        self.advanced_mode = False
        self.protocol_ready = False
        self.save_dialog: QFileDialog | None = None
        self.pending_capture: list[tuple[float, float, int, float, float, float]] = []

        self._build_ui()
        self._refresh_ports()

        self.port_timer = QTimer(self)
        self.port_timer.timeout.connect(self._refresh_ports)
        self.port_timer.start(1500)

        self.plot_timer = QTimer(self)
        self.plot_timer.timeout.connect(self._refresh_plot)
        self.plot_timer.start(100)

        QTimer.singleShot(800, self._auto_connect)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addLayout(self._build_connection_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        control_scroll = QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        control_scroll.setWidget(self._build_control_panel())
        control_scroll.setMinimumWidth(340)
        splitter.addWidget(control_scroll)
        splitter.addWidget(self._build_plot_panel())
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setPlaceholderText("设备日志和通信信息")
        self.log.setMaximumHeight(130)
        self.log.setVisible(False)
        root.addWidget(self.log)

        self.clear_log_button = QPushButton("清空日志")
        self.clear_log_button.clicked.connect(self.log.clear)
        self.clear_log_button.setVisible(False)
        root.addWidget(self.clear_log_button, 0, Qt.AlignmentFlag.AlignRight)

    def _build_connection_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel("设备"))

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(360)
        self.port_combo.setVisible(False)
        layout.addWidget(self.port_combo)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self._refresh_ports)
        self.refresh_button.setVisible(False)
        layout.addWidget(self.refresh_button)

        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self._toggle_connection)
        layout.addWidget(self.connect_button)

        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #9a6700; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.device_label = QLabel("正在检测 ESP32-C3...")
        layout.addWidget(self.device_label, 1)

        self.advanced_button = QPushButton("高级模式")
        self.advanced_button.setCheckable(True)
        self.advanced_button.toggled.connect(self._toggle_advanced_mode)
        layout.addWidget(self.advanced_button)
        return layout

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.config_group = QGroupBox("ADC 配置")
        config_form = QFormLayout(self.config_group)

        self.rate_combo = QComboBox()
        for rate in (8, 16, 32, 64, 128, 250, 475, 860):
            self.rate_combo.addItem(f"{rate} SPS", rate)
        self.rate_combo.setCurrentIndex(self.rate_combo.findData(DEFAULT_RATE))
        config_form.addRow("采样率", self.rate_combo)

        self.fsr_combo = QComboBox()
        for fsr in (0.256, 0.512, 1.024, 2.048, 4.096, 6.144):
            self.fsr_combo.addItem(f"±{fsr:g} V", fsr)
        self.fsr_combo.setCurrentIndex(self.fsr_combo.findData(DEFAULT_FSR))
        config_form.addRow("量程", self.fsr_combo)

        self.apply_button = QPushButton("应用配置")
        self.apply_button.clicked.connect(self._apply_config)
        config_form.addRow(self.apply_button)
        self.config_group.setVisible(False)
        layout.addWidget(self.config_group)

        gain_group = QGroupBox("放大参数")
        gain_form = QFormLayout(gain_group)
        self.r12_spin = QDoubleSpinBox()
        self.r12_spin.setRange(0.0, 100.0)
        self.r12_spin.setDecimals(2)
        self.r12_spin.setSingleStep(1.0)
        self.r12_spin.setValue(10.0)
        self.r12_spin.setSuffix(" kΩ")
        self.r12_spin.valueChanged.connect(self._refresh_plot)
        gain_form.addRow("R12电阻", self.r12_spin)
        gain_form.addRow("R13电阻", QLabel(f"{R13_KOHM:g} kΩ（固定）"))
        layout.addWidget(gain_group)

        action_group = QGroupBox("采集")
        action_layout = QVBoxLayout(action_group)
        self.start_button = QPushButton("开始采集")
        self.start_button.clicked.connect(self._start_stream)
        action_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("停止采集")
        self.stop_button.clicked.connect(self._stop_stream)
        self.stop_button.setEnabled(False)
        action_layout.addWidget(self.stop_button)
        self.save_button = QPushButton("保存检测区 CSV")
        self.save_button.clicked.connect(self._save_capture)
        action_layout.addWidget(self.save_button)
        self.save_status = QLabel("尚未保存检测数据")
        self.save_status.setWordWrap(True)
        self.save_status.setStyleSheet("color: #64748b;")
        action_layout.addWidget(self.save_status)
        self.clear_capture_button = QPushButton("清空检测区")
        self.clear_capture_button.clicked.connect(self._clear_capture)
        action_layout.addWidget(self.clear_capture_button)
        self.self_test_button = QPushButton("设备自检")
        self.self_test_button.clicked.connect(self._self_test)
        self.self_test_button.setVisible(False)
        action_layout.addWidget(self.self_test_button)
        self.setup_button = QPushButton("一键准备设备")
        self.setup_button.clicked.connect(self._install_firmware)
        action_layout.addWidget(self.setup_button)
        layout.addWidget(action_group)

        stats_group = QGroupBox("AIN0 实时统计")
        stats_form = QFormLayout(stats_group)
        self.stat_labels: dict[str, QLabel] = {}
        for key, label in (
            ("r12", "R12电阻"),
            ("gain", "放大倍数"),
            ("pre_voltage", "放大前电压"),
            ("post_voltage", "放大后电压"),
            ("adc_voltage", "ADC输出"),
            ("raw", "原始码"),
            ("mean", "窗口平均"),
            ("minimum", "窗口最小"),
            ("maximum", "窗口最大"),
            ("peak_to_peak", "峰峰值"),
            ("rms", "交流 RMS"),
            ("count", "样本数"),
        ):
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.stat_labels[key] = value
            stats_form.addRow(label, value)
        layout.addWidget(stats_group)

        self.last_error = QLabel("")
        self.last_error.setWordWrap(True)
        self.last_error.setStyleSheet("color: #b42318;")
        layout.addWidget(self.last_error)
        layout.addStretch(1)
        return panel

    def _toggle_advanced_mode(self, enabled: bool) -> None:
        self.advanced_mode = enabled
        self.port_combo.setVisible(enabled)
        self.refresh_button.setVisible(enabled)
        self.config_group.setVisible(enabled)
        self.self_test_button.setVisible(enabled)
        self.log.setVisible(enabled)
        self.clear_log_button.setVisible(enabled)
        self.advanced_button.setText("收起高级模式" if enabled else "高级模式")

    def _auto_connect(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            if self.port_combo.count() > 0:
                self._toggle_connection()

    def _build_plot_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.plot = PlotCanvas()
        self.plot.set_y_range(-1.65, 1.65)
        layout.addWidget(self.plot)
        return panel

    def _refresh_ports(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        selected = self.port_combo.currentData()
        ports = discover_ports()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for label, device in ports:
            self.port_combo.addItem(label, device)
        if selected:
            index = self.port_combo.findData(selected)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        self.port_combo.blockSignals(False)
        if self.worker is None or not self.worker.isRunning():
            if ports:
                self.device_label.setText(f"已发现设备：{ports[0][1]}")
            else:
                self.device_label.setText("未发现 ESP32-C3，请检查 USB 连接")

    def _toggle_connection(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._disconnect_device()
            return
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "没有串口", "请先插入设备或刷新串口列表。")
            return

        self.worker = SerialWorker(port)
        self.worker.connected.connect(self._on_connected)
        self.worker.disconnected.connect(self._on_disconnected)
        self.worker.sample_received.connect(self._on_sample)
        self.worker.info_received.connect(self._on_info)
        self.worker.log_message.connect(self._append_log)
        self.worker.error_message.connect(self._on_error)
        self.worker.start()
        self.connect_button.setText("断开")
        self.status_label.setText("连接中")

    def _disconnect_device(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self._on_disconnected()

    def _on_connected(self, port: str) -> None:
        self.protocol_ready = False
        self.status_label.setText(f"已连接：{port}")
        self.status_label.setStyleSheet("color: #16803c; font-weight: bold;")
        self.device_label.setText("设备已连接，正在等待采集程序")
        self._append_log(f"已连接 {port}")
        QTimer.singleShot(1800, self._show_uninitialized_state)

    def _on_disconnected(self) -> None:
        self.protocol_ready = False
        self.status_label.setText("未连接")
        self.status_label.setStyleSheet("color: #9a6700; font-weight: bold;")
        self.connect_button.setText("连接")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.device_label.setText("未发现 ESP32-C3，请检查 USB 连接")
        self._append_log("设备已断开")

    def _on_info(self, message: dict[str, Any]) -> None:
        self.protocol_ready = True
        firmware = message.get("firmware", "未知固件")
        address = message.get("address", "?")
        mac = message.get("mac", "?")
        self.device_label.setText(f"固件：{firmware} | 地址：{address} | MAC：{mac}")
        self._append_log(json.dumps(message, ensure_ascii=False))

    def _show_uninitialized_state(self) -> None:
        if self.worker is not None and self.worker.isRunning() and not self.protocol_ready:
            self.device_label.setText("设备已连接，但未安装采集程序，请点击“一键准备设备”")

    def _on_error(self, message: str) -> None:
        self.last_error.setText(message)
        self._append_log(f"错误：{message}")

    def _append_log(self, message: str) -> None:
        self.log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _send(self, command: dict[str, Any]) -> bool:
        if self.worker is None or not self.worker.isRunning():
            self._on_error("设备未连接")
            return False
        self.worker.send(command)
        return True

    def _apply_config(self) -> None:
        rate = int(self.rate_combo.currentData())
        fsr = float(self.fsr_combo.currentData())
        self.current_rate = rate
        self.current_fsr = fsr
        self._send({"cmd": "config", "rate": rate, "fsr": fsr})

    def _start_stream(self) -> None:
        if not self._send(
            {
                "cmd": "start",
                "rate": int(self.rate_combo.currentData()),
                "fsr": float(self.fsr_combo.currentData()),
            }
        ):
            return
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.last_error.clear()

    def _stop_stream(self) -> None:
        self._send({"cmd": "stop"})
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _self_test(self) -> None:
        self._send({"cmd": "scan"})
        self._send({"cmd": "sample"})

    def _install_firmware(self) -> None:
        if self.installer is not None and self.installer.isRunning():
            return
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "没有串口", "请先插入设备。")
            return
        if self.worker is not None and self.worker.isRunning():
            self._disconnect_device()

        base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        firmware_path = base_path / "firmware" / "main.py"
        if not firmware_path.is_file():
            self._on_error(f"找不到设备程序：{firmware_path}")
            return

        self.setup_button.setEnabled(False)
        self.status_label.setText("正在初始化设备")
        self.installer = FirmwareInstaller(port, firmware_path)
        self.installer.progress.connect(self._append_log)
        self.installer.succeeded.connect(self._on_install_succeeded)
        self.installer.failed.connect(self._on_install_failed)
        self.installer.start()

    def _on_install_succeeded(self) -> None:
        self.setup_button.setEnabled(True)
        self._append_log("设备初始化完成")
        self.status_label.setText("设备已初始化，正在重连")
        QTimer.singleShot(1500, self._reconnect_after_install)

    def _on_install_failed(self, message: str) -> None:
        self.setup_button.setEnabled(True)
        self.status_label.setText("设备初始化失败")
        self._on_error(f"设备初始化失败：{message}")

    def _reconnect_after_install(self) -> None:
        self._refresh_ports()
        if self.worker is None or not self.worker.isRunning():
            self._toggle_connection()

    def _on_sample(self, sample: dict[str, Any]) -> None:
        try:
            timestamp = float(sample.get("t_ms", 0)) / 1000.0
            raw = int(sample["raw"])
            adc_voltage = float(sample.get("voltage", raw * self.current_fsr / 32768.0))
            voltage = adc_voltage - BIAS_VOLTAGE
        except (KeyError, TypeError, ValueError):
            self._append_log(f"无法解析采样：{sample}")
            return

        r12 = self.r12_spin.value()
        gain = self._current_gain()
        self.samples.append((timestamp, voltage, raw, adc_voltage, r12, gain))
        self.total_samples += 1

    def _current_gain(self) -> float:
        return 1.0 + self.r12_spin.value() / R13_KOHM

    def _clear_capture(self) -> None:
        self.samples.clear()
        self.total_samples = 0
        self.plot.clear()
        for label in self.stat_labels.values():
            label.setText("-")
        self._append_log("已清空检测区")

    def _refresh_plot(self) -> None:
        if not self.samples:
            return
        data = list(self.samples)
        timestamps = [row[0] for row in data]
        voltages = [row[1] for row in data]
        adc_voltages = [row[3] for row in data]
        pre_voltages = [row[1] / row[5] for row in data]
        relative_time = [value - timestamps[-1] for value in timestamps]
        self.plot.set_data(relative_time, voltages)

        window = voltages[-max(2, int(self.current_rate * WINDOW_SECONDS)) :]
        gain = data[-1][5]
        mean = sum(window) / len(window)
        minimum = min(window)
        maximum = max(window)
        centered = [value - mean for value in window]
        values = {
            "r12": f"{data[-1][4]:.2f} kΩ",
            "gain": f"{gain:.3f}×",
            "pre_voltage": f"{pre_voltages[-1]:.6f} V",
            "post_voltage": f"{voltages[-1]:.6f} V",
            "raw": str(data[-1][2]),
            "adc_voltage": f"{adc_voltages[-1]:.6f} V",
            "mean": f"{mean:.6f} V",
            "minimum": f"{minimum:.6f} V",
            "maximum": f"{maximum:.6f} V",
            "peak_to_peak": f"{maximum - minimum:.6f} V",
            "rms": f"{math.sqrt(sum(value * value for value in centered) / len(centered)):.6f} V",
            "count": str(self.total_samples),
        }
        for key, value in values.items():
            self.stat_labels[key].setText(value)

    def _save_capture(self) -> None:
        if not self.samples:
            self.save_status.setText("没有可保存的数据，请先开始采集")
            self.save_status.setStyleSheet("color: #b42318;")
            self._on_error("检测区没有数据可保存")
            return

        if self.save_dialog is not None and self.save_dialog.isVisible():
            self.save_dialog.activateWindow()
            self.save_dialog.raise_()
            return

        try:
            save_dir = Path.home() / "ADC_Debugger_Data"
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = "AIN0_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
            self.pending_capture = list(self.samples)
            dialog = QFileDialog(self, "保存检测区 CSV")
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            dialog.setNameFilter("CSV 文件 (*.csv)")
            dialog.setDefaultSuffix("csv")
            dialog.setDirectory(str(save_dir))
            dialog.selectFile(filename)
            dialog.fileSelected.connect(self._write_capture)
            dialog.rejected.connect(lambda: self._on_save_cancelled())
            dialog.finished.connect(lambda _result: self._clear_save_dialog(dialog))
            self.save_dialog = dialog
            dialog.open()
        except OSError as exc:
            self.save_status.setText(f"保存失败：{exc}")
            self.save_status.setStyleSheet("color: #b42318;")
            self._on_error(f"无法准备保存：{exc}")

    def _write_capture(self, filename: str) -> None:
        path = Path(filename)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        try:
            with open(path, "w", newline="", encoding="utf-8") as record_file:
                writer = csv.writer(record_file)
                writer.writerow(
                    [
                        "time_s",
                        "raw",
                        "adc_voltage_v",
                        "zeroed_output_v",
                        "r12_kohm",
                        "gain",
                        "pre_amplification_v",
                    ]
                )
                for timestamp, zeroed, raw, adc_voltage, r12, gain in self.pending_capture:
                    writer.writerow(
                        [
                            timestamp,
                            raw,
                            f"{adc_voltage:.9f}",
                            f"{zeroed:.9f}",
                            f"{r12:.2f}",
                            f"{gain:.6f}",
                            f"{zeroed / gain:.9f}",
                        ]
                    )
            self.save_status.setText(f"已保存 {len(self.pending_capture)} 条数据\n{path}")
            self.save_status.setStyleSheet("color: #16803c;")
            self._append_log(f"已保存检测区数据：{path}")
        except OSError as exc:
            self.save_status.setText(f"保存失败：{exc}")
            self.save_status.setStyleSheet("color: #b42318;")
            self._on_error(f"无法保存文件：{exc}")

    def _on_save_cancelled(self) -> None:
        self.save_status.setText("已取消保存")
        self.save_status.setStyleSheet("color: #64748b;")

    def _clear_save_dialog(self, dialog: QFileDialog) -> None:
        if self.save_dialog is dialog:
            self.save_dialog = None
        dialog.deleteLater()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.installer is not None and self.installer.isRunning():
            self.installer.wait(1500)
        self._disconnect_device()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
