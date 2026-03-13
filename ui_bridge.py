"""
ui_bridge.py  —  All signal → UI updates. 30fps EEG redraw timer.
"""

import time
import numpy as np
from PyQt6.QtCore import QObject, pyqtSlot, QTimer, Qt
from dashboard import CalibrationScreen

RESIST_WARMUP_SEC = 3
RESIST_GOOD       = 500_000
RESIST_OK         = 700_000
FPS               = 30
DOWNSAMPLE        = 2


def _resist_color(ohms):
    if ohms < RESIST_GOOD:   return "#10B981"
    if ohms < RESIST_OK:     return "#F59E0B"
    return "#EF4444"


def _resist_str(ohms):
    if ohms <= 0 or ohms >= 100_000_000:
        return "No contact"
    if ohms >= 1_000_000:
        return f"{ohms/1_000_000:.1f}MΩ"
    return f"{ohms/1_000:.0f}kΩ"


class UIBridge(QObject):

    def __init__(self, dashboard, parent=None):
        super().__init__(parent)
        self._dash          = dashboard
        self._raw_ptr       = 0
        self._y_ranges      = [None] * 4
        self._resist_start  = None
        self._latest_raw    = None
        self._resist_labels = {}        # ch → QLabel for value text
        self._contact_ok    = False     # True only when all 4 electrodes have contact
        self._math_engine   = None      # set in wire()

        # 30fps redraw timer
        self._draw_timer = QTimer()
        self._draw_timer.setInterval(1000 // FPS)
        self._draw_timer.timeout.connect(self._redraw_eeg)

        # FIX #4: build value labels inside each channel's existing v_box
        self._build_resist_labels()

    # ── FIX #4: value labels are already built in dashboard on each led ─
    def _build_resist_labels(self):
        for ch, led in self._dash.quality_leds.items():
            # dashboard.py stores val_lbl directly on the led widget
            self._resist_labels[ch] = led.val_lbl

    # ── Wire everything ───────────────────────────────────────────────
    def wire(self, sensor_worker, math_engine, arm_controller):
        self._math_engine = math_engine

        sensor_worker.sig_status.connect(self._on_status)
        sensor_worker.sig_connected.connect(self._on_connected)
        sensor_worker.sig_resist.connect(self._on_resist)

        math_engine.sig_raw_uv.connect(self._on_raw_uv)
        math_engine.sig_calib.connect(self._on_calib)
        math_engine.sig_calib_mode.connect(self._on_calib_mode)
        math_engine.sig_waves.connect(self._on_waves)
        math_engine.sig_metrics.connect(self._on_metrics)

        # Arm gets metrics only — queued connection ensures it runs in main thread
        math_engine.sig_metrics.connect(
            arm_controller.slot_metrics,
            Qt.ConnectionType.QueuedConnection)

        # Arm state → image card on dashboard
        arm_controller.sig_state.connect(self._dash.update_arm_state)

        self._wire_buttons(sensor_worker, math_engine, arm_controller)
        self._draw_timer.start()
        print("[UIBridge] Wired.")

    # ── Button wiring ─────────────────────────────────────────────────
    def _wire_buttons(self, sw, me, arm):
        dash = self._dash

        # Disconnect dashboard's own button handlers first
        for btn in [dash.btn_connect, dash.btn_arduino,
                    dash.btn_iapf, dash.btn_baseline]:
            try:
                btn.clicked.disconnect()
            except Exception:
                pass

        # ── Connect Device ─────────────────────────────────────────
        def _toggle_device():
            if dash.btn_connect.isChecked():
                # FIX #5: update the badge immediately before scanning
                dash.btn_connect.setText("Scanning...")
                dash.btn_connect.setEnabled(False)
                dash.device_badge.setText(" ● Scanning... ")
                dash.device_badge.setStyleSheet(
                    "background-color:#FEF3C7;color:#D97706;"
                    "border-radius:15px;padding:5px 15px;font-weight:bold;")
                self._resist_start = None
                self._contact_ok   = False
                sw.start_worker()
            else:
                sw.stop_worker()
                self._reset_ui()

        dash.btn_connect.clicked.connect(_toggle_device)

        # ── Connect Arduino ────────────────────────────────────────
        def _toggle_arduino():
            if dash.btn_arduino.isChecked():
                dash.btn_arduino.setEnabled(False)
                dash.btn_arduino.setText("Connecting...")
                from PyQt6.QtWidgets import QApplication
                QApplication.processEvents()
                ok = arm.connect(port=getattr(dash, 'arduino_port', None))
                dash.btn_arduino.setEnabled(True)
                if ok:
                    dash.btn_arduino.setText("Disconnect Arduino")
                    dash.arduino_badge.setText(" ● Arduino Connected ")
                    dash.arduino_badge.setStyleSheet(
                        "background-color:#D1FAE5;color:#059669;"
                        "border-radius:15px;padding:5px 15px;font-weight:bold;")
                else:
                    dash.btn_arduino.setChecked(False)
                    dash.btn_arduino.setText("Connect Arduino")
                    dash.arduino_badge.setText(" ● Connection Failed ")
                    dash.arduino_badge.setStyleSheet(
                        "background-color:#FEE2E2;color:#EF4444;"
                        "border-radius:15px;padding:5px 15px;font-weight:bold;")
            else:
                arm.disconnect()
                dash.btn_arduino.setText("Connect Arduino")
                dash.arduino_badge.setText(" ● Arduino Disconnected ")
                dash.arduino_badge.setStyleSheet(
                    "background-color:#FEE2E2;color:#EF4444;"
                    "border-radius:15px;padding:5px 15px;font-weight:bold;")

        dash.btn_arduino.clicked.connect(_toggle_arduino)

        # IAPF — eyes closed, relax, find alpha peak frequency
        def _do_iapf():
            if not self._contact_ok:
                self._dash.card_state.update_data("!", "Put headband on first")
                return
            self._calibrated_once = False
            me.start_calibration()
            dash.btn_iapf.setChecked(False)
            # Show fullscreen overlay
            self._calib_screen = CalibrationScreen("IAPF")
            self._calib_screen.show()

        # Baseline — eyes open, relax, capture resting state
        def _do_baseline():
            if not self._contact_ok:
                self._dash.card_state.update_data("!", "Put headband on first")
                return
            me.start_baseline()
            dash.btn_baseline.setChecked(False)
            # Show fullscreen overlay
            self._calib_screen = CalibrationScreen("Baseline")
            self._calib_screen.show()

        dash.btn_iapf.clicked.connect(_do_iapf)
        dash.btn_baseline.clicked.connect(_do_baseline)

        # Close event
        def _close(event):
            sw.stop_worker()
            arm.disconnect()
            self._draw_timer.stop()
            event.accept()

        dash.closeEvent = _close

    # ── Status → state card subtext ───────────────────────────────────
    @pyqtSlot(str)
    def _on_status(self, msg):
        print(f"[Status] {msg}")
        try:
            self._dash.card_state.lbl_sub.setText(msg)
        except Exception:
            pass

    # ── Connected / disconnected ──────────────────────────────────────
    @pyqtSlot(bool)
    def _on_connected(self, ok):
        dash = self._dash
        dash.btn_connect.setEnabled(True)
        if ok:
            dash.btn_connect.setText("Disconnect")
            dash.btn_connect.setChecked(True)
            dash.device_badge.setText(" ● Device Connected ")
            dash.device_badge.setStyleSheet(
                "background-color:#D1FAE5;color:#059669;"
                "border-radius:15px;padding:5px 15px;font-weight:bold;")
            dash.card_state.update_data("Adjust", "Waiting for electrode contact...")
        else:
            # Only reset badge if user has actually stopped scanning
            # (btn_connect unchecked). If still checked, we're retrying — keep
            # the badge as "Scanning..." so it doesn't flicker to Disconnected.
            if not dash.btn_connect.isChecked():
                dash.btn_connect.setText("Connect Device")
                dash.device_badge.setText(" ● Device Disconnected ")
                dash.device_badge.setStyleSheet(
                    "background-color:#FEE2E2;color:#EF4444;"
                    "border-radius:15px;padding:5px 15px;font-weight:bold;")
                self._reset_ui()
            else:
                # Still scanning — keep badge orange, re-enable button
                dash.btn_connect.setText("Scanning...")
                dash.btn_connect.setEnabled(False)
                dash.device_badge.setText(" ● Scanning... ")
                dash.device_badge.setStyleSheet(
                    "background-color:#FEF3C7;color:#D97706;"
                    "border-radius:15px;padding:5px 15px;font-weight:bold;")
                self._reset_ui(keep_scanning=True)

    # ── Resistance ────────────────────────────────────────────────────
    @pyqtSlot(dict)
    def _on_resist(self, resist):
        # Warmup guard
        if self._resist_start is None:
            self._resist_start = time.time()
        if time.time() - self._resist_start < RESIST_WARMUP_SEC:
            for ch in resist:
                self._set_led_grey(ch, "...")
            return

        # FIX #4: update each channel's LED + value label
        for ch, ohms in resist.items():
            led   = self._dash.quality_leds.get(ch)
            lbl   = self._resist_labels.get(ch)
            color = _resist_color(ohms)
            val   = _resist_str(ohms)

            if led:
                led.setStyleSheet(
                    f"background-color:{color};border-radius:7px;"
                    f"border:1px solid #9CA3AF;")
            if lbl:
                lbl.setText(val)
                lbl.setStyleSheet(
                    f"font-size:9px;font-weight:bold;color:{color};"
                    f"border:none;margin:0px;padding:0px;")

        # FIX #2 & #3: start calibration only when ALL channels have contact
        if not self._contact_ok:
            all_good = all(
                0 < v < RESIST_OK for v in resist.values()
            )
            if all_good:
                self._contact_ok = True
                print("[UIBridge] Good contact — starting calibration.")
                self._dash.card_state.update_data("0%", "Calibrating — stay still")
                if self._math_engine:
                    self._math_engine.start_calibration()

    def _set_led_grey(self, ch, text="---"):
        led = self._dash.quality_leds.get(ch)
        lbl = self._resist_labels.get(ch)
        if led:
            led.setStyleSheet(
                "background-color:#D1D5DB;border-radius:7px;"
                "border:1px solid #9CA3AF;")
        if lbl:
            lbl.setText(text)
            lbl.setStyleSheet(
                "font-size:9px;font-weight:bold;color:#9CA3AF;"
                "border:none;margin:0px;padding:0px;")

    # ── Raw EEG buffer update (BLE rate) ─────────────────────────────
    @pyqtSlot(list)
    def _on_raw_uv(self, packet):
        # FIX #3: ignore data if contact not confirmed yet
        if not self._contact_ok:
            return

        arr  = np.array(packet).T   # [4, n]
        n    = arr.shape[1]
        buf  = self._dash.raw_buffer
        dlen = self._dash.data_len
        ptr  = self._raw_ptr
        end  = ptr + n

        if end <= dlen:
            buf[:, ptr:end] = arr
        else:
            first = dlen - ptr
            buf[:, ptr:]      = arr[:, :first]
            buf[:, :end-dlen] = arr[:, first:]

        self._raw_ptr    = end % dlen
        self._latest_raw = True

    # ── EEG redraw at 30fps ───────────────────────────────────────────
    def _redraw_eeg(self):
        if not self._latest_raw:
            return
        self._latest_raw = None

        buf  = self._dash.raw_buffer
        dlen = self._dash.data_len
        p    = self._raw_ptr

        display = (buf if p == 0
                   else np.concatenate([buf[:, p:], buf[:, :p]], axis=1))

        for i in range(4):
            ch = display[i, ::DOWNSAMPLE].copy()
            ch -= float(np.mean(ch))          # remove DC offset
            self._dash.curves[i].setData(ch)

            # FIX #1: set Y range independently per channel
            if self._y_ranges[i] is None:
                nonzero = ch[np.abs(ch) > 1]
                if len(nonzero) > 20:
                    peak = float(np.percentile(np.abs(nonzero), 95))
                    if peak > 5:
                        self._y_ranges[i] = peak * 1.5
                        self._dash.plots[i].setYRange(
                            -self._y_ranges[i],
                             self._y_ranges[i],
                            padding=0)

    # ── Alpha / Beta ──────────────────────────────────────────────────
    @pyqtSlot(float, float)
    def _on_waves(self, alpha, beta):
        if not self._contact_ok:    # FIX #3: gate on contact
            return
        ab = self._dash.alpha_buffer
        bb = self._dash.beta_buffer
        ab = np.roll(ab, -1); ab[-1] = alpha
        bb = np.roll(bb, -1); bb[-1] = beta
        self._dash.alpha_buffer = ab
        self._dash.beta_buffer  = bb
        self._dash.curve_alpha.setData(ab)
        self._dash.curve_beta.setData(bb)

    # ── Attention / Relaxation ────────────────────────────────────────
    @pyqtSlot(float, float)
    def _on_metrics(self, att, rel):
        if not self._contact_ok:    # FIX #3: gate on contact
            return
        self._dash.odometer.update_values(att)
        if att > 60:
            self._dash.card_state.update_data("Focus", "Closing grip...")
        elif rel > 60:
            self._dash.card_state.update_data("Relax", "Opening grip...")
        else:
            self._dash.card_state.update_data("Neutral", "Monitoring...")

    # ── Calibration mode change ───────────────────────────────────────
    @pyqtSlot(str)
    def _on_calib_mode(self, mode):
        if mode == "IAPF":
            self._dash.card_state.update_data("IAPF", "Close eyes & relax...")
        elif mode == "Baseline":
            self._dash.card_state.update_data("Base", "Eyes open, stay still...")
        elif mode == "Running":
            self._dash.card_state.update_data("Live", "Streaming data!")

    # ── Calibration progress ──────────────────────────────────────────
    @pyqtSlot(int)
    def _on_calib(self, pct):
        if not self._contact_ok:
            return
        if pct < 100:
            current_val = self._dash.card_state.lbl_value.text()
            self._dash.card_state.update_data(
                current_val, f"Calibrating... {pct}%")
        else:
            self._dash.card_state.update_data("✓", "Calibration complete!")
            # Auto-close the fullscreen overlay when done
            if hasattr(self, '_calib_screen') and self._calib_screen:
                self._calib_screen.close()
                self._calib_screen = None

    # ── Full UI reset ─────────────────────────────────────────────────
    def _reset_ui(self, keep_scanning=False):
        dash = self._dash
        dash.raw_buffer[:]   = 0
        dash.alpha_buffer[:] = 0
        dash.beta_buffer[:]  = 0
        self._raw_ptr        = 0
        self._y_ranges       = [None] * 4
        self._resist_start   = None
        self._latest_raw     = None
        self._contact_ok     = False

        if not keep_scanning:
            dash.odometer.update_values(0)
            dash.card_state.update_data("-", "Waiting for data...")

        for ch in self._dash.quality_leds:
            self._set_led_grey(ch, "---")

        for i in range(4):
            dash.curves[i].setData([])
            dash.plots[i].setYRange(-50, 50)

        dash.curve_alpha.setData([])
        dash.curve_beta.setData([])
        self._y_ranges = [None] * 4