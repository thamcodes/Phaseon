from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
import time
import serial
import serial.tools.list_ports

# ── Tunable thresholds ────────────────────────────────────────────────
CLOSE_THRESH = 50    # attention % needed to close fist
OPEN_THRESH  = 30    # attention % must drop below this to open fist
DEBOUNCE_MS  = 600   # milliseconds threshold must hold before acting

# ── Arduino serial settings ───────────────────────────────────────────
BAUD_RATE    = 9600


class ArmController(QObject):
    sig_state = pyqtSignal(str)   # 'O', 'N', or 'C' — for UI image card

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ser          = None
        self._state        = 'OPEN'
        self._last_cmd     = None
        self._close_since  = None
        self._open_since   = None

    # ── Connection ───────────────────────────────────────────────────
    @property
    def is_connected(self):
        return self._ser is not None and self._ser.is_open

    def connect(self, port=None):
        try:
            if port is None:
                port = self._auto_detect()
            if port is None:
                print("[ArmController] No Arduino found.")
                return False
            self._ser = serial.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"[ArmController] Connected on {port}")
            return True
        except Exception as e:
            print(f"[ArmController] Connect error: {e}")
            self._ser = None
            return False

    def disconnect(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser         = None
        self._last_cmd    = None
        self._close_since = None
        self._open_since  = None
        print("[ArmController] Disconnected.")

    def _auto_detect(self):
        keywords = ["Arduino", "CH340", "USB Serial", "USB-SERIAL"]
        for p in serial.tools.list_ports.comports():
            if any(k in (p.description or '') for k in keywords):
                print(f"[ArmController] Auto-detected: {p.device} ({p.description})")
                return p.device
        return None

    # ── Command send ──────────────────────────────────────────────────
    def _send(self, cmd):
        """Send 'C', 'N', or 'O' — only if state actually changed."""
        if cmd == self._last_cmd:
            return
        if not self.is_connected:
            return
        try:
            self._ser.write(cmd.encode())
            self._last_cmd = cmd
            labels = {'C': 'CLOSE fist', 'N': 'NEUTRAL', 'O': 'OPEN fist'}
            print(f"[ArmController] → {labels.get(cmd, cmd)}")
            self.sig_state.emit(cmd)   # update UI image card
        except Exception as e:
            print(f"[ArmController] Send error: {e}")

    # ── Slot: receives (attention, relaxation) from MathEngine ────────
    @pyqtSlot(float, float)
    def slot_metrics(self, attention, relaxation):
        print(f"[ArmController] att={attention:.1f} rel={relaxation:.1f} state={self._state} connected={self.is_connected}")
        now = time.time()

        # ── CLOSE — attention above threshold ─────────────────────────
        if attention >= CLOSE_THRESH:
            if self._close_since is None:
                self._close_since = now
            elif (now - self._close_since) * 1000 >= DEBOUNCE_MS:
                if self._state != 'CLOSED':
                    self._state = 'CLOSED'
                    self._send('C')   # LED blinks
            self._open_since = None

        # ── OPEN — attention below lower threshold ────────────────────
        elif attention < OPEN_THRESH:
            if self._open_since is None:
                self._open_since = now
            elif (now - self._open_since) * 1000 >= DEBOUNCE_MS:
                if self._state != 'OPEN':
                    self._state = 'OPEN'
                    self._send('O')   # LED off
            self._close_since = None

        # ── NEUTRAL — attention between thresholds ────────────────────
        else:
            self._close_since = None
            self._open_since  = None
            if self._state != 'NEUTRAL':
                self._state = 'NEUTRAL'
                self._send('N')       # LED steady on