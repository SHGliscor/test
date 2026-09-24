#!/usr/bin/env python3
"""
Capture / Pokédex RAM probe for PokebotSwitch-FRLG.

Purpose
-------
Drive the Switch from your PC (Koi botbase) while watching live RAM, so you can
walk through: encounter → bag → throw → Gotcha → Dex registration → nickname
and mark which RAM values change on each screen.

This is how we find a reliable "Dex screen is open" offset later.

Usage
-----
  cd C:\\Users\\roger\\Desktop\\pokebot-frlg
  python capture_probe.py

  Or: python capture_probe.py 192.168.1.162 6000

Requires: same folder layout as the bot (pokebot_frlg/), PySide6, Koi Wi‑Fi mode.
Disconnect the physical controller first (same as the main bot).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from pokebot-frlg root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from pokebot_frlg.wifi_botbase import WiFiBotbase, WiFiBotbaseError
from pokebot_frlg.offsets import (
    IN_BATTLE,
    BATTLE_MENU,
    INITIAL_SEED,
    LARGE_SHIFT,
    lookup,
    FRLG_GAME_VERSION,
)


def _hex_u8(v: int) -> str:
    return f"0x{v:02X} ({v})"


def _hex_u32(v: int) -> str:
    return f"0x{v:08X}"


class CaptureProbe(QMainWindow):
    def __init__(self, host: str = "192.168.1.162", port: int = 6000):
        super().__init__()
        self.setWindowTitle("FRLG Capture / Dex RAM Probe")
        self.resize(780, 640)

        self.bot: WiFiBotbase | None = None
        self.off = None
        self._last = {}
        self._poll_ms = 120

        w = QWidget()
        self.setCentralWidget(w)
        root = QVBoxLayout(w)

        # --- connect row ---
        row = QHBoxLayout()
        row.addWidget(QLabel("Switch IP"))
        self.ip = QLineEdit(host)
        self.ip.setFixedWidth(140)
        row.addWidget(self.ip)
        row.addWidget(QLabel("Port"))
        self.port = QLineEdit(str(port))
        self.port.setFixedWidth(70)
        row.addWidget(self.port)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_switch)
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.disconnect_switch)
        self.btn_disconnect.setEnabled(False)
        row.addWidget(self.btn_connect)
        row.addWidget(self.btn_disconnect)
        row.addStretch(1)
        root.addLayout(row)

        self.status = QLabel("Not connected — physical controller should be released (Koi only).")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        # --- live RAM ---
        root.addWidget(QLabel("Live RAM (poll ~8 Hz)"))
        self.ram = QLabel("—")
        self.ram.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ram.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        root.addWidget(self.ram)

        # --- buttons ---
        root.addWidget(QLabel("Send input to Switch"))
        grid = QGridLayout()
        buttons = [
            (0, 1, "X"),
            (1, 0, "Y"),
            (1, 1, "B"),
            (1, 2, "A"),
            (2, 1, "DUP"),
            (3, 0, "DLEFT"),
            (3, 1, "DDOWN"),
            (3, 2, "DRIGHT"),
            (4, 0, "PLUS"),
            (4, 1, "MINUS"),
            (4, 2, "HOME"),
        ]
        for r, c, name in buttons:
            b = QPushButton(name)
            b.setFixedSize(72, 36)
            b.clicked.connect(lambda _=False, n=name: self.send_click(n))
            grid.addWidget(b, r, c)
        root.addLayout(grid)

        hold_row = QHBoxLayout()
        for name in ("A", "B"):
            b = QPushButton(f"HOLD {name} 0.25s")
            b.clicked.connect(lambda _=False, n=name: self.send_hold(n, 0.25))
            hold_row.addWidget(b)
        for name in ("A", "B"):
            b = QPushButton(f"HOLD {name} 0.50s")
            b.clicked.connect(lambda _=False, n=name: self.send_hold(n, 0.50))
            hold_row.addWidget(b)
        hold_row.addStretch(1)
        root.addLayout(hold_row)

        # --- markers ---
        root.addWidget(QLabel("Mark current screen (writes a snapshot into the log)"))
        mark_row = QHBoxLayout()
        for label in (
            "OVERWORLD",
            "BATTLE_MENU",
            "BAG",
            "THROW_ANIM",
            "GOTCHA",
            "DEX_DATA_ADDED",
            "DEX_ENTRY",
            "NICKNAME",
            "PARTY_AFTER",
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, n=label: self.mark(n))
            mark_row.addWidget(b)
        root.addLayout(mark_row)

        # --- log ---
        root.addWidget(QLabel("Change log + markers (copy this out when done)"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        root.addWidget(self.log, stretch=1)

        btn_clear = QPushButton("Clear log")
        btn_clear.clicked.connect(self.log.clear)
        root.addWidget(btn_clear)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_ram)

    def append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def connect_switch(self):
        self.disconnect_switch()
        host = self.ip.text().strip()
        try:
            port = int(self.port.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Port", "Port must be a number")
            return
        try:
            bot = WiFiBotbase(host, port)
            ident = bot.connect()
            title, _ = bot.get_title_id()
            off = lookup(title)
            if off is None:
                bot.close()
                raise RuntimeError(f"Unsupported title id {title}")
            version, _ = bot.get_textish("game version")
            if version != FRLG_GAME_VERSION:
                bot.close()
                raise RuntimeError(f"Unexpected game version {version}")
            bot.initialize_controller()
            self.bot = bot
            self.off = off
            self._last = {}
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.status.setText(
                f"Connected {host}:{port} | {off.language} {off.game} | title {title} | connect {ident.connect_ms:.0f} ms"
            )
            self.append(f"CONNECTED {off.language} {off.game}")
            self.timer.start(self._poll_ms)
            self.poll_ram()
        except Exception as exc:
            QMessageBox.critical(self, "Connect failed", str(exc))
            self.append(f"CONNECT FAIL: {exc}")

    def disconnect_switch(self):
        self.timer.stop()
        if self.bot:
            try:
                self.bot.set_stick("LEFT", 0, 0)
                self.bot.set_stick("RIGHT", 0, 0)
                self.bot.detach_controller()
            except Exception:
                pass
            try:
                self.bot.close()
            except Exception:
                pass
        self.bot = None
        self.off = None
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.status.setText("Disconnected")

    def send_click(self, name: str):
        if not self.bot:
            return
        try:
            self.bot.click(name)
            self.append(f"INPUT click {name}")
        except WiFiBotbaseError as exc:
            self.append(f"INPUT ERROR: {exc}")

    def send_hold(self, name: str, hold: float):
        if not self.bot:
            return
        try:
            self.bot.press(name)
            time.sleep(hold)
            self.bot.release(name)
            self.append(f"INPUT press {name} hold={hold:.2f}s")
        except WiFiBotbaseError as exc:
            self.append(f"INPUT ERROR: {exc}")

    def read_snapshot(self) -> dict:
        assert self.bot and self.off
        in_b = self.bot.read_heap(IN_BATTLE, 1)[0]
        menu = self.bot.read_heap(BATTLE_MENU, 1)[0]
        over = self.bot.read_heap(self.off.overworld, 1)[0]
        seed = int.from_bytes(self.bot.read_heap(self.off.current_seed, 4), "little")
        # Extra peeks near battle/overworld — useful when comparing screens
        extras = {}
        for label, addr, n in (
            ("battle_menu+0", BATTLE_MENU, 1),
            ("in_battle+0", IN_BATTLE, 1),
            ("overworld+0", self.off.overworld, 1),
            ("overworld+1", self.off.overworld + 1, 1),
            ("overworld-1", self.off.overworld - 1, 1),
            ("seed", self.off.current_seed, 4),
        ):
            raw = self.bot.read_heap(addr, n)
            if n == 1:
                extras[label] = raw[0]
            else:
                extras[label] = int.from_bytes(raw, "little")
        return {
            "in_battle": in_b,
            "battle_menu": menu,
            "overworld": over,
            "seed": seed,
            "extras": extras,
        }

    def poll_ram(self):
        if not self.bot or not self.off:
            return
        try:
            snap = self.read_snapshot()
        except Exception as exc:
            self.ram.setText(f"Read error: {exc}")
            return

        text = (
            f"IN_BATTLE   { _hex_u8(snap['in_battle']) }\n"
            f"BATTLE_MENU { _hex_u8(snap['battle_menu']) }\n"
            f"OVERWORLD   { _hex_u8(snap['overworld']) }\n"
            f"SEED        { _hex_u32(snap['seed']) }"
        )
        self.ram.setText(text)

        # Log changes
        for key in ("in_battle", "battle_menu", "overworld"):
            prev = self._last.get(key)
            cur = snap[key]
            if prev is not None and prev != cur:
                self.append(f"CHANGE {key}: {prev} -> {cur}")
        self._last = {k: snap[k] for k in ("in_battle", "battle_menu", "overworld", "seed")}

    def mark(self, name: str):
        if not self.bot:
            self.append(f"MARK {name} (not connected)")
            return
        try:
            snap = self.read_snapshot()
            self.append(
                f"MARK {name} | in_battle={snap['in_battle']} "
                f"battle_menu={snap['battle_menu']} overworld={snap['overworld']} "
                f"seed={snap['seed']:08X} extras={snap['extras']}"
            )
        except Exception as exc:
            self.append(f"MARK {name} FAIL: {exc}")

    def closeEvent(self, event):
        self.disconnect_switch()
        event.accept()


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.162"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    app = QApplication(sys.argv)
    win = CaptureProbe(host, port)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
