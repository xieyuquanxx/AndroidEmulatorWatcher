from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class SSHHost:
    """Represents an entry from ~/.ssh/config."""

    alias: str
    hostname: str
    user: Optional[str] = None
    port: int = 22
    identity_file: Optional[str] = None

    def display_name(self) -> str:
        user_prefix = f"{self.user}@" if self.user else ""
        return f"{self.alias} ({user_prefix}{self.hostname}:{self.port})"


@dataclass(slots=True)
class EmulatorDescriptor:
    """Metadata describing a single Android emulator instance."""

    serial: str  # e.g., emulator-5554
    port: int


@dataclass(slots=True)
class FrameEvent:
    """Frame data emitted by an emulator streaming worker."""

    emulator: EmulatorDescriptor
    frame_bytes: bytes
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class RunResult:
    """Standardized response from SSH command execution."""

    command: str
    stdout: bytes
    stderr: bytes
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0
