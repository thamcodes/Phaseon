"""
math_engine.py  —  Raw packets → em_st_artifacts → EEG results.

Calibration modes:
    IAPF (Individual Alpha Peak Frequency):
        Measures the dominant alpha frequency unique to this person.
        Run once at the start. Person should close eyes and relax.
        Takes ~8 seconds. Improves alpha/beta accuracy significantly.

    Baseline:
        Captures the person's resting brain state as a reference point.
        Attention/relaxation values are then expressed relative to this baseline.
        Run after IAPF. Person should sit relaxed with eyes open.
        Takes ~8 seconds.

    Both are just math_engine recalibration with the right mode set.
    The sensor keeps streaming — no need to stop/restart signal.
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

try:
    from em_st_artifacts.utils import lib_settings, support_classes
    from em_st_artifacts import emotional_math
    MATH_OK = True
except ImportError as e:
    print(f"[MathEngine] Import error: {e}")
    MATH_OK = False

EMIT_EVERY = 1


class MathEngine(QObject):
    sig_raw_uv   = pyqtSignal(list)          # [(O1,O2,T3,T4),...] µV
    sig_waves    = pyqtSignal(float, float)  # alpha%, beta%
    sig_metrics  = pyqtSignal(float, float)  # attention%, relaxation%
    sig_calib    = pyqtSignal(int)           # 0-100
    sig_calib_mode = pyqtSignal(str)         # "IAPF" | "Baseline" | "Running"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._math        = None
        self._cb_count    = 0
        self._calib_pct   = 0
        self._calibrated  = False
        self._running     = False   # True after start_calibration() called
        self._setup_math()

    # ── Math engine init ──────────────────────────────────────────────
    def _setup_math(self):
        if not MATH_OK:
            return
        try:
            mls = lib_settings.MathLibSetting(
                sampling_rate=250, process_win_freq=25, n_first_sec_skipped=4,
                fft_window=1000, bipolar_mode=True, channels_number=4,
                channel_for_analysis=0)
            ads = lib_settings.ArtifactDetectSetting(
                art_bord=110, allowed_percent_artpoints=70,
                raw_betap_limit=800_000, global_artwin_sec=4,
                num_wins_for_quality_avg=125, hamming_win_spectrum=True,
                hanning_win_spectrum=False, total_pow_border=400_000_000,
                spect_art_by_totalp=True)
            sads = lib_settings.ShortArtifactDetectSetting()
            mss  = lib_settings.MentalAndSpectralSetting(
                n_sec_for_averaging=2, n_sec_for_instant_estimation=4)

            self._math = emotional_math.EmotionalMath(mls, ads, sads, mss)
            self._math.set_calibration_length(8)
            self._math.set_zero_spect_waves(True, 0, 1, 1, 1, 0)
            self._math.set_spect_normalization_by_bands_width(True)
            self._math.set_mental_estimation_mode(True)
            print("[MathEngine] Ready.")
        except Exception as e:
            print(f"[MathEngine] Setup error: {e}")
            self._math = None

    # ── Public API ────────────────────────────────────────────────────

    def start_calibration(self):
        """
        Initial calibration — called by UIBridge once electrode contact
        is confirmed. IAPF mode: person should close eyes and relax.
        8 seconds. Must complete before baseline.
        """
        if not self._math:
            return
        self._math.start_calibration()
        self._cb_count   = 0
        self._calib_pct  = 0
        self._calibrated = False
        self._running    = True
        self.sig_calib_mode.emit("IAPF")
        print("[MathEngine] IAPF calibration started — eyes closed, relax.")

    def start_baseline(self):
        """
        Baseline calibration — called after IAPF is complete.
        Person should sit relaxed with eyes open.
        Captures resting brain state so attention/relaxation values
        are meaningful relative to THIS person's normal state.
        8 seconds.
        """
        if not self._math:
            return
        if not self._calibrated:
            print("[MathEngine] Run IAPF first before baseline.")
            return
        self._math.start_calibration()
        self._cb_count  = 0
        self._calib_pct = 0
        self.sig_calib_mode.emit("Baseline")
        print("[MathEngine] Baseline calibration started — eyes open, relax.")

    def reset(self):
        """Full reset on device reconnect."""
        self._cb_count   = 0
        self._calib_pct  = 0
        self._calibrated = False
        self._running    = False
        self._setup_math()

    # ── Main packet processing slot ───────────────────────────────────
    @pyqtSlot(list)
    def slot_packet(self, data):
        if not self._math or not data:
            return
        try:
            # Always collect raw µV
            raw_uv = [(s.O1*1e6, s.O2*1e6, s.T3*1e6, s.T4*1e6) for s in data]

            # Always push to math (keeps internal state valid)
            bipolar = [support_classes.RawChannels(s.T3-s.O1, s.T4-s.O2)
                       for s in data]
            self._math.push_data(bipolar)
            self._math.process_data_arr()

            self._cb_count += 1
            if self._cb_count % EMIT_EVERY != 0:
                return

            # UIBridge gates display on contact — just always emit raw
            self.sig_raw_uv.emit(raw_uv)

            if not self._running:
                return

            # ── Calibration progress ──────────────────────────────────
            calib = int(self._math.get_calibration_percents())
            if calib != self._calib_pct:
                self._calib_pct = calib
                self.sig_calib.emit(calib)

            if calib < 100:
                return

            # ── Calibration just completed ────────────────────────────
            if not self._calibrated:
                self._calibrated = True
                self.sig_calib_mode.emit("Running")
                print("[MathEngine] Calibration complete — streaming live data.")

            # ── Spectral (alpha / beta) ───────────────────────────────
            spect = self._math.read_spectral_data_percents_arr()
            if spect:
                last = spect[-1]
                self.sig_waves.emit(
                    float(last.alpha * 100),
                    float(last.beta  * 100))

            # ── Mental (attention / relaxation) ───────────────────────
            mental = self._math.read_mental_data_arr()
            if mental:
                att = float(mental[-1].rel_attention)
                rel = float(mental[-1].rel_relaxation)
                self.sig_metrics.emit(att, rel)

        except Exception as e:
            print(f"[MathEngine] Error: {e}")