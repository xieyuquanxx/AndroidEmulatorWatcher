from __future__ import annotations

import logging
import sys
from functools import partial
from pathlib import Path
from queue import Empty
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .adb_service import ADBService, DEFAULT_ADB_PATH
from .models import EmulatorDescriptor
from .ssh_client import SSHSession
from .ssh_config import SSHConfigLoader
from .widgets.emulator_panel import EmulatorPanel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ICON_PATH = PROJECT_ROOT / "assets" / "icon.png"

# UI constants
FRAME_UPDATE_INTERVAL_MS = 200
DEFAULT_WINDOW_WIDTH = 1920
DEFAULT_WINDOW_HEIGHT = 1080
CONTROLS_MIN_WIDTH = 400
GRID_COLUMNS = 2

# Modern stylesheet
MAIN_STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
}

QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}

QLabel {
    color: #c9d1d9;
    background-color: transparent;
}

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: normal;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #484f58;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton#primaryButton {
    background-color: #30363d;
    color: #c9d1d9;
    border-color: #484f58;
}

QPushButton#primaryButton:hover {
    background-color: #484f58;
    border-color: #6e7681;
}

QPushButton#primaryButton:pressed {
    background-color: #21262d;
}

QPushButton#dangerButton {
    background-color: #30363d;
    color: #c9d1d9;
    border-color: #484f58;
}

QPushButton#dangerButton:hover {
    background-color: #484f58;
    border-color: #6e7681;
}

QPushButton#dangerButton:pressed {
    background-color: #21262d;
}

QComboBox {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 28px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #8b949e;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

QLineEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 28px;
}

QLineEdit:hover {
    border-color: #8b949e;
}

QLineEdit:focus {
    border-color: #1f6feb;
    outline: none;
}

QListWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
    font-size: 13px;
}

QListWidget::item {
    background-color: transparent;
    color: #c9d1d9;
    padding: 8px 12px;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:hover {
    background-color: #161b22;
}

QListWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

QScrollArea {
    background-color: #0d1117;
    border: none;
}

QScrollBar:vertical {
    background-color: #0d1117;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0d1117;
    height: 12px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #484f58;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

#controlsContainer {
    background-color: #161b22;
    border-right: 1px solid #21262d;
    padding: 0;
}

#sectionTitle {
    color: #58a6ff;
    font-size: 14px;
    font-weight: 600;
    padding: 8px 0;
    background-color: transparent;
}

#statusLabel {
    background-color: #0d1117;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 12px;
    font-size: 12px;
    font-weight: 500;
}

#statusLabel[status="connected"] {
    background-color: #0d1117;
    color: #3fb950;
    border-color: #238636;
}

