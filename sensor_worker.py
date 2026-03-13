"""
sensor_worker.py
────────────────
Single responsibility: find the BrainBit/NeiryBCI headband,
connect to it, and stream raw sample packets + resistance readings.

Emits:
    sig_status(str)     — human-readable status messages
    sig_connected(bool) — True on connect, False on genuine drop
    sig_packet(list)    — raw sample objects from neurosdk
    sig_resist(dict)    — {O1, O2, T3, T4} resistance in Ohms
"""

import time
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from neurosdk.scanner import Scanner
    from neurosdk.cmn_types import SensorFamily, SensorCommand
    SDK_OK = True
except ImportError as e:
    print(f"[SensorWorker] Import error: {e}")
    SDK_OK = False

SCAN_TIMEOUT    = 7     # seconds to scan for device
STAB_DELAY      = 3     # seconds after connect before sending commands
CMD_RETRIES     = 3     # command retry attempts
CMD_RETRY_WAIT  = 2     # seconds between retries
WATCHDOG_SEC    = 15    # seconds without a packet before assuming dropped
                        # (BLE can gap naturally — don't be too aggressive)
KEEPALIVE_MS    = 200   # main loop polling interval in ms


class SensorWorker(QThread):
    sig_status    = pyqtSignal(str)
    sig_connected = pyqtSignal(bool)
    sig_packet    = pyqtSignal(list)
    sig_resist    = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running        = False
        self._last_packet_t = 0.0

    # ── BLE callbacks — called from neurosdk's internal thread ───────
    def _on_signal(self, sensor, data):
        if not self.running or not data:
            return
        self._last_packet_t = time.time()
        self.sig_packet.emit(list(data))

    def _on_resist(self, sensor, data):
        if not self.running:
            return
        self.sig_resist.emit({
            'O1': float(data.O1),
            'O2': float(data.O2),
            'T3': float(data.T3),
            'T4': float(data.T4),
        })

    # ── Main loop: keeps retrying until stop_worker() is called ──────
    def run(self):
        self.running = True
        if not SDK_OK:
            self.sig_status.emit("neurosdk not installed.")
            return

        while self.running:
            self._run_session()
            if self.running:
                self.sig_status.emit("Reconnecting in 3s...")
                # Sleep in small chunks so stop_worker() is responsive
                for _ in range(30):
                    if not self.running:
                        break
                    self.msleep(100)

    def _run_session(self):
        sensor        = None
        scanner       = None
        was_connected = False

        try:
            # ── Scan ─────────────────────────────────────────────────
            self.sig_status.emit("Scanning for headband...")
            scanner = Scanner([
                SensorFamily.LEHeadband,
                SensorFamily.LEBrainBit,
                SensorFamily.LEBrainBit2,
            ])
            scanner.start()

            # Full scan duration — check for stop every 500ms
            elapsed = 0
            while elapsed < SCAN_TIMEOUT * 1000:
                self.msleep(500)
                elapsed += 500
                if not self.running:
                    scanner.stop()
                    return
                # Early exit if device already found
                if scanner.sensors():
                    break

            scanner.stop()

            found = scanner.sensors()
            if not found:
                self.sig_status.emit("No device found — retrying...")
                return   # Loop retries — do NOT emit sig_connected(False)

            # ── Connect ───────────────────────────────────────────────
            sensor = scanner.create_sensor(found[0])
            sensor.signalDataReceived = self._on_signal
            sensor.resistDataReceived = self._on_resist

            self.sig_status.emit(f"Connected → {found[0].Name}")
            self.sig_connected.emit(True)
            was_connected = True

            # BLE stabilisation delay — full 3 seconds, no early exit
            self.msleep(STAB_DELAY * 1000)

            # ── Start streaming with retry ────────────────────────────
            for attempt in range(CMD_RETRIES):
                try:
                    if sensor.is_supported_command(SensorCommand.StartSignalAndResist):
                        sensor.exec_command(SensorCommand.StartSignalAndResist)
                    else:
                        sensor.exec_command(SensorCommand.StartResist)
                        sensor.exec_command(SensorCommand.StartSignal)
                    print(f"[SensorWorker] Streaming started.")
                    break
                except Exception as e:
                    print(f"[SensorWorker] Command attempt {attempt+1} failed: {e}")
                    if attempt < CMD_RETRIES - 1:
                        self.msleep(CMD_RETRY_WAIT * 1000)
                    else:
                        raise

            self._last_packet_t = time.time()

            # ── Watchdog keep-alive loop ──────────────────────────────
            while self.running:
                self.msleep(KEEPALIVE_MS)
                gap = time.time() - self._last_packet_t
                if gap > WATCHDOG_SEC:
                    self.sig_status.emit(
                        f"No data for {int(gap)}s — reconnecting...")
                    print(f"[SensorWorker] Watchdog triggered after {gap:.1f}s")
                    break

        except Exception as e:
            self.sig_status.emit(f"Error: {e}")
            print(f"[SensorWorker] Exception: {e}")

        finally:
            # ── Clean stop ────────────────────────────────────────────
            if sensor:
                try:
                    if sensor.is_supported_command(SensorCommand.StopSignalAndResist):
                        sensor.exec_command(SensorCommand.StopSignalAndResist)
                    else:
                        try: sensor.exec_command(SensorCommand.StopSignal)
                        except Exception: pass
                        try: sensor.exec_command(SensorCommand.StopResist)
                        except Exception: pass
                except Exception:
                    pass
                try:
                    del sensor
                except Exception:
                    pass
            if scanner:
                try:
                    del scanner
                except Exception:
                    pass

            # Only tell UI we disconnected if we were actually connected
            # — not on every failed scan attempt (keeps badge as Scanning...)
            if was_connected:
                self.sig_connected.emit(False)

    # ── Public control ────────────────────────────────────────────────
    def start_worker(self):
        if not self.isRunning():
            self.running = True
            self.start()

    def stop_worker(self):
        self.running = False
        self.quit()
        self.wait(5000)