from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, List

from .models import EmulatorDescriptor, FrameEvent
from .ssh_client import SSHSession

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _WorkerHandle:
    descriptor: EmulatorDescriptor
    stop_event: threading.Event
    thread: threading.Thread


class ADBService:
    """Runs adb commands remotely via SSH and streams emulator frames."""

    def __init__(
        self,
        ssh_session: SSHSession,
        interval: float = 1.0,
        adb_executable: str = "/data7/Users/xyq/develop/gui-agent/sdk/platform-tools/adb",
    ) -> None:
        self.ssh_session = ssh_session
        self.frame_queue: queue.Queue[FrameEvent] = queue.Queue()
        self.interval = interval
        self._workers: Dict[str, _WorkerHandle] = {}
        self._lock = threading.RLock()
        self.adb_executable = adb_executable

    def list_emulators(self) -> List[EmulatorDescriptor]:
        result = self.ssh_session.run(f"{self.adb_executable} devices", timeout=10)
        if not result.ok:
            logger.warning(
                "adb devices failed: %s", result.stderr.decode("utf-8", errors="ignore")
            )
            return []

        lines = result.stdout.decode("utf-8", errors="ignore").splitlines()
        descriptors: List[EmulatorDescriptor] = []
        for line in lines[1:]:
            line = line.strip()
            if not line or "device" not in line:
                continue
            serial, status = line.split()
            if not serial.startswith("emulator-") or status != "device":
                continue
            port = _serial_to_port(serial)
            descriptors.append(EmulatorDescriptor(serial=serial, port=port))
        return descriptors

    def start_stream(self, descriptor: EmulatorDescriptor) -> None:
        with self._lock:
            if descriptor.serial in self._workers:
                return
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._frame_worker,
                name=f"frame-{descriptor.serial}",
                daemon=True,
                args=(descriptor, stop_event),
            )
            self._workers[descriptor.serial] = _WorkerHandle(
                descriptor, stop_event, thread
            )
            thread.start()

    def stop_stream(self, serial: str) -> None:
        with self._lock:
            handle = self._workers.pop(serial, None)
        if handle is None:
            return
        handle.stop_event.set()
        handle.thread.join(timeout=self.interval * 2)

    def stop_all(self) -> None:
        with self._lock:
            serials = list(self._workers.keys())
        for serial in serials:
            self.stop_stream(serial)

    def active_serials(self) -> list[str]:
        with self._lock:
            return list(self._workers.keys())

    def _frame_worker(
        self, descriptor: EmulatorDescriptor, stop_event: threading.Event
    ) -> None:
        command = f"{self.adb_executable} -s {descriptor.serial} exec-out screencap -p"
        while not stop_event.is_set():
            result = self.ssh_session.run(command, timeout=20)
            if result.ok and result.stdout:
                frame_bytes = result.stdout.replace(b"\r\r\n", b"\n")
                self.frame_queue.put(
                    FrameEvent(emulator=descriptor, frame_bytes=frame_bytes)
                )
            else:
                logger.error(
                    "Failed to capture frame for %s: %s",
                    descriptor.serial,
                    result.stderr.decode("utf-8", errors="ignore"),
                )
            stop_event.wait(self.interval)


def _serial_to_port(serial: str) -> int:
    suffix = serial.split("-", maxsplit=1)[-1]
    try:
        return int(suffix)
    except ValueError:
        return -1


# /data7/Users/xyq/develop/gui-agent/sdk/platform-tools/adb
