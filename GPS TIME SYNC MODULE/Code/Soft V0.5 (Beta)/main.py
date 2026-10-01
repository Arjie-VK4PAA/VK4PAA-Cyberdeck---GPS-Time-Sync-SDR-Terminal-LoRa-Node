# main.py - GPS-disciplined shack clock, stage 1 (no display yet)
#
# NEO-6M GPS  -> UART0  (GP0 = Pico TX, GP1 = Pico RX)
# RV-3028 RTC -> I2C0   (GP4 = SDA, GP5 = SCL)
#
# Prints the RTC time (UTC) once a second to the MicroPython REPL / Thonny shell.
# The RTC is set from GPS on the first fix, then re-aligned if it drifts by more
# than a second or every RESYNC_EVERY_S seconds.
#
# Accuracy note: the NEO-6M breakout has no PPS pin, so sync comes from the NMEA
# text. Expect the RTC to sit roughly 0.1-0.2 s behind true UTC (the time it takes
# the GPS to send the sentence). Fine for a clock face; not sub-second.

import time
from machine import I2C, Pin
from rv3028 import RV3028
from gps import GPS

# ---- settings ---------------------------------------------------------------
GPS_BAUD = 9600           # NEO-6M factory default
TRIM_NMEA = True          # tell the GPS to send only GGA + RMC (steadier timing)
RESYNC_EVERY_S = 3600     # periodic re-alignment while the GPS has a fix
# -----------------------------------------------------------------------------


def epoch_s(t):
    """(y, mo, d, h, mi, s) -> seconds since 1970 (pure arithmetic, UTC)."""
    y, m, d, hh, mm, ss = t
    if m <= 2:
        y -= 1
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return (era * 146097 + doe - 719468) * 86400 + hh * 3600 + mm * 60 + ss


def fmt(t):
    return "%04d-%02d-%02d %02d:%02d:%02d UTC" % t


def ago(s):
    if s < 120:
        return "%d s" % s
    if s < 7200:
        return "%d min" % (s // 60)
    return "%d h %02d min" % (s // 3600, (s // 60) % 60)


def read_rtc(rtc):
    """RTC time tuple, or None if the I2C read failed / looks like garbage."""
    try:
        t = rtc.read_time()
    except OSError:
        return None
    if 1 <= t[1] <= 12 and 1 <= t[2] <= 31 and t[3] < 24 and t[4] < 60 and t[5] < 60:
        return t
    return None


def main():
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
    rtc = RV3028(i2c)
    rtc.begin()                                   # raises with a wiring hint if absent

    gps = GPS(0, tx=0, rx=1, baud=GPS_BAUD)
    if TRIM_NMEA:
        # the module ignores commands until it has booted - wait for its first bytes
        t0 = time.ticks_ms()
        while not gps.uart.any() and time.ticks_diff(time.ticks_ms(), t0) < 2000:
            time.sleep_ms(50)
        gps.keep_only()

    # ---- start-up report ----------------------------------------------------
    rtc_valid = not rtc.power_lost()
    print()
    print("=== GPS clock - stage 1 (GPS + RTC) ===")
    print("RV-3028 found at 0x52")
    if rtc_valid:
        t = read_rtc(rtc)
        print("RTC time at boot:", fmt(t) if t else "unreadable")
    else:
        print("RTC lost all power - its time is invalid until the first GPS fix")
    if rtc.ran_on_backup():
        print("RTC rode through a power loss on the supercap")
        rtc.clear_ran_on_backup()
    print("RTC backup:", rtc.describe_backup())
    if not rtc.supercap_ready():
        print("  ! supercap is not in use - run setup_rtc_backup.py once")
    print("Waiting for GPS (a cold start needs a clear view of the sky)...")
    print()

    last_sync_ms = None
    last_sec = -1
    had_fix = False
    next_read = time.ticks_ms()

    while True:
        fix = gps.poll()
        now = time.ticks_ms()

        # ---- GPS gave us a new valid time: decide whether to set the RTC ------
        if fix is not None:
            try:
                before = read_rtc(rtc)
                diff = (epoch_s(fix) - epoch_s(before)) if before else None
                first = last_sync_ms is None
                hourly = (not first and
                          time.ticks_diff(now, last_sync_ms) >= RESYNC_EVERY_S * 1000)
                # +/- 1 s is normal (sentence timing), so only act on > 1 s
                if first or hourly or diff is None or abs(diff) > 1:
                    was_valid = rtc_valid
                    rtc.write_time(fix)
                    rtc.clear_power_lost()
                    rtc_valid = True
                    last_sync_ms = now
                    if was_valid and diff is not None:
                        print("[sync] RTC set from GPS (it was %+d s from GPS)" % diff)
                    else:
                        print("[sync] RTC set from GPS")
                    next_read = now
            except OSError:
                print("[sync] RTC write failed - check I2C wiring")

        if gps.fix != had_fix:
            print("[gps] fix acquired" if gps.fix else "[gps] fix lost - RTC keeps time")
            had_fix = gps.fix

        # ---- print once per RTC second ---------------------------------------
        if time.ticks_diff(now, next_read) >= 0:
            t = read_rtc(rtc)
            if t is None:
                print("RTC read error - check I2C wiring")
                next_read = time.ticks_add(now, 1000)
            elif t[5] != last_sec:
                last_sec = t[5]
                next_read = time.ticks_add(now, 900)    # next change is ~1 s away

                if gps.last_rx_ms is None or time.ticks_diff(now, gps.last_rx_ms) > 3000:
                    g = "GPS: NO DATA (check wiring)"
                elif gps.fix:
                    g = "GPS fix" + (", %d sats" % gps.sats if gps.sats is not None else "")
                else:
                    g = "GPS searching"
                if last_sync_ms is None:
                    s = "not synced yet"
                else:
                    s = "synced %s ago" % ago(time.ticks_diff(now, last_sync_ms) // 1000)
                print("%s%s | %s | %s" % (fmt(t), "" if rtc_valid else " [RTC not set]", g, s))
            else:
                next_read = time.ticks_add(now, 20)

        time.sleep_ms(10)


if __name__ == "__main__":
    main()
