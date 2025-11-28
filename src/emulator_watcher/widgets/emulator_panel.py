from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QColor
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..models import EmulatorDescriptor

TARGET_WIDTH = 360
TARGET_HEIGHT = int(TARGET_WIDTH * (2400 / 1080))
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
PANEL_STYLESHEET = """
#emulatorPanel {
    background-color: #1a1d24;
    border: 1px solid #272c36;
    border-radius: 16px;
}
#emulatorTitle {
    color: #f4f7ff;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
#frameSurface {
    background-color: #10131a;
    border: 1px solid #2c3342;
    border-radius: 12px;
    color: #686f83;
}
#emulatorMeta {
    color: #9aa4ba;
    font-size: 12px;
    letter-spacing: 0.4px;
}
"""


class EmulatorPanel(QWidget):
    """Displays the latest frame for a single emulator."""

    def __init__(
        self, descriptor: EmulatorDescriptor, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.descriptor = descriptor

        self.setObjectName("emulatorPanel")

        self.title_label = QLabel(f"{descriptor.serial} (:{descriptor.port})")
        self.title_label.setObjectName("emulatorTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = self.title_label.font()
        title_font.setPointSize(12)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)

        self.frame_label = QLabel("Waiting for frame...")
        self.frame_label.setObjectName("frameSurface")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumSize(TARGET_WIDTH, TARGET_HEIGHT)

        self.meta_label = QLabel("Idle")
        self.meta_label.setObjectName("emulatorMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_font = self.meta_label.font()
        meta_font.setPointSize(11)
        meta_font.setWeight(QFont.Weight.Medium)
        self.meta_label.setFont(meta_font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.frame_label)
        layout.addWidget(self.meta_label)

        # Apply a subtle shadow so each panel pops against darker dashboards.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(PANEL_STYLESHEET)

    def update_frame(self, frame_bytes: bytes, timestamp: datetime) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(frame_bytes, format="PNG"):
            scaled = pixmap.scaled(
                TARGET_WIDTH,
                TARGET_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.frame_label.setPixmap(scaled)
            local_time = timestamp.astimezone(BEIJING_TZ)
            self.meta_label.setText(
                f"Updated at {local_time.strftime('%H:%M:%S')} Beijing"
            )
        else:
            self.meta_label.setText("Failed to decode frame")
