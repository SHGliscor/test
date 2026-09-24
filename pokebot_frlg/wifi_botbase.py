from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Optional


DEFAULT_PORT = 6000
MAX_MEMORY_READ = 468


class WiFiBotbaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class WiFiIdentity:
    host: str
    port: int
    connect_ms: float


class WiFiBotbase:
    """Wi-Fi transport for Koi sys/usb-botbase socket mode.

    RAM writes/freezes are intentionally not exposed. Controller commands are
    allowed because the bot needs them for automation.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT, timeout_s: float = 5.0):
        self.host = host.strip()
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self.sock: Optional[socket.socket] = None
        self._rx = bytearray()
        self.command_log = []

    def connect(self) -> WiFiIdentity:
        if not self.host:
            raise WiFiBotbaseError("Switch IP/hostname is empty")
        self.close()
        started = time.perf_counter()
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
            self.sock.settimeout(self.timeout_s)
        except OSError as exc:
            self.sock = None
            raise WiFiBotbaseError(
                f"Could not connect to {self.host}:{self.port}: {exc}. "
                "Check the Switch IP, botbase Wi-Fi mode, port 6000, and LAN connection."
            ) from exc
        return WiFiIdentity(self.host, self.port, (time.perf_counter() - started) * 1000.0)

    def close(self):
        sock, self.sock = self.sock, None
        self._rx.clear()
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _ensure(self) -> socket.socket:
        if self.sock is None:
            raise WiFiBotbaseError("Not connected")
        return self.sock

    def send(self, command: str):
        if "\n" in command or "\r" in command:
            raise ValueError("command must not contain CR/LF")
        self.command_log.append({"t": round(time.time(), 3), "command": command})
        try:
            self._ensure().sendall(command.encode("ascii") + b"\r\n")
        except OSError as exc:
            raise WiFiBotbaseError(f"Socket send failed for {command!r}: {exc}") from exc

    def _readline(self, max_bytes: int = 4 * 1024 * 1024) -> bytes:
        sock = self._ensure()
        while True:
            pos = self._rx.find(b"\n")
            if pos >= 0:
                line = bytes(self._rx[:pos])
                del self._rx[: pos + 1]
                return line.rstrip(b"\r")
            if len(self._rx) > max_bytes:
                raise WiFiBotbaseError(f"Response exceeded {max_bytes} bytes without a newline")
            try:
                chunk = sock.recv(4096)
            except socket.timeout as exc:
                raise WiFiBotbaseError("Timed out waiting for botbase response") from exc
            except OSError as exc:
                raise WiFiBotbaseError(f"Socket receive failed: {exc}") from exc
            if not chunk:
                raise WiFiBotbaseError("Switch closed the botbase socket")
            self._rx.extend(chunk)

    def query_line(self, command: str, *, max_bytes: int = 4 * 1024 * 1024) -> bytes:
        self.send(command)
        return self._readline(max_bytes=max_bytes)

    @staticmethod
    def _decode_text(payload: bytes) -> str:
        return payload.decode("ascii", errors="replace").strip()

    def read_heap(self, offset: int, length: int) -> bytes:
        if offset < 0 or offset > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("heap offset is outside u64 range")
        if length < 0:
            raise ValueError("length must be non-negative")
        out = bytearray()
        done = 0
        while done < length:
            count = min(MAX_MEMORY_READ, length - done)
            raw_line = self.query_line(f"peek 0x{offset + done:X} {count}", max_bytes=max(4096, count * 2 + 128))
            text = self._decode_text(raw_line).replace(" ", "")
            if len(text) != count * 2:
                raise WiFiBotbaseError(
                    f"Unexpected heap-read response at 0x{offset + done:X}: "
                    f"expected {count * 2} hex chars, got {len(text)} ({text[:160]!r})"
                )
            try:
                out.extend(bytes.fromhex(text))
            except ValueError as exc:
                raise WiFiBotbaseError(f"Non-hex heap-read response: {text[:160]!r}") from exc
            done += count
            if done < length:
                time.sleep(0.002)
        return bytes(out)

    def get_title_id(self) -> tuple[str, bytes]:
        raw = self.query_line("getTitleID", max_bytes=128)
        text = self._decode_text(raw).replace("0x", "").replace("0X", "").upper()
        return text, raw

    def get_u64_hex(self, command: str) -> tuple[Optional[int], bytes]:
        raw = self.query_line(command, max_bytes=128)
        text = self._decode_text(raw).replace("0x", "").replace("0X", "")
        try:
            return (int(text, 16), raw) if text else (None, raw)
        except ValueError:
            return None, raw

    def get_textish(self, command: str) -> tuple[str, bytes]:
        raw = self.query_line(command, max_bytes=4096)
        return self._decode_text(raw), raw

    # Controller commands do not return a line in Wi-Fi mode.
    def click(self, button: str):
        self.send(f"click {button}")

    def press(self, button: str):
        self.send(f"press {button}")

    def release(self, button: str):
        self.send(f"release {button}")

    def detach_controller(self):
        self.send("detachController")

    # Koi botbase screen-control commands are send-only in Wi-Fi mode.
    def screen_off(self):
        self.send("screenOff")

    def screen_on(self):
        self.send("screenOn")

    def set_stick(self, side: str, x: int, y: int):
        side = side.upper()
        if side not in ("LEFT", "RIGHT"):
            raise ValueError("stick side must be LEFT or RIGHT")
        self.send(f"setStick {side} {int(x)} {int(y)}")

    def click_sequence(self, sequence: str):
        """Run a Koi clickSeq atomically inside the Switch sysmodule.

        This is important for Gen3-style Spin: the directional input must
        exist for roughly one game frame. Sending separate setStick commands
        exposes each command to botbase's normal scheduling delay and can turn
        a one-frame turn into a real movement.
        """
        if not sequence or any(ch in sequence for ch in "\r\n "):
            raise ValueError("click sequence must be non-empty and contain no spaces/CR/LF")
        self.send(f"clickSeq {sequence}")

    def initialize_controller(self, settle_s: float = 0.75):
        # Match the public SysBot FRLG startup flow: detach any stale HDLS
        # virtual controller, then create a clean neutral controller state.
        self.detach_controller()
        time.sleep(settle_s)
        self.set_stick("LEFT", 0, 0)
        self.set_stick("RIGHT", 0, 0)
        time.sleep(0.25)

    def soft_reset_frlg(self, hold_s: float = 0.50, settle_s: float = 0.50):
        # Proven Switch FRLG combo used by the public SysBot.NET FRLG implementation.
        for b in ("A", "B", "X", "Y"):
            self.press(b)
        time.sleep(hold_s)
        for b in ("A", "B", "X", "Y"):
            self.release(b)
        time.sleep(settle_s)
