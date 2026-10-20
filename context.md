# Azura v1 — Claude's working context

Last updated: 2026-10-20 (session 1). Read this first in any new session, then `docs/design.md`.
The living design doc (source of truth) is the Claude Doc linked below; `docs/` holds a snapshot.

## What Azura is
ESP32-C3 SuperMini (socketed) on a carrier board. USB-C 5 V in (J1), one switched 5 V lamp output
(J4 USB-C or J5 USB-A). MEMS mic MSM381ACB026 → LM358 gain stage → ADC1_CH0 (GPIO0) at 16 kHz.
A double clap toggles the lamp via GPIO3 (SY6280 EN). Firmware: C on ESP-IDF v6.1. Owner: Joe Gould (JoeGould1878).

## Links
- Repo: https://github.com/JoeGould1878/azura_v1
- Design doc + plan (Claude Doc, private): https://claude.ai/code/artifact/4a4da1dd-c438-40f9-902a-6cf1cc44eeb8
  (tab 1: design + plan; tab 2: "Board to-do", the KiCad change list). Snapshots: docs/design.md, docs/board-todo.md.
- Schematic: Project_Az_v1_kicad.kicad_sch (KiCad 10), uploaded in chat 2026-10-20. Not in the repo yet
  (suggest a hardware/ folder once Joe has applied the board to-do).

## State
- Phase 0. Branch `phase0/build-and-hello-lamp` (PR to main): firmware builds on v6.1 (verified: app,
  bootloader, partition table for esp32c3); bring-up app = BOOT toggles lamp, LED heartbeat, 1 s ADC stats.
- Hardware: schematic as drawn has the must-fix bugs; Joe is applying docs/board-todo.md in KiCad, then sends
  the .kicad_sch back for a check with tools/kicad_netlist.py. No PCB layout yet.
- Next firmware step (Phase 1b): port tools/clap_model_reference.py to components/clap_dsp in C, host tests in
  test/host proving identical event logs, capture mode + tools/capture.py, CI.

## Decisions (Joe, 2026-10-20)
- SY6280AAC load switch replaces the discrete limiter + switch (Q1–Q4, R9, R13, R16–R18).
- BOM as small as possible; optional parts go in as unfitted (DNP) footprints. 40 → 31 parts.
- Status LED + fallback switch parked; zero-part version in firmware (module LED GPIO8, BOOT button GPIO9),
  DNP tact-switch footprint on GPIO10.
- Lamp not chosen → assume 5 V ≤ 1.5 A; R_SET (4.3k ≈ 1.2–2.0 A; 3.3k for a 1.5 A lamp) and fitted connector follow.
- No enclosure → assume inline box, sound hole under the board.
- v1 extras: none (VBUS monitor, J4 CC sense, RRIO op-amp → v1.1).
- My defaults, not confirmed: JLC top-side SMT + hand-soldered THT, 5 boards; lamp off after power cut; Wi-Fi off.

## Key facts
- Pins: GPIO0 ADC_IN, GPIO3 lamp EN (R10 pull-down), GPIO8 LED active low, GPIO9 BOOT, GPIO10 optional SW1.
  J3 = 5V/GND/3V3/GPIO4..0 row. Strapping: GPIO2, 8, 9. Verify pin order on the real module.
- Analogue after trims: bias 1.1 V (R4 200k / R7 100k), gain 48, no divider (R15 removed) → ADC bias ≈ 1800 codes,
  1 LSB ≈ 0.61 mV ≈ 34 dB SPL at the mic; clip ≈ 99 dB SPL peak; AA pole R8 10k + C9 3.3 nF ≈ 4.8 kHz.
  R14 4k7 must stay (only DC load → class A). Clap at 4 m ≈ 530 LSB peak (estimate).
- SY6280: 80 mΩ, ILIM = 6800/R_SET ±25 %, abs max 6 V on all pins (below SMAJ5.0A's 6.4 V breakdown → C1
  electrolytic at J1 does the hot-plug damping; keep SMAJ5.0A). EN threshold ≤ 2.4 V → GPIO 3.3 V OK.
- ESP-IDF v6.1 facts (checked in source/build): -Werror on (deprecations excepted); log macros do NOT
  format-check; IRAM_ATTR on prototype + definition → -Werror=attributes; on_conv_done fires even if the ring
  push failed; register_event_callbacks(NULL) → INVALID_ARG; adc_continuous_read returns short at ring wrap;
  C3 result = 4 bytes; fs 611–83333 Hz; ADC_ATTEN_DB_12 ≈ 0–2.5 V; `format` field deprecated.

## DSP design
- Pipeline + starting parameters: design doc "Double-clap DSP". Golden model: tools/clap_model_reference.py
  (synthetic suite 165/170). Trade-off: early-decay limit 15 ms rejects drums but misses some very reverberant
  claps; real recordings decide. Latency = clamp(1.5 × gap, 400, 800) ms ≈ 450 ms at a 300 ms gap.

## Open questions for Joe
- Assembly (JLC top-side + hand THT, 5 boards?); breadboard of the front end?; Wi-Fi/BLE plans?;
  lamp state after power cut; GitHub Actions CI (planned for Phase 1b).

## Building in a Claude sandbox (no PyPI)
- ESP-IDF v6.1 cloned from GitHub with submodules; toolchain via `install.sh esp32c3` (GitHub releases work;
  dl.espressif.com is blocked, so the Python env step fails). Python deps from GitHub source trees on
  PYTHONPATH: esp-idf-kconfig, esp-pylib, rich, rich-click, pyelftools, pyserial, esptool, intelhex, reedsolomon.
- Configure with plain CMake: `cmake -S . -B <build> -G Ninja -DPYTHON_DEPS_CHECKED=1` (skips the constraints
  check), `IDF_COMPONENT_MANAGER=0`, then `ninja -C <build>`.

## Conventions
- "#n" = row n of the design doc's Schematic review table.
- Work on branches + PRs; never push to main directly. Commit trailers per session instructions.
- British English in docs.

## Session log
- 2026-10-20 (session 1): reviewed repo + schematic (netlist by script), wrote the design doc and board to-do;
  Joe chose SY6280 + minimal BOM; Phase 0 firmware built and pushed on phase0/build-and-hello-lamp.
