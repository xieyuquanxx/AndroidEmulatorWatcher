# Emulator Watcher Architecture

## Goals
- Provide a desktop GUI that allows selecting an SSH host defined in the system `~/.ssh/config` file.
- Establish an SSH tunnel to the selected server using Paramiko and launch `adb` commands remotely.
- Discover Android emulators (`adb devices`) and stream their screen contents via `adb exec-out screencap -p`.
- Render multiple emulator feeds concurrently in the Python GUI, labeling each feed by the emulator port.
- Allow starting/stopping individual feeds without blocking the UI thread.

## Technology Choices
- **Python 3.10+** for type hinting and `asyncio`/`threading` support.
- **PyQt6** for a responsive, multi-panel GUI with image rendering.
- **Paramiko** to parse `~/.ssh/config` and manage SSH sessions, port-forwarding if required.
- **ADB CLI** executed on the remote server to interface with Android emulators.
- **Pillow (PIL)** optional for image post-processing if future transformations are required; PyQt can ingest PNG bytes directly, so dependency stays optional.

## High-Level Components
1. **Config Layer (`ssh_config.py`)**
   - Parses `~/.ssh/config` using `paramiko.config.SSHConfig`.
   - Exposes structured entries with hostname, user, port, identity file.
   - Provides filtering and refresh utilities for the GUI.

2. **Connection Layer (`ssh_client.py`)**
   - Wraps Paramiko `SSHClient` with context management.
   - Handles connection lifecycle, authentication (keys/agent), and command execution helpers.
   - Provides a reusable `run` helper returning stdout/stderr plus a streaming method for long-lived commands.

3. **ADB Service (`adb_service.py`)**
   - Uses `SSHClient` to run `adb devices` and parse emulator serials (e.g., `emulator-5554`).
   - Spawns background worker threads per emulator that repeatedly call `adb exec-out screencap -p` and push frames to a `Queue`.
   - Each worker tags frames with the emulator serial/port for routing to the GUI.

4. **GUI Layer (`app.py`, `widgets/`)**
   - Main window hosts:
     - SSH host selector (list or combo box) populated from config layer.
     - Refresh buttons for hosts and connected emulators.
     - Scrollable grid of emulator panels; each panel contains the latest frame as a `QLabel` pixmap and metadata (serial, fps, last update time).
   - Uses `QTimer` or `Signal`/`Slot` connections to consume frame queues from worker threads without blocking the UI thread.

5. **State/Models (`models.py`)**
   - Dataclasses for SSH host entry, emulator descriptor, and frame events.
   - Central store to let GUI query current sessions and feed statuses.

6. **Threading & Safety**
   - Worker threads run blocking SSH `exec_command` loops to fetch screenshots.
   - Use `queue.Queue` per emulator for frames; GUI consumes via timer.
   - Provide clean shutdown by signaling workers and closing SSH sessions on app exit.

## Workflow
1. Launch app → load ssh config → populate host selector.
2. User selects host → app establishes SSH connection lazily when user clicks "Connect".
3. Once connected, `adb_service` queries `adb devices` to list emulators; show list with checkboxes.
4. User toggles emulators to watch → start worker thread per emulator.
5. Worker loops: `adb -s <serial> exec-out screencap -p`, convert response to `QImage`, post to queue.
6. GUI timer updates each panel with the latest pixmap.
7. On disconnect/exit, stop workers, close SSH connection.

## Future Enhancements
- Add port-forwarding controls for `adb` if remote server not running emulators locally.
- Support video streaming via `adb shell screenrecord --output-format=h264` piped to decoder.
- Persist favorite hosts/emulators and user layout preferences.
- Integrate metrics (CPU, battery) alongside screenshots.
