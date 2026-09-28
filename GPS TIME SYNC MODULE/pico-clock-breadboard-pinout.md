# GPS Clock — Breadboard Pinout

DEV NOTE: This Pinout was made by Claude

Pico pin names below are GPIO labels (e.g. `GP4`), not physical pin numbers, as requested.

| Component | Pin on component | Pin name on the Pico | Notes |
|---|---|---|---|
| GPS (u-blox NEO-6M) | TX | GP1 (UART0 RX) | GPS transmits NMEA sentences; Pico receives them. TX/RX cross over, as with any UART link. |
| GPS (u-blox NEO-6M) | RX | GP0 (UART0 TX) | Pico can send configuration commands to the GPS module. Rarely used once the module is configured. |
| GPS (u-blox NEO-6M) | VCC | 3V3(OUT) | Powered from the Pico's 3.3V rail. |
| GPS (u-blox NEO-6M) | GND | GND | Common ground. |
| RTC (Makerverse RV-3028) | SDA | GP4 (I2C0 SDA) | Shared I2C0 bus — see explanation below. |
| RTC (Makerverse RV-3028) | SCL | GP5 (I2C0 SCL) | Shared I2C0 bus — see explanation below. |
| RTC (Makerverse RV-3028) | VCC | 3V3(OUT) | Powered from the Pico's 3.3V rail. |
| RTC (Makerverse RV-3028) | GND | GND | Common ground. |
| RTC (Makerverse RV-3028) | INT | *not connected* | Alarm/periodic interrupt output. Not needed for basic timekeeping — left unconnected. |
| RTC (Makerverse RV-3028) | CLK | *not connected* | Configurable clock output. Not GPS-disciplined, so no use here — left unconnected. |
| RTC (Makerverse RV-3028) | EVI | *not connected* | External event-timestamp input. No use case in this build — left unconnected. |
| OLED (SSD1306) | SDA | GP4 (I2C0 SDA) | Shared I2C0 bus — see explanation below. |
| OLED (SSD1306) | SCL | GP5 (I2C0 SCL) | Shared I2C0 bus — see explanation below. |
| OLED (SSD1306) | VCC | 3V3(OUT) | Powered from the Pico's 3.3V rail. |
| OLED (SSD1306) | GND | GND | Common ground. |
| Button 1 | leg A | GP14 | Internal pull-up enabled in firmware; pin reads LOW when pressed. |
| Button 1 | leg B | GND | Completes the circuit on press. |
| Button 2 | leg A | GP15 | Internal pull-up enabled in firmware. |
| Button 2 | leg B | GND | Completes the circuit on press. |
| Button 3 | leg A | GP16 | Internal pull-up enabled in firmware. |
| Button 3 | leg B | GND | Completes the circuit on press. |
| 3.3V regulator | VOUT | VSYS | Feeds the Pico's power input — see power note below. |
| 3.3V regulator | GND | GND | Common ground. |

## Why the RTC and OLED share GP4/GP5

I2C is a **multi-drop bus**, not a point-to-point link like UART. Every device on the bus listens on the same two wires (SDA for data, SCL for the clock signal) and only responds when the Pico addresses its specific 7-bit device address — the RTC and OLED ship with different factory addresses (RV-3028 is commonly `0x52`, SSD1306 is commonly `0x3C` or `0x3D`), so they can't collide even though they're wired to the identical two GPIO pins. This is the whole point of I2C: it trades a dedicated pair of wires per device (like SPI or UART would need) for one shared pair plus an addressing scheme, which is why it only costs you 2 GPIOs total no matter how many I2C peripherals you add later.

UART, by contrast, is point-to-point — that's why the GPS gets its own dedicated GP0/GP1 pair rather than sharing with anything.

## Why the buttons don't share pins

Each button needs its own GPIO because a digital input pin can only read one binary state at a time — if two buttons shared a pin, the Pico couldn't tell which one was pressed (or that both were, or neither). Buttons are cheap on GPIO count here (3 pins) since the Pico has plenty spare, so there's no incentive to get clever with pin-sharing tricks (like a resistor ladder into one analog pin) for a 3-button interface.

## Why some RTC pins are left unconnected

The RV-3028 only *needs* VCC/GND/SDA/SCL to function as a readable/writable time source over I2C — that's the whole interface this build actually uses. INT, CLK, and EVI are bonus features (interrupt-driven alarms, a free-running clock output, and an external event logger) that solve problems this project doesn't have. Wiring them up would cost breadboard space and GPIO pins for no functional gain right now — though INT is worth remembering if you ever want a "wake on the minute" interrupt instead of polling the RTC in a loop.

## Power note — still an open decision

This table assumes peripherals draw power from the Pico's own **3V3(OUT)** pin, with your external 3.3V regulator feeding **VSYS** and the Pico's onboard switching regulator doing the final conversion. That's the simpler wiring option, but it means the "RF-quiet" benefit of your external linear regulator only applies to the Pico's own core — not to the GPS/RTC/OLED, which would still be running off the Pico's internal switcher. If RF quietness for the peripherals matters too, the alternative is running your external regulator's 3.3V output directly to a shared rail that powers the Pico's VSYS *and* the peripherals in parallel, bypassing 3V3(OUT) entirely. Worth deciding before you commit to wiring.
