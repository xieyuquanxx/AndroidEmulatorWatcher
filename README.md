# Emulator Watcher

PyQt-based desktop app that connects to remote servers over SSH, discovers running Android emulators via `adb`, and continuously streams their screenshots into a multi-panel viewer.

## Features
- Reads available hosts directly from your `~/.ssh/config` file for quick selection.
- Establishes an SSH session using Paramiko and runs all `adb` commands remotely.
- Lists connected emulators (`adb devices`) and lets you start/stop watchers per instance.
- Streams frames by executing `adb -s <serial> exec-out screencap -p` in worker threads and renders them in the GUI with timestamps.
- Supports multiple concurrent emulators; each feed is labeled by its emulator serial and port.
- Provides a manual "Remote adb path" input so you can point to a non-standard `adb` binary on the server.

## Requirements
- Python 3.10 or newer on the local machine.
- The remote server must have Android SDK platform tools (`adb`) installed and available on `PATH`.
- Your `~/.ssh/config` must contain the target host definitions (non-wildcard entries) and the associated SSH keys must be accessible (agent or local files).
- Local machine needs an X server (macOS + Qt is fine) and access to PyQt6.

## Quick Start
1. Install dependencies:
   ```bash
   uv sync
   source .venv/bin/activate
   ```
2. Launch the GUI:
   ```bash
   uv run emulator-watcher
   ```
3. Enter the absolute path to `adb` on the remote server, then select a host and click **Connect**.
4. Click **Refresh Emulators** to list running emulators.
5. Highlight one or more emulators and click **Start Watching** to begin streaming their screens.

## Project Structure
```
src/emulator_watcher/
├── app.py              # PyQt application + main window
├── adb_service.py      # SSH-backed adb helpers and screenshot workers
├── ssh_config.py       # Parser for ~/.ssh/config entries
├── ssh_client.py       # Paramiko session wrapper
├── models.py           # Shared dataclasses
└── widgets/
    └── emulator_panel.py
```

## Known Limitations / Next Steps
- Currently relies on repeated screenshots; for smoother video consider piping `screenrecord` and decoding H.264.
- Workers stop only between screencap calls; cancelling a hung `adb` might need timeouts + channel close.
- No explicit port-forwarding controls; assume emulators run directly on the remote host where `adb` executes.
- Error surfaces mainly via log output; hooking into UI notifications for worker failures would improve UX.

## Logging & Debugging
- The app enables a basic logging configuration; run it from a terminal to view SSH/ADB warnings.
- If your SSH config uses includes or ProxyCommand entries, extend `ssh_config.py` to handle them appropriately.
