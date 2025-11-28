from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from paramiko.config import SSHConfig

from .models import SSHHost


class SSHConfigLoader:
    """Loads host definitions from the user's SSH config file."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or Path.home() / ".ssh" / "config"

    def load(self) -> List[SSHHost]:
        if not self.config_path.exists():
            return []

        with self.config_path.open("r", encoding="utf-8") as handle:
            config = SSHConfig()
            config.parse(handle)

        hosts: List[SSHHost] = []
        for host_entry in self._iter_host_entries(config):
            alias = host_entry.get("alias")
            hostname = host_entry.get("hostname")
            if not alias or not hostname:
                continue

            user = host_entry.get("user")
            identity_files = host_entry.get("identityfile") or []
            identity_file = identity_files[0] if identity_files else None
            port = int(host_entry.get("port", 22))

            hosts.append(
                SSHHost(
                    alias=alias,
                    hostname=hostname,
                    user=user,
                    port=port,
                    identity_file=identity_file,
                )
            )
        hosts.sort(key=lambda host: host.alias.lower())
        return hosts

    def _iter_host_entries(self, config: SSHConfig) -> Iterable[dict]:
        for entry in config._config:
            hostnames: list[str] = entry.get("host", [])
            if not hostnames:
                continue
            config_dict = entry.get("config", {})
            for alias in hostnames:
                if any(token in alias for token in ("*", "?")):
                    continue
                yield {
                    "alias": alias,
                    "hostname": config_dict.get("hostname", alias),
                    "user": config_dict.get("user"),
                    "port": config_dict.get("port", 22),
                    "identityfile": config_dict.get("identityfile"),
                }
