from __future__ import annotations

import threading
from typing import Optional

import paramiko

from .models import RunResult, SSHHost


class SSHSession:
    """Thin wrapper around Paramiko's SSHClient with convenience helpers."""

    def __init__(
        self, host: SSHHost, timeout: float = 10.0, banner_timeout: float = 30.0
    ) -> None:
        self.host = host
        self.timeout = timeout
        self.banner_timeout = banner_timeout
        self._client: Optional[paramiko.SSHClient] = None
        self._lock = threading.RLock()

    def __enter__(self) -> "SSHSession":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        with self._lock:
            if self._client is not None:
                return

            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=self.host.hostname,
                port=self.host.port,
                username=self.host.user,
                timeout=self.timeout,
                banner_timeout=self.banner_timeout,
                allow_agent=True,
                look_for_keys=True,
                key_filename=self.host.identity_file,
            )
            self._client = client

    def close(self) -> None:
        with self._lock:
            if self._client is None:
                return
            self._client.close()
            self._client = None

    def run(self, command: str, timeout: Optional[float] = None) -> RunResult:
        client = self._ensure_client()
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read()
        err = stderr.read()
        exit_status = stdout.channel.recv_exit_status()
        return RunResult(command=command, stdout=out, stderr=err, exit_code=exit_status)

    def _ensure_client(self) -> paramiko.SSHClient:
        if self._client is None:
            self.connect()
        assert self._client is not None  # for type checkers
        return self._client
