from __future__ import annotations

import logging
import sys
from functools import partial
from queue import Empty
from typing import Dict, List, Optional

from PyQt6.QtCore import QTimer
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

from .adb_service import ADBService
from .models import EmulatorDescriptor
from .ssh_client import SSHSession
from .ssh_config import SSHConfigLoader
from .widgets.emulator_panel import EmulatorPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Emulator Watcher")

        self.host_loader = SSHConfigLoader()
        self.hosts = self.host_loader.load()
        self.ssh_session: Optional[SSHSession] = None
        self.adb_service: Optional[ADBService] = None
        self.emulators: Dict[str, EmulatorDescriptor] = {}
        self.panels: Dict[str, EmulatorPanel] = {}

        self._build_ui()
        self._populate_hosts()

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._drain_frames)
        self.frame_timer.start(200)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)

        controls_container = QWidget()
        controls_container.setMinimumWidth(400)
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.addLayout(self._build_host_controls())
        controls_layout.addLayout(self._build_emulator_controls())
        controls_layout.addStretch()
        self.status_label = QLabel("Disconnected")
        controls_layout.addWidget(self.status_label)

        layout.addWidget(controls_container, 0)
        layout.addWidget(self._build_scroll_area(), 1)

    def _build_host_controls(self) -> QVBoxLayout:
        container = QVBoxLayout()

        top_row = QHBoxLayout()
        self.host_combo = QComboBox()
        self.refresh_hosts_btn = QPushButton("Reload Hosts")
        self.refresh_hosts_btn.clicked.connect(self._populate_hosts)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._handle_connect)

        top_row.addWidget(QLabel("SSH Host:"))
        self.host_combo.currentIndexChanged.connect(self._update_connect_state)
        top_row.addWidget(self.host_combo)
        top_row.addWidget(self.refresh_hosts_btn)
        top_row.addWidget(self.connect_btn)

        adb_row = QHBoxLayout()
        self.adb_path_edit = QLineEdit()
        self.adb_path_edit.setPlaceholderText("/usr/bin/adb or leave empty")
        self.adb_path_edit.textChanged.connect(self._update_connect_state)
        adb_row.addWidget(QLabel("Remote adb path:"))
        adb_row.addWidget(self.adb_path_edit)

        container.addLayout(top_row)
        container.addLayout(adb_row)
        return container

    def _build_emulator_controls(self) -> QVBoxLayout:
        container = QVBoxLayout()

        self.emulator_list = QListWidget()
        self.emulator_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        buttons = QHBoxLayout()
        self.refresh_emulators_btn = QPushButton("Refresh Emulators")
        self.refresh_emulators_btn.clicked.connect(self._refresh_emulators)
        self.refresh_emulators_btn.setEnabled(False)

        self.start_watch_btn = QPushButton("Start Watching")
        self.start_watch_btn.clicked.connect(partial(self._set_watch_state, True))
        self.start_watch_btn.setEnabled(False)

        self.stop_watch_btn = QPushButton("Stop Watching")
        self.stop_watch_btn.clicked.connect(partial(self._set_watch_state, False))
        self.stop_watch_btn.setEnabled(False)

        buttons.addWidget(self.refresh_emulators_btn)
        buttons.addWidget(self.start_watch_btn)
        buttons.addWidget(self.stop_watch_btn)

        container.addWidget(QLabel("Available Emulators"))
        container.addWidget(self.emulator_list)
        container.addLayout(buttons)
        return container

    def _build_scroll_area(self) -> QScrollArea:
        self.panels_container = QWidget()
        self.panels_layout = QGridLayout(self.panels_container)

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
            self.status_label.setText("No hosts found in ~/.ssh/config")

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
        adb_executable = (
            self.adb_path_edit.text().strip()
            or "/data7/Users/xyq/develop/gui-agent/sdk/platform-tools/adb"
        )
        self.adb_service = ADBService(session, adb_executable=adb_executable)
        self.connect_btn.setText("Disconnect")
        self.refresh_emulators_btn.setEnabled(True)
        self.start_watch_btn.setEnabled(True)
        self.stop_watch_btn.setEnabled(True)
        self.status_label.setText(f"Connected to {host.alias}")
        self._refresh_emulators()

    def _disconnect(self) -> None:
        if self.adb_service:
            self.adb_service.stop_all()
            self.adb_service = None
        if self.ssh_session:
            self.ssh_session.close()
            self.ssh_session = None
        self.connect_btn.setText("Connect")
        self.refresh_emulators_btn.setEnabled(False)
        self.start_watch_btn.setEnabled(False)
        self.stop_watch_btn.setEnabled(False)
        self.status_label.setText("Disconnected")
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
            item.setData(256, desc.serial)  # custom role
            self.emulator_list.addItem(item)
        if not descriptors:
            self.status_label.setText("No emulators detected on server")

    def _set_watch_state(self, start: bool) -> None:
        if not self.adb_service:
            return
        selected_items = self.emulator_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No emulator", "Select one or more emulators")
            return
        for item in selected_items:
            serial = item.data(256)
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

    def _active_serials(self) -> List[str]:
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
        columns = 1 if count == 1 else 2
        for index, panel in enumerate(panels):
            row = index // columns
            col = index % columns
            self.panels_layout.addWidget(panel, row, col)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._disconnect()
        super().closeEvent(event)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s"
    )
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1920, 1080)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
