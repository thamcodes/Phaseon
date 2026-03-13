"""
File - dashboard.py is the front-end. It has a Sidebar and Content Area.

The Sidebar consists of 4 buttons: Connect/Disconnect Device, Connect/Disconnect Arduino, IAPF Calibration 
and Baseline Calibration. Along with buttons, it has a Resistance indicator that shows the value of 
resistance faced by each electrode.

The Content Area consists of: Attention-Relaxation Odometer, Dominant State card, Recording card, Arm State card
Alpha-Beta graph, Raw EEG graph.
"""

# Import Libraries
"""
The libraries are:
> os - interacting with os
> sys - variables used by python interpretor
> numpy - numerical operations
> pyqtgraph - high performance graphics and GUI
> PyQt6 - bindings for Qt framework
> datetime - classes for manipulating date & time
"""
import os
import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFrame, QGraphicsDropShadowEffect, QGridLayout)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPixmap
from datetime import datetime


# Color Scheme
bg_color        = "#F3F4F6"  # Cool Gray
white_color     = "#FFFFFF"  # White
primary_color   = "#059669"  # Emerald Green
attention_color = "#047857"  # Deep Teal Green
relax_color     = "#34D399"  # Mint Green
beta_color      = "#EF4444"  # Coral Red
alpha_color     = "#10B981"  # Emerald
text_dark_color  = "#1F2937" # Dark Slate
text_light_color = "#9CA3AF" # Medium Gray
accent_red_color = "#EF4444" # Coral Red