#statusLabel[status="error"] {
    background-color: #0d1117;
    color: #f85149;
    border-color: #da3633;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Emulator Watcher")

        self.host_loader = SSHConfigLoader()
        self.hosts = self.host_loader.load()
        self.ssh_session: Optional[SSHSession] = None
        self.adb_service: Optional[ADBService] = None
        self.emulators: dict[str, EmulatorDescriptor] = {}
        self.panels: dict[str, EmulatorPanel] = {}

        self._build_ui()
        self._populate_hosts()

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._drain_frames)
        self.frame_timer.start(FRAME_UPDATE_INTERVAL_MS)

    def _build_ui(self) -> None:
        self.setStyleSheet(MAIN_STYLESHEET)

        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        controls_container = QWidget()
        controls_container.setObjectName("controlsContainer")
        controls_container.setMinimumWidth(CONTROLS_MIN_WIDTH)
        controls_container.setMaximumWidth(CONTROLS_MIN_WIDTH)

        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(20, 20, 20, 20)
        controls_layout.setSpacing(20)

        # Header
        header = QLabel("Emulator Watcher")
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #58a6ff;
            padding: 10px 0;
        """)
        controls_layout.addWidget(header)

        controls_layout.addLayout(self._build_host_controls())
        controls_layout.addLayout(self._build_emulator_controls())
        controls_layout.addStretch()

        self.status_label = QLabel("● Disconnected")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.status_label)

        layout.addWidget(controls_container, 0)
        layout.addWidget(self._build_scroll_area(), 1)

    def _build_host_controls(self) -> QVBoxLayout:
        container = QVBoxLayout()
        container.setSpacing(12)

        # Section title
        section_title = QLabel("SSH 连接")
        section_title.setObjectName("sectionTitle")
        container.addWidget(section_title)

        # Host selector
        host_label = QLabel("SSH 主机:")
        host_label.setStyleSheet("font-size: 12px; color: #8b949e; padding: 4px 0;")
        container.addWidget(host_label)

        self.host_combo = QComboBox()
        self.host_combo.currentIndexChanged.connect(self._update_connect_state)
        container.addWidget(self.host_combo)

        # Buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.refresh_hosts_btn = QPushButton("刷新")
        self.refresh_hosts_btn.clicked.connect(self._populate_hosts)
        self.refresh_hosts_btn.setMaximumWidth(70)

        self.connect_btn = QPushButton("连接")
        self.connect_btn.setObjectName("primaryButton")
        self.connect_btn.clicked.connect(self._handle_connect)

        buttons_row.addWidget(self.refresh_hosts_btn)
        buttons_row.addWidget(self.connect_btn)
        container.addLayout(buttons_row)

        # ADB path
        adb_label = QLabel("远程 ADB 路径:")
        adb_label.setStyleSheet(
            "font-size: 12px; color: #8b949e; padding: 8px 0 4px 0;"
        )
        container.addWidget(adb_label)

        self.adb_path_edit = QLineEdit()
        self.adb_path_edit.setText(DEFAULT_ADB_PATH)
        self.adb_path_edit.setPlaceholderText("输入 adb 可执行文件路径")
        self.adb_path_edit.textChanged.connect(self._update_connect_state)
        container.addWidget(self.adb_path_edit)

        return container

    def _build_emulator_controls(self) -> QVBoxLayout:
        container = QVBoxLayout()
        container.setSpacing(12)

        # Section title
        section_title = QLabel("模拟器管理")
        section_title.setObjectName("sectionTitle")
        container.addWidget(section_title)

        # Refresh button
        self.refresh_emulators_btn = QPushButton("刷新模拟器")
        self.refresh_emulators_btn.clicked.connect(self._refresh_emulators)
        self.refresh_emulators_btn.setEnabled(False)
        container.addWidget(self.refresh_emulators_btn)

        # List label
        list_label = QLabel("可用模拟器:")
        list_label.setStyleSheet("font-size: 12px; color: #8b949e; padding: 4px 0;")
        container.addWidget(list_label)

        self.emulator_list = QListWidget()
        self.emulator_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.emulator_list.setMinimumHeight(200)
        container.addWidget(self.emulator_list)

        # Watch control buttons
        watch_buttons = QHBoxLayout()
        watch_buttons.setSpacing(8)

        self.start_watch_btn = QPushButton("开始监控")
        self.start_watch_btn.setObjectName("primaryButton")
        self.start_watch_btn.clicked.connect(partial(self._set_watch_state, True))
        self.start_watch_btn.setEnabled(False)

        self.stop_watch_btn = QPushButton("停止监控")
        self.stop_watch_btn.setObjectName("dangerButton")
        self.stop_watch_btn.clicked.connect(partial(self._set_watch_state, False))
        self.stop_watch_btn.setEnabled(False)

        watch_buttons.addWidget(self.start_watch_btn)
        watch_buttons.addWidget(self.stop_watch_btn)
        container.addLayout(watch_buttons)

        return container

    def _build_scroll_area(self) -> QScrollArea:
        self.panels_container = QWidget()
        self.panels_container.setStyleSheet("background-color: #0d1117;")

        self.panels_layout = QGridLayout(self.panels_container)
        self.panels_layout.setContentsMargins(20, 20, 20, 20)
        self.panels_layout.setSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.panels_container)
        return scroll

    def _populate_hosts(self) -> None:
        self.hosts = self.host_loader.load()
        self.host_combo.blockSignals(True)
        self.host_combo.clear()
        for host in self.hosts:
            self.host_combo.addItem(host.display_name(), host)
        self.host_combo.blockSignals(False)
        self._update_connect_state()
        if not self.hosts:
            self.status_label.setText("⚠️ ~/.ssh/config 中未找到主机")
            self.status_label.setProperty("status", "error")
            self.status_label.setStyle(self.status_label.style())

    def _handle_connect(self) -> None:
        if self.ssh_session and self.ssh_session.connected:
            self._disconnect()
            return

        index = self.host_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, "No host", "Select an SSH host first")
            return
        host = self.host_combo.currentData()
        assert host is not None
        session = SSHSession(host)
        try:
            session.connect()
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Connection failed", str(exc))
            return
        self.ssh_session = session
        adb_executable = self.adb_path_edit.text().strip() or DEFAULT_ADB_PATH
        self.adb_service = ADBService(session, adb_executable=adb_executable)
        self.connect_btn.setText("断开")
        self.connect_btn.setObjectName("dangerButton")
        self.connect_btn.setStyle(self.connect_btn.style())
        self.refresh_emulators_btn.setEnabled(True)
        self.start_watch_btn.setEnabled(True)
        self.stop_watch_btn.setEnabled(True)
        self.status_label.setText(f"● 已连接到 {host.alias}")
        self.status_label.setProperty("status", "connected")
        self.status_label.setStyle(self.status_label.style())
        self._refresh_emulators()

    def _disconnect(self) -> None:
        if self.adb_service:
            self.adb_service.stop_all()
            self.adb_service = None
        if self.ssh_session:
            self.ssh_session.close()
            self.ssh_session = None
        self.connect_btn.setText("连接")
        self.connect_btn.setObjectName("primaryButton")
        self.connect_btn.setStyle(self.connect_btn.style())
        self.refresh_emulators_btn.setEnabled(False)
        self.start_watch_btn.setEnabled(False)
        self.stop_watch_btn.setEnabled(False)
        self.status_label.setText("● 未连接")
        self.status_label.setProperty("status", "")
        self.status_label.setStyle(self.status_label.style())
        self.emulator_list.clear()
        self.emulators.clear()
        self._clear_panels()

    def _refresh_emulators(self) -> None:
        if not self.adb_service:
            return
        descriptors = self.adb_service.list_emulators()
        self.emulators = {desc.serial: desc for desc in descriptors}
        self.emulator_list.clear()
        for desc in descriptors:
            item = QListWidgetItem(f"{desc.serial} (:{desc.port})")
            item.setData(Qt.ItemDataRole.UserRole, desc.serial)
            self.emulator_list.addItem(item)
        if not descriptors:
            self.status_label.setText("⚠️ 服务器上未检测到模拟器")
            self.status_label.setProperty("status", "error")
            self.status_label.setStyle(self.status_label.style())
        else:
            self.status_label.setText(f"● 已连接 - 发现 {len(descriptors)} 个模拟器")
            self.status_label.setProperty("status", "connected")
            self.status_label.setStyle(self.status_label.style())

    def _set_watch_state(self, start: bool) -> None:
        if not self.adb_service:
            return
        selected_items = self.emulator_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No emulator", "Select one or more emulators")
            return
        for item in selected_items:
            serial = item.data(Qt.ItemDataRole.UserRole)
            descriptor = self.emulators.get(serial)
            if not descriptor:
                continue
            if start:
                self.adb_service.start_stream(descriptor)
                self._ensure_panel(descriptor)
            else:
                self.adb_service.stop_stream(serial)
        if not start:
            self._prune_panels()

    def _ensure_panel(self, descriptor: EmulatorDescriptor) -> None:
        if descriptor.serial in self.panels:
            return
        panel = EmulatorPanel(descriptor)
        self.panels[descriptor.serial] = panel
        self._reflow_panels()

    def _prune_panels(self) -> None:
        active_serials = set(self._active_serials())
        for serial, panel in list(self.panels.items()):
            if serial not in active_serials:
                panel.setParent(None)
                panel.deleteLater()
                del self.panels[serial]
        self._reflow_panels()

    def _active_serials(self) -> list[str]:
        if not self.adb_service:
            return []
        return self.adb_service.active_serials()

    def _clear_panels(self) -> None:
        for panel in self.panels.values():
            panel.setParent(None)
            panel.deleteLater()
        self.panels.clear()
        self._reflow_panels()

    def _update_connect_state(self) -> None:
        has_host = self.host_combo.currentIndex() >= 0
        has_adb = bool(self.adb_path_edit.text().strip())
        self.connect_btn.setEnabled(has_host and has_adb)

    def _drain_frames(self) -> None:
        if not self.adb_service:
            return
        while True:
            try:
                frame = self.adb_service.frame_queue.get_nowait()
            except Empty:
                break
            panel = self.panels.get(frame.emulator.serial)
            if panel:
                panel.update_frame(frame.frame_bytes, frame.timestamp)

    def _reflow_panels(self) -> None:
        # Remove layout references but keep widgets alive for re-adding
        while (item := self.panels_layout.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.panels_container)

        panels = [panel for _, panel in sorted(self.panels.items())]
        count = len(panels)
        if count == 0:
            return
        columns = 1 if count == 1 else GRID_COLUMNS
        for index, panel in enumerate(panels):
            row = index // columns
            col = index % columns
            self.panels_layout.addWidget(panel, row, col)

    def closeEvent(self, event) -> None:
        self._disconnect()
        super().closeEvent(event)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setWindowIcon(_build_app_icon())
    window = MainWindow()
    window.setWindowIcon(app.windowIcon())
    window.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


def _build_app_icon(size: int = 256) -> QIcon:
    """Load the shipping icon from assets with a graceful fallback."""

    if ICON_PATH.exists():
        icon = QIcon(str(ICON_PATH))
        if not icon.isNull():
            return icon
        logging.warning(
            "Failed to load assets/icon.png, falling back to generated icon"
        )
    else:
        logging.warning("assets/icon.png missing, falling back to generated icon")

    return _build_fallback_icon(size)


def _build_fallback_icon(size: int = 256) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    gradient = QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, QColor("#3a7bd5"))
    gradient.setColorAt(1.0, QColor("#00d2ff"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    margin = size * 0.1
    diameter = size - (margin * 2)
    painter.drawRoundedRect(margin, margin, diameter, diameter, 40, 40)

    painter.setPen(QColor("#fefefe"))
    font = QFont("SF Pro Rounded", int(size * 0.35), QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 105)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "EW")
    painter.end()

    icon = QIcon()
    icon.addPixmap(pixmap)
    return icon
