import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread

from sensor_worker  import SensorWorker
from math_engine    import MathEngine
from arm_controller import ArmController
from ui_bridge      import UIBridge
from dashboard      import PhaseonDashboard


def main():
    pg.setConfigOptions(antialias=False, useOpenGL=False)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Create UI ─────────────────────────────────────────────────────
    dashboard = PhaseonDashboard()

    # ── Create backend objects ────────────────────────────────────────
    sensor_worker  = SensorWorker()
    math_engine    = MathEngine()
    arm_controller = ArmController()

    # ── Math engine runs in its own thread ────────────────────────────
    math_thread = QThread()
    math_engine.moveToThread(math_thread)
    math_thread.start()

    # SensorWorker → MathEngine (raw data pipe)
    sensor_worker.sig_packet.connect(math_engine.slot_packet)

    # Reset math state on reconnect — calibration restarts via contact detection
    sensor_worker.sig_connected.connect(
        lambda ok: math_engine.reset() if ok else None)

    # ── UIBridge wires all signals to dashboard ───────────────────────
    bridge = UIBridge(dashboard)
    bridge.wire(sensor_worker, math_engine, arm_controller)

    dashboard.show()
    ret = app.exec()

    # ── Clean shutdown ────────────────────────────────────────────────
    sensor_worker.stop_worker()
    arm_controller.disconnect()
    math_thread.quit()
    math_thread.wait(3000)
    sys.exit(ret)


if __name__ == "__main__":
    main()