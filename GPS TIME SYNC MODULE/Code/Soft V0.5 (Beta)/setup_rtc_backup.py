# setup_rtc_backup.py - run ONCE from Thonny (Run current script), then you're done.
#
# The RV-3028 ships with its supercap trickle charger and backup switchover both
# switched OFF, so the supercap on the Makerverse board does nothing until this
# is stored in the chip's EEPROM. The setting survives power loss, so you only
# ever need to run this once per RTC board. It checks first and does nothing
# (no EEPROM write) if the chip is already set up.

from machine import I2C, Pin
from rv3028 import RV3028

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
rtc = RV3028(i2c)
rtc.begin()

print("Before:", rtc.describe_backup())

if rtc.enable_supercap_backup():
    rtc.reload_config_from_eeprom()      # re-read from EEPROM to prove it stuck
    print("After: ", rtc.describe_backup())
    if rtc.supercap_ready():
        print("Done - supercap will now charge whenever the board has power (a few minutes).")
    else:
        print("FAILED - setting did not stick. Check the 3V3 supply and try again.")
else:
    print("Already set up - nothing written.")
