# Azura v1

A USB-C pass-through box that switches a 5 V USB lamp when you clap twice.

- **MCU:** ESP32-C3 SuperMini (socketed), ESP-IDF v6.1, C.
- **Power:** USB-C 5 V in (J1) → 5 V rail → SY6280 load switch (EN = GPIO3) → lamp port, J4 USB-C (advertises 1.5 A) or J5 USB-A.
- **Audio:** MSM381ACB026 bottom-port MEMS mic → LM358 gain ×48 → RC filter → GPIO0 (ADC1 channel 0), sampled at 16 kHz with DMA.
- **UI:** the module's blue LED (GPIO8) for feedback, its BOOT button (GPIO9) as a manual toggle; optional carrier footprints for a status LED (GPIO7) and a button (GPIO10).

Status: **Phase 0**. The firmware builds and the bring-up app runs on a bare SuperMini; the clap detector (Phase 1b) and the PCB layout (Phase 1) are next. See [docs/design.md](docs/design.md) for the design and plan, [docs/board-todo.md](docs/board-todo.md) for the KiCad change list, and [context.md](context.md) for where things stand.

## Build and flash

```sh
. ~/.espressif/v6.1/esp-idf/export.sh     # or wherever your ESP-IDF v6.1 lives
idf.py build                              # target esp32c3 comes from sdkconfig.defaults
idf.py -p /dev/ttyACM0 flash monitor      # the SuperMini's USB-C is the C3's native USB-Serial-JTAG
```

> **Until the D3 back-feed diode is on the board** (design doc, must-fix #3), don't plug the module's USB into a PC while the board is powered from J1: the two supplies would be tied together.

## What the Phase 0 build does

- BOOT (or SW1) toggles the lamp. The lamp is always off after power-up or reset.
- The LED blinks briefly every 2 s, and flashes longer when the lamp changes state.
- Once a second the log reports the microphone channel: samples per second, mean (the DC bias, about 1800 codes on the v1 board), AC rms, min/max and sampler error counters.

## Layout

```text
main/                    app_main and task wiring
components/adc_sampler/  continuous ADC + DMA capture of the mic channel
components/board/        pin map (board.h)
components/lamp/         lamp enable (GPIO3 / SY6280 EN)
components/ui/           LEDs (module + optional D4) and buttons
docs/                    design doc snapshot, board to-do, diagrams
hardware/                KiCad project (once the board to-do is applied)
tools/                   check_board_todo.py (schematic vs the board to-do), kicad_netlist.py (connectivity dump),
                         clap_model_reference.py (detector golden model)
```
