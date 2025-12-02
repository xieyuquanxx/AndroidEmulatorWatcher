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
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
}
#emulatorTitle {
    color: #58a6ff;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.3px;
    background-color: transparent;
}
#frameSurface {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 8px;
    color: #8b949e;
}
#emulatorMeta {
    color: #8b949e;
    font-size: 12px;
    letter-spacing: 0.3px;
    background-color: transparent;
}
#emulatorPort {
    color: #7ee787;
    font-size: 13px;
    font-weight: 500;
    background-color: transparent;
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

        # Title with serial
        self.title_label = QLabel(descriptor.serial)
        self.title_label.setObjectName("emulatorTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = self.title_label.font()
        title_font.setPointSize(13)
        title_font.setWeight(QFont.Weight.Bold)
        self.title_label.setFont(title_font)

        # Port info
        self.port_label = QLabel(f"Port: {descriptor.port}")
        self.port_label.setObjectName("emulatorPort")
        self.port_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        port_font = self.port_label.font()
        port_font.setPointSize(11)
        self.port_label.setFont(port_font)

        self.frame_label = QLabel("等待画面...")
        self.frame_label.setObjectName("frameSurface")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumSize(TARGET_WIDTH, TARGET_HEIGHT)
        self.frame_label.setStyleSheet("""
            #frameSurface {
                font-size: 14px;
                color: #58a6ff;
            }
        """)

        self.meta_label = QLabel("空闲")
        self.meta_label.setObjectName("emulatorMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_font = self.meta_label.font()
        meta_font.setPointSize(11)
        meta_font.setWeight(QFont.Weight.Medium)
        self.meta_label.setFont(meta_font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.port_label)
        layout.addWidget(self.frame_label)
        layout.addWidget(self.meta_label)

        # Apply a subtle shadow for depth
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 180))
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
            self.meta_label.setText(f"{local_time.strftime('%H:%M:%S')} 北京时间")
        else:
            self.meta_label.setText("无法解码画面")