# Calibration Screen Overlay
""" It displays a screen overlay when IAPF and Baseline calibration is happening. """
class CalibrationScreen(QWidget):
    def __init__(self, mode_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration In Progress")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setStyleSheet("background-color: black;")
        self.showFullScreen()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        layout.addStretch()

        self.lbl_status = QLabel(f"Calibrating {mode_name}...")
        self.lbl_status.setStyleSheet(f"color: {relax_color}; font-size: 48px; font-weight: bold;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        lbl_sub = QLabel("Please remain still and relax.")
        lbl_sub.setStyleSheet("color: #888; font-size: 24px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)
        layout.addStretch()

        self.btn_cancel = QPushButton("Cancel / Exit")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setFixedSize(200, 60)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent_red_color}; color: white;
                border-radius: 10px; font-size: 18px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #C53030; }}
        """)
        self.btn_cancel.clicked.connect(self.close)

        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(self.btn_cancel)
        btn_container.addStretch()
        layout.addLayout(btn_container)
        layout.addSpacing(50)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(30000)


# ── Attention / Relaxation arc odometer ──────────────────────────────
class MentalOdometer(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(340, 180)
        self.setStyleSheet(f"background-color: {white_color}; border-radius: 16px;")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        self.attention  = 0
        self.relaxation = 0

    def update_values(self, att):
        self.attention  = int(max(0, min(100, att)))
        self.relaxation = 100 - self.attention
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w         = self.width()
        x, y      = 40, 25
        rect_size = w - 80
        rect      = QRectF(x, y, rect_size, rect_size)
        arc_w     = 25

        # Background arc
        painter.setPen(QPen(QColor("#E5E7EB"), arc_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(rect, 180 * 16, -180 * 16)

        # Attention arc
        att_deg = (self.attention / 100.0) * 180
        painter.setPen(QPen(QColor(attention_color), arc_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(rect, 180 * 16, int(-att_deg * 16))

        # Relaxation arc
        rel_deg = (self.relaxation / 100.0) * 180
        painter.setPen(QPen(QColor(relax_color), arc_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(rect, int((180 - att_deg) * 16), int(-rel_deg * 16))

        # Percentage numbers
        painter.setFont(QFont('Roboto', 28, QFont.Weight.Bold))
        painter.setPen(QColor(attention_color))
        painter.drawText(QRectF(x, y+60, rect_size/2, 50), Qt.AlignmentFlag.AlignCenter, f"{self.attention}%")
        painter.setPen(QColor(relax_color))
        painter.drawText(QRectF(x+rect_size/2, y+60, rect_size/2, 50), Qt.AlignmentFlag.AlignCenter, f"{self.relaxation}%")

        # Labels
        painter.setFont(QFont('Roboto', 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(attention_color), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPoint(int(x + rect_size/4 - 35), int(y + 120))
        painter.setPen(QColor(text_dark_color))
        painter.drawText(QRectF(x, y+110, rect_size/2, 20), Qt.AlignmentFlag.AlignCenter, "Attention")
        painter.setPen(QPen(QColor(relax_color), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPoint(int(x + rect_size*0.75 - 38), int(y + 120))
        painter.setPen(QColor(text_dark_color))
        painter.drawText(QRectF(x+rect_size/2, y+110, rect_size/2, 20), Qt.AlignmentFlag.AlignCenter, "Relaxation")


# ── Stat card ─────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, title, value, subtext, is_primary=False):
        super().__init__()
        self.setFixedSize(220, 180)
        if is_primary:
            bg, text_main, text_sub = primary_color, white_color, "#D1FAE5"
        else:
            bg, text_main, text_sub = white_color, text_dark_color, text_light_color
        self.setStyleSheet(f"background-color: {bg}; border-radius: 15px;")
        if not is_primary:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setColor(QColor(0, 0, 0, 15))
            shadow.setOffset(0, 4)
            self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {text_sub}; font-size: 13px; font-weight: 600;")
        layout.addWidget(lbl_title)
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: {text_main}; font-size: 32px; font-weight: bold;")
        layout.addWidget(self.lbl_value)
        self.lbl_sub = QLabel(subtext)
        self.lbl_sub.setStyleSheet(f"color: {text_sub}; font-size: 11px;")
        layout.addWidget(self.lbl_sub)

    def update_data(self, new_val, new_sub):
        self.lbl_value.setText(str(new_val))
        self.lbl_sub.setText(str(new_sub))


# ── Main dashboard window ─────────────────────────────────────────────
class PhaseonDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.arduino_serial  = None
        self.arduino_port    = 'COM3'
        self.recording_start = None

        self.setWindowTitle("Phaseon - Interface")
        self.resize(1280, 900)
        self.setStyleSheet(f"background-color: {bg_color}; font-family: 'Roboto';")

        # Data buffers
        self.data_len    = 500
        self.channels    = ['O1', 'O2', 'T3', 'T4']
        self.raw_buffer  = np.zeros((4, self.data_len))
        self.alpha_buffer = np.zeros(self.data_len)
        self.beta_buffer  = np.zeros(self.data_len)

        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QHBoxLayout(central)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(0)

        self._init_sidebar()
        self._init_content()

        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

    # ── Sidebar ───────────────────────────────────────────────────────
    def _init_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {white_color};
                border-right: 1px solid #E5E7EB;
                border-radius: 15px;
            }}
            QLabel {{
                color: {text_light_color};
                font-weight: bold;
                padding-left: 10px;
                margin-top: 10px;
            }}
            QPushButton {{
                text-align: left; padding: 12px 20px;
                border: none; border-radius: 10px;
                color: {text_dark_color}; font-weight: 600; font-size: 14px;
            }}
            QPushButton:hover   {{ background-color: #EBF4DD; }}
            QPushButton:checked {{ background-color: {primary_color}; color: white; }}
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 30, 20, 20)
        layout.setSpacing(20)

        brand = QLabel("Dashboard")
        brand.setStyleSheet(
            f"color: {primary_color}; font-size: 24px; font-weight: 800;"
            "padding-left: 5px; margin-bottom: 20px; border: none;")
        layout.addWidget(brand)

        # Buttons
        self.btn_connect  = QPushButton("Connect Device")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self.toggle_device)
        layout.addWidget(self.btn_connect)

        self.btn_arduino  = QPushButton("Connect Arduino")
        self.btn_arduino.setCheckable(True)
        self.btn_arduino.clicked.connect(self.toggle_arduino)
        layout.addWidget(self.btn_arduino)

        self.btn_iapf     = QPushButton("IAPF Calibration")
        self.btn_iapf.setCheckable(True)
        layout.addWidget(self.btn_iapf)

        self.btn_baseline = QPushButton("Baseline Calibration")
        self.btn_baseline.setCheckable(True)
        layout.addWidget(self.btn_baseline)

        # Resistance indicators
        layout.addSpacing(10)
        res_title = QLabel("Resistance")
        res_title.setStyleSheet(f"color: {text_dark_color}; font-size: 14px;")
        layout.addWidget(res_title)

        quality_container = QFrame()
        quality_container.setStyleSheet("border: none; border-radius: 10px; padding: 5px;")
        q_layout = QGridLayout(quality_container)
        q_layout.setSpacing(8)

        self.quality_leds = {}
        channels = [('O1', 0, 0), ('O2', 0, 1), ('T3', 1, 0), ('T4', 1, 1)]

        for ch, row, col in channels:
            v_box = QVBoxLayout()
            v_box.setSpacing(2)

            led = QLabel()
            led.setFixedSize(14, 14)
            led.setStyleSheet(
                "background-color: #D1D5DB; border-radius: 7px;"
                "border: 1px solid #9CA3AF;")

            ch_lbl = QLabel(ch)
            ch_lbl.setStyleSheet(
                f"font-size: 10px; color: {text_light_color};"
                "font-weight: normal; margin-top: 0px; border: none;")
            ch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Value label — shows kΩ / MΩ / No contact
            val_lbl = QLabel("---")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(
                "font-size: 9px; font-weight: bold; color: #9CA3AF;"
                "border: none; margin: 0px; padding: 0px;")

            v_box.addWidget(led,    alignment=Qt.AlignmentFlag.AlignCenter)
            v_box.addWidget(ch_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            v_box.addWidget(val_lbl,alignment=Qt.AlignmentFlag.AlignCenter)

            q_layout.addLayout(v_box, row, col)
            self.quality_leds[ch] = led
            # Store val_lbl reference so UIBridge can find it
            led.val_lbl = val_lbl

        layout.addWidget(quality_container)
        layout.addStretch()
        self.main_layout.addWidget(sidebar)

    # ── Content area ──────────────────────────────────────────────────
    def _init_content(self):
        content = QWidget()
        layout  = QVBoxLayout(content)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # ── Header row ────────────────────────────────────────────────
        header = QHBoxLayout()
        title  = QLabel("Phaseon")
        title.setStyleSheet(f"color: {text_dark_color}; font-size: 28px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.device_badge = QLabel(" ● Device Disconnected ")
        self.device_badge.setStyleSheet(
            f"background-color: #FEE2E2; color: {accent_red_color};"
            "border-radius: 15px; padding: 5px 15px; font-weight: bold;")
        header.addWidget(self.device_badge)
        header.addSpacing(10)

        self.arduino_badge = QLabel(" ● Arduino Disconnected ")
        self.arduino_badge.setStyleSheet(
            f"background-color: #FEE2E2; color: {accent_red_color};"
            "border-radius: 15px; padding: 5px 15px; font-weight: bold;")
        header.addWidget(self.arduino_badge)
        layout.addLayout(header)

        # ── Stat cards row ────────────────────────────────────────────
        stats = QHBoxLayout()
        stats.setSpacing(25)

        self.odometer  = MentalOdometer()
        self.card_state = StatCard("Dominant State", "-", "Waiting for data...", is_primary=True)

        # Session timer card
        self.record_card = QFrame()
        self.record_card.setFixedSize(220, 180)
        self.record_card.setStyleSheet(
            f"background-color: {text_dark_color}; border-radius: 15px;")
        rec = QVBoxLayout(self.record_card)
        rec.setContentsMargins(20, 15, 20, 15)

        rec_title = QLabel("Session Duration")
        rec_title.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")

        time_row = QHBoxLayout()
        self.lbl_start = QLabel("Start: --:--")
        self.lbl_end   = QLabel("End: --:--")
        for l in [self.lbl_start, self.lbl_end]:
            l.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        time_row.addWidget(self.lbl_start)
        time_row.addStretch()
        time_row.addWidget(self.lbl_end)

        self.btn_record = QPushButton("Start Recording")
        self.btn_record.setCheckable(True)
        self.btn_record.setStyleSheet(
            f"background-color: {primary_color}; color: white;"
            "border-radius: 8px; padding: 8px; font-weight: bold; margin-top: 5px;")
        self.btn_record.clicked.connect(self._toggle_record)

        rec.addWidget(rec_title)
        rec.addWidget(self.lbl_timer)
        rec.addLayout(time_row)
        rec.addStretch()
        rec.addWidget(self.btn_record)

        stats.addWidget(self.odometer)
        stats.addWidget(self.card_state)
        stats.addWidget(self.record_card)
        stats.addWidget(self._build_arm_card())
        stats.addStretch()
        layout.addLayout(stats)

        # ── Alpha / Beta wave graph ───────────────────────────────────
        wave_frame = QFrame()
        wave_frame.setFixedHeight(180)
        wave_frame.setStyleSheet(
            f"background-color: {white_color}; border-radius: 20px;")
        sh = QGraphicsDropShadowEffect()
        sh.setBlurRadius(20); sh.setColor(QColor(0,0,0,10)); sh.setOffset(0,5)
        wave_frame.setGraphicsEffect(sh)

        wl = QVBoxLayout(wave_frame)
        wl.setContentsMargins(20, 10, 20, 10)

        wave_hdr = QHBoxLayout()
        wave_hdr.addWidget(QLabel("Alpha & Beta Waves"))
        legend = QLabel(
            '<span style="color:#10B981;font-weight:bold;">■ Alpha — Relaxation</span>'
            '&nbsp;&nbsp;&nbsp;'
            '<span style="color:#EF4444;font-weight:bold;">■ Beta — Focus/Attention</span>')
        legend.setStyleSheet("font-size:11px; background:none; border:none;")
        wave_hdr.addStretch()
        wave_hdr.addWidget(legend)
        wl.addLayout(wave_hdr)

        self.wave_widget = pg.GraphicsLayoutWidget()
        self.wave_widget.setBackground('w')
        pw = self.wave_widget.addPlot()
        pw.showGrid(x=False, y=True, alpha=0.1)
        pw.getAxis('left').setPen('#DDD')
        pw.hideAxis('bottom')
        pw.setMouseEnabled(x=False, y=False)
        pw.setYRange(0, 100)
        self.curve_alpha = pw.plot(pen=pg.mkPen(color=alpha_color, width=2))
        self.curve_beta  = pw.plot(pen=pg.mkPen(color=beta_color,  width=2))
        wl.addWidget(self.wave_widget)
        layout.addWidget(wave_frame)

        # ── Raw EEG graph — 4 stacked subplots ───────────────────────
        eeg_frame = QFrame()
        eeg_frame.setStyleSheet(
            f"background-color: {white_color}; border-radius: 20px;")
        sh2 = QGraphicsDropShadowEffect()
        sh2.setBlurRadius(20); sh2.setColor(QColor(0,0,0,10)); sh2.setOffset(0,5)
        eeg_frame.setGraphicsEffect(sh2)

        el = QVBoxLayout(eeg_frame)
        el.setContentsMargins(20, 10, 20, 10)
        el.setSpacing(4)

        eeg_title = QLabel("Live Raw EEG")
        eeg_title.setStyleSheet(
            f"color: {text_dark_color}; font-size: 13px; font-weight: bold;"
            "border: none;")
        el.addWidget(eeg_title)

        self.graph_widget = pg.GraphicsLayoutWidget()
        self.graph_widget.setBackground('w')

        line_colors = ["#1F2937", "#059669", "#7C3AED", "#D97706"]
        axis_pen    = pg.mkPen(color="#DDDDDD", width=1)
        label_style = {'color': '#DDDDDD', 'font-size': '9pt', 'font-weight': 'bold'}

        self.plots  = []
        self.curves = []

        for i, ch_name in enumerate(self.channels):
            p = self.graph_widget.addPlot(row=i, col=0)
            p.showGrid(x=False, y=True, alpha=0.08)
            p.hideButtons()
            p.setMenuEnabled(False)
            p.setMouseEnabled(x=False, y=False)
            p.setLabel('left', ch_name, **label_style)
            p.getAxis('left').setPen(axis_pen)
            p.getAxis('left').setTextPen(axis_pen)
            p.hideAxis('bottom')
            p.setYRange(-200, 200)          # set individually for all 4
            p.setContentsMargins(0, 0, 0, 0)

            curve = p.plot(pen=pg.mkPen(color=line_colors[i], width=1.5))
            self.plots.append(p)
            self.curves.append(curve)

        el.addWidget(self.graph_widget)
        layout.addWidget(eeg_frame, stretch=1)
        self.main_layout.addWidget(content)

    def _build_arm_card(self):
        """Card showing current arm state as an image."""
        base = os.path.dirname(os.path.abspath(__file__))
        self._arm_images = {
            'O': QPixmap(os.path.join(base, "assets", "state-images" , "hand-open.png")),
            'N': QPixmap(os.path.join(base, "assets", "state-images" , "hand-neutral.png")),
            'C': QPixmap(os.path.join(base, "assets", "state-images" , "hand-close.png")),
        }

        card = QFrame()
        card.setFixedSize(220, 180)
        card.setStyleSheet(
            f"background-color: {white_color}; border-radius: 15px;")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        title = QLabel("Arm State")
        title.setStyleSheet(
            f"color: {text_light_color}; font-size: 13px; font-weight: 600;")
        layout.addWidget(title)

        self.arm_image_lbl = QLabel()
        self.arm_image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arm_image_lbl.setPixmap(
            self._arm_images['O'].scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.arm_image_lbl)

        self.arm_state_lbl = QLabel("Open")
        self.arm_state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arm_state_lbl.setStyleSheet(
            f"color: {primary_color}; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.arm_state_lbl)

        return card

    def update_arm_state(self, cmd):
        """Called by UIBridge with 'O', 'N', or 'C'."""
        labels = {'O': ('Open',    primary_color),
                  'N': ('Neutral', '#D97706'),
                  'C': ('Closed',  '#EF4444')}
        text, color = labels.get(cmd, ('Open', primary_color))
        self.arm_state_lbl.setText(text)
        self.arm_state_lbl.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: bold;")
        self.arm_image_lbl.setPixmap(
            self._arm_images[cmd].scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    # ── Placeholder toggle methods (overridden by UIBridge) ───────────
    def toggle_device(self):
        pass

    def toggle_arduino(self):
        pass

    # ── Recording ─────────────────────────────────────────────────────
    def _toggle_record(self):
        if self.btn_record.isChecked():
            self.btn_record.setText("Stop")
            self.btn_record.setStyleSheet(
                f"background-color: {accent_red_color}; color: white;"
                "border-radius: 8px; padding: 8px; font-weight: bold; margin-top: 5px;")
            self.recording_start = datetime.now()
            self.lbl_start.setText(f"Start: {self.recording_start.strftime('%H:%M:%S')}")
            self.lbl_end.setText("End: --:--")
        else:
            self.btn_record.setText("Start Recording")
            self.btn_record.setStyleSheet(
                f"background-color: {primary_color}; color: white;"
                "border-radius: 8px; padding: 8px; font-weight: bold; margin-top: 5px;")
            if self.recording_start:
                self.lbl_end.setText(
                    f"End: {datetime.now().strftime('%H:%M:%S')}")
                self.recording_start = None

    def _update_clock(self):
        if self.recording_start:
            elapsed = datetime.now() - self.recording_start
            s = int(elapsed.total_seconds())
            self.lbl_timer.setText(f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PhaseonDashboard()
    w.show()
    sys.exit(app.exec())