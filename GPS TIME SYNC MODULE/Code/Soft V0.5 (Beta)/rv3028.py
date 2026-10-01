# rv3028.py - minimal MicroPython driver for the RV-3028-C7 RTC
# (Makerverse RTC with supercapacitor backup). Register map checked against
# the Micro Crystal RV-3028-C7 Application Manual, Rev 1.4.

import time

ADDR = 0x52

REG_TIME = 0x00        # seconds, minutes, hours, weekday, date, month, year (BCD)
REG_STATUS = 0x0E
REG_CTRL1 = 0x0F
REG_CTRL2 = 0x10
REG_EE_CMD = 0x27
REG_EE_BACKUP = 0x37   # config register: TCE (trickle charger) + BSM (backup switchover)

ST_EEBUSY = 0x80
ST_BSF = 0x20          # backup switchover has happened
ST_PORF = 0x01         # power-on-reset flag: time is NOT valid while set

CTRL1_EERD = 0x08      # pause the automatic EEPROM -> RAM refresh
CTRL2_12_24 = 0x02     # 1 = 12-hour mode (we force 0 = 24-hour)

BK_TCE = 0x20          # trickle charger enable
BK_BSM = 0x0C          # backup switchover mode field (bits 3:2)
BK_BSM_LEVEL = 0x0C    # 0b11 = level switching mode

BSM_NAMES = ("off", "direct", "off", "level")


def _bcd2dec(b):
    return (b >> 4) * 10 + (b & 0x0F)


def _dec2bcd(d):
    return ((d // 10) << 4) | (d % 10)


def weekday(y, m, d):
    """0 = Monday ... 6 = Sunday (Sakamoto's method)."""
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    sunday_zero = (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7
    return (sunday_zero + 6) % 7


class RV3028:
    def __init__(self, i2c, addr=ADDR):
        self.i2c = i2c
        self.addr = addr

    # ---- low level -------------------------------------------------------
    def _rd(self, reg, n=1):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def _wr(self, reg, data):
        self.i2c.writeto_mem(self.addr, reg, data)

    def _set_bits(self, reg, mask):
        self._wr(reg, bytes([self._rd(reg)[0] | mask]))

    def _clear_bits(self, reg, mask):
        self._wr(reg, bytes([self._rd(reg)[0] & ~mask]))

    def _wait_eeprom(self, timeout_ms=500):
        start = time.ticks_ms()
        while self._rd(REG_STATUS)[0] & ST_EEBUSY:
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("RV-3028 EEPROM busy timeout")
            time.sleep_ms(5)

    # ---- start-up --------------------------------------------------------
    def begin(self):
        if self.addr not in self.i2c.scan():
            raise OSError("RV-3028 not found at 0x%02X - check SDA=GP4, SCL=GP5, 3V3, GND"
                          % self.addr)
        self._wait_eeprom()                     # first ~66 ms after power-up
        self._clear_bits(REG_CTRL2, CTRL2_12_24)  # force 24-hour mode (power-on default)

    # ---- time ------------------------------------------------------------
    def read_time(self):
        """Returns (year, month, day, hour, minute, second).

        Seconds..year are read in ONE burst; the chip freezes its counters
        during the access, so the result is always coherent."""
        d = self._rd(REG_TIME, 7)
        return (2000 + _bcd2dec(d[6]),
                _bcd2dec(d[5] & 0x1F),
                _bcd2dec(d[4] & 0x3F),
                _bcd2dec(d[2] & 0x3F),
                _bcd2dec(d[1] & 0x7F),
                _bcd2dec(d[0] & 0x7F))

    def write_time(self, t):
        """t = (year, month, day, hour, minute, second), UTC.

        Written in ONE burst. Writing the seconds register also restarts the
        chip's sub-second divider, so the new second starts right now."""
        y, mo, d, h, mi, s = t
        self._wr(REG_TIME, bytes([_dec2bcd(s), _dec2bcd(mi), _dec2bcd(h),
                                  weekday(y, mo, d), _dec2bcd(d), _dec2bcd(mo),
                                  _dec2bcd(y - 2000)]))

    # ---- status flags ----------------------------------------------------
    def power_lost(self):
        """True if the chip lost ALL power since the flag was last cleared."""
        return bool(self._rd(REG_STATUS)[0] & ST_PORF)

    def clear_power_lost(self):
        self._clear_bits(REG_STATUS, ST_PORF)

    def ran_on_backup(self):
        """True if the chip switched to the supercap at some point."""
        return bool(self._rd(REG_STATUS)[0] & ST_BSF)

    def clear_ran_on_backup(self):
        self._clear_bits(REG_STATUS, ST_BSF)

    # ---- supercap backup configuration (lives in EEPROM) -----------------
    def backup_config(self):
        r = self._rd(REG_EE_BACKUP)[0]
        return bool(r & BK_TCE), (r & BK_BSM) >> 2

    def supercap_ready(self):
        tce, bsm = self.backup_config()
        return tce and bsm in (1, 3)

    def describe_backup(self):
        tce, bsm = self.backup_config()
        return "trickle charger %s, backup switchover %s" % (
            "ON" if tce else "OFF", BSM_NAMES[bsm])

    def _eeprom_command(self, cmd, ram_edit=None):
        """0x11 = UPDATE (config RAM -> EEPROM), 0x12 = REFRESH (EEPROM -> config RAM).

        Follows the datasheet procedure: pause auto-refresh, (edit RAM), send
        0x00 then the command, wait for EEbusy to clear, re-enable auto-refresh."""
        self._wait_eeprom()
        self._set_bits(REG_CTRL1, CTRL1_EERD)
        try:
            if ram_edit is not None:
                self._wr(ram_edit[0], bytes([ram_edit[1]]))
            self._wr(REG_EE_CMD, b"\x00")
            self._wr(REG_EE_CMD, bytes([cmd]))
            time.sleep_ms(5)
            self._wait_eeprom()                 # an UPDATE takes about 63 ms
        finally:
            self._clear_bits(REG_CTRL1, CTRL1_EERD)

    def enable_supercap_backup(self):
        """ONE-TIME EEPROM write: trickle charger on (3 kohm), level-switching
        backup. Skipped (returns False) if it is already set."""
        cur = self._rd(REG_EE_BACKUP)[0]
        new = (cur & ~BK_BSM) | BK_TCE | BK_BSM_LEVEL
        if new == cur:
            return False
        self._eeprom_command(0x11, (REG_EE_BACKUP, new))
        return True

    def reload_config_from_eeprom(self):
        """Re-read the config registers from EEPROM - proves a write stuck."""
        self._eeprom_command(0x12)
