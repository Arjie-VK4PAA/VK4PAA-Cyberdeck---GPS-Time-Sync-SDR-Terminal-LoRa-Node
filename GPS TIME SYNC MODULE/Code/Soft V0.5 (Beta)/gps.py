# gps.py - NMEA reader for the u-blox NEO-6M (UART0: GP0 = Pico TX, GP1 = Pico RX)

import time
from machine import UART, Pin

# NMEA sentence ids used by the u-blox CFG-MSG command (message class 0xF0)
NMEA_IDS = {"GGA": 0x00, "GLL": 0x01, "GSA": 0x02, "GSV": 0x03, "RMC": 0x04, "VTG": 0x05}


class GPS:
    def __init__(self, uart_id=0, tx=0, rx=1, baud=9600):
        self.uart = UART(uart_id, baudrate=baud, tx=Pin(tx), rx=Pin(rx), rxbuf=1024)
        self._buf = b""
        # live state, read by main.py
        self.fix = False            # True while the latest RMC says status 'A'
        self.utc = None             # (y, mo, d, h, mi, s) from the latest valid RMC
        self.sats = None            # satellites used (from GGA), None until seen
        self.bytes_rx = 0
        self.last_rx_ms = None      # ticks_ms of the last received byte
        self.good = 0               # sentences with a good checksum
        self.bad = 0                # sentences with a bad checksum

    # ---- optional: cut the NEO-6M down to the sentences we use ------------
    def _ubx(self, cls, mid, payload):
        msg = bytes([cls, mid, len(payload) & 0xFF, len(payload) >> 8]) + payload
        a = b = 0
        for c in msg:                       # UBX Fletcher checksum
            a = (a + c) & 0xFF
            b = (b + a) & 0xFF
        self.uart.write(b"\xb5\x62" + msg + bytes([a, b]))

    def keep_only(self, keep=("GGA", "RMC")):
        """Ask the module to stop sending the sentences we don't use.

        With the default sentence set at 9600 baud the RMC line finishes
        ~0.4 s after the top of the second; with just GGA + RMC it is ~0.15 s.
        Not saved to the module - it is simply re-sent on every boot."""
        for name in NMEA_IDS:
            rate = 1 if name in keep else 0
            self._ubx(0x06, 0x01, bytes([0xF0, NMEA_IDS[name], rate]))
            time.sleep_ms(60)

    # ---- parsing ----------------------------------------------------------
    def poll(self):
        """Call often. Returns the (y, mo, d, h, mi, s) UTC tuple from a new
        valid RMC sentence if one arrived, otherwise None."""
        n = self.uart.any()
        if not n:
            return None
        data = self.uart.read(n)
        if not data:
            return None
        self.bytes_rx += len(data)
        self.last_rx_ms = time.ticks_ms()
        self._buf += data
        if len(self._buf) > 512 and b"\n" not in self._buf:
            self._buf = b""                 # junk with no line ends - start over
            return None
        if b"\n" not in self._buf:
            return None

        lines = self._buf.split(b"\n")
        self._buf = lines.pop()             # keep the unfinished last line
        result = None
        for line in lines:
            utc = self._handle(line)
            if utc is not None:
                result = utc
        return result

    def _handle(self, line):
        i = line.rfind(b"$")                # skips any binary UBX ACK bytes in front
        star = line.rfind(b"*")
        if i < 0 or star < i + 6:
            return None
        body = line[i + 1:star]
        cs = 0
        for c in body:
            cs ^= c
        try:
            want = int(line[star + 1:star + 3].decode(), 16)
            fields = body.decode().split(",")
        except (ValueError, UnicodeError):
            self.bad += 1
            return None
        if cs != want:
            self.bad += 1
            return None
        self.good += 1

        kind = fields[0][2:]                # GPRMC / GNRMC -> RMC
        try:
            if kind == "RMC" and len(fields) > 9:
                return self._rmc(fields)
            if kind == "GGA" and len(fields) > 7:
                self.sats = int(fields[7]) if fields[7] else 0
        except ValueError:
            pass
        return None

    def _rmc(self, f):
        if f[2] != "A" or len(f[1]) < 6 or len(f[9]) != 6:
            self.fix = False                # 'V' = receiver warning / no fix
            return None
        t, d = f[1], f[9]
        utc = (2000 + int(d[4:6]), int(d[2:4]), int(d[0:2]),
               int(t[0:2]), int(t[2:4]), int(t[4:6]))
        y, mo, dd, h, mi, s = utc
        if not (2020 <= y <= 2099 and 1 <= mo <= 12 and 1 <= dd <= 31
                and h < 24 and mi < 60 and s < 60):   # s == 60 (leap second) skipped
            return None
        self.fix = True
        self.utc = utc
        return utc
