# CONTEXT — Azura v1

> **Read this first, every session.** It's the single source of truth for *where we are*.
> How it works → `docs/DESIGN.md` · What's next → `docs/MILESTONES.md` · KiCad changes → `docs/BOARD_TODO.md` ·
> Interfaces → the `.h` files.
>
> Last updated: **2026-11-12** · Current milestone: **M1 (schematic) and M3 (detector on a PC), not started**

---

## 1. What we're building

A USB-C pass-through box that switches a 5 V USB lamp when you clap twice:

1. 5 V in on USB-C (J1); the lamp plugs into J4 (USB-C) or J5 (USB-A).
2. A MEMS mic and an LM358 gain stage feed the ESP32-C3's ADC at 16 kHz.
3. An integer leaky-integrator detector finds double claps and rejects knocks, music, speech and applause.
4. A double clap toggles the SY6280 load switch that feeds the lamp port.

One person (Joe). Firmware, the KiCad board and the detector all live in this repo.

## 2. How we work

- **Working level is chosen per feature.** At the start of each feature (before its branch is made),
  agree a level and record it in the §5 table and the PR description:

  | Level | Who writes the code | Claude's role |
  |---|---|---|
  | **L1 Hand** | Joe | Tutor + reviewer. Explains first, gives hints and test cases, doesn't hand over finished `.c` logic |
  | **L2 Draft** | Claude drafts, function by function | Joe reviews line by line and must be able to explain every line before merging |
  | **L3 AI** | Claude | Joe reviews the PR and tests it. For drivers, glue, tools, scripts, CI, docs |

  Whatever the level: tests pass, Joe approves every merge, whoever merges can explain the code, and
  hardware testing is never skipped. If a feature's level isn't recorded, Claude asks before writing code.
- **Quality bar: solid, industry-standard firmware and hardware**, not "works on my desk". Reviews are honest
  about correctness, edge cases, naming, readability and embedded practice, and explain *why*.
- **Headers are contracts.** To change one: edit the header, update DESIGN.md if behaviour changed, log it in §6.
- **Minimal BOM at every step**, using the rules in §4.
- **Git workflow:** one branch per task (`feature/…`, `fix/…`, `docs/…`, `hw/…`), small commits, a PR into
  `main` using `.github/pull_request_template.md`, **squash and merge**, delete the branch. Nobody pushes to `main`.
- **CONTEXT.md is updated in the same PR** as the work it describes (solo project, so no merge conflicts).
  Edit §5 Status, §6/§7 if anything was decided or raised, and add one line to §10.
- **The repo is the master.** `docs/DESIGN.md` and `docs/BOARD_TODO.md` started as snapshots of the Claude Doc
  "Azura v1 — Design Doc & Plan of Action"; from now on the repo copies win if they differ. Copies in the
  *azura-v1* claude.ai project are snapshots too, so attach the current CONTEXT.md when starting a new chat there.
- **Tools:** Claude Code in the repo for code, reviews and builds (follows `CLAUDE.md`); `/tighten` to sharpen a
  prompt before running it; project chats for learning, design and planning.

## 3. Targets (proposed — confirm or change)

| Target | Value | Status |
|---|---|---|
| Detection, double claps at 1–3 m, quiet room | ≥ 95 % | proposed |
| Detection with TV or music at conversation level | ≥ 85 % | proposed |
| False toggles from household sound | ≤ 1 per 24 h (stretch ≤ 1 per week) | proposed |
| Latency, second clap → lamp change | ≤ 600 ms for clap gaps up to 400 ms | proposed |
| Lamp current | ≤ 1 A (5 W); R_SET 4.7 kΩ → limit 1.1–1.8 A | proposed (Q1) |
| Board draw, lamp off, radio off | < 50 mA | proposed |
| Fitted parts | 32 (40 as first drawn) | agreed |

## 4. BOM rules

1. Smallest BOM that meets §3. Every part earns its place; optional parts go in as unfitted (DNP) footprints.
2. Reuse an existing BOM line before adding a value (R_SET = R14's 4.7 kΩ, R8 = R11's 22 kΩ, C12 = C4's 10 µF).
3. Record LCSC number, stock and basic/extended status for every new part. Extended parts cost a JLC setup fee.
4. Firmware instead of hardware where it works (module LED and BOOT button before a carrier LED and switch).
5. **Never burn eFuses** (secure boot, flash encryption) on dev modules. It's irreversible.

## 5. Status

- **Milestone:** M0 done in software (PR #1 merged 2026-11-02). Nothing run on hardware yet.
  Joe hasn't started M1. Full step-by-step plan: `docs/MILESTONES.md`.

  | Task | Branch | Level |
  |---|---|---|
  | Phase 0 firmware: build fixes, adc_sampler rework, lamp/ui/board, bring-up app | merged (PR #1) | L3 |
  | Board to-do in KiCad (M1) | `hw/board-todo` (to make) | L1, Joe in KiCad |
  | `clap_dsp` C port + host tests (M3) | — | decide at start |
  | Capture mode + `tools/capture.py` / `eval.py` (M3) | — | decide at start |
- **Done:**
  - 2026-10-20: design doc, schematic review (netlist by script), DSP reference model, board to-do,
    `tools/check_board_todo.py`. Joe chose the SY6280, a minimal BOM, and parked the LED and switch.
  - 2026-11-02: PR #1 merged. Firmware builds clean on ESP-IDF v6.1 for esp32c3.
  - 2026-11-12: CLAUDE.md, CONTEXT.md, MILESTONES.md, PR template and `/tighten` set up like ad-tracker.
- **Hardware on hand:** not recorded (Q2).
- **Next actions:**
  1. Joe: answer Q1 (lamp) and Q2 (hardware on hand); pick the level for `clap_dsp`.
  2. Joe: flash the bring-up build on a bare SuperMini (M0 last step).
  3. Joe: start `docs/BOARD_TODO.md` step 0 on branch `hw/board-todo`.

## 6. Decisions

| ID | Date | Decision | Why | Status |
|---|---|---|---|---|
| D-01 | 10-20 | SY6280AAC (C55136) load switch replaces the discrete limiter and Q3/Q4 output switch | 0.12 V drop vs 0.62 V, thermal shutdown, reverse blocking, 8 parts → 2. Also fixes the switched-GND bug | agreed |
| D-02 | 10-20 | Minimal BOM; optional parts as DNP footprints | Cost and assembly time | agreed |
| D-03 | 10-20 | Status LED and fallback switch parked: DNP D4+R21 (GPIO7) and SW1 (GPIO10); firmware uses module LED (GPIO8) and BOOT (GPIO9) | Zero BOM until the enclosure shows they're needed | agreed |
| D-04 | 10-20 | R_SET 4.7 kΩ (1.1–1.8 A). 4.3 kΩ is the floor; over ~1.1 A needs another switch | ±25 % limit tolerance, 2 A device ceiling | proposed (Q1) |
| D-05 | 10-20 | R15 removed; ADC sees U1 directly (bias 1.1 V ≈ 1800 codes); R8 22 kΩ + C9 1 nF anti-alias (7.2 kHz) | 1.5× resolution, no new part; same detector score as 4.8 kHz | proposed |
| D-06 | 10-20 | C12 10 µF at the SY6280 OUT; D2 unfitted | SY6280 pins are rated to 6 V; the lamp port had no capacitor | proposed |
| D-07 | 10-20 | D3 B5819W from USB_VBUS to the module's 5V pin | Stops the PC and charger supplies being tied together | agreed (must-fix) |
| D-08 | 10-20 | Detector: integer leaky integrators (fast envelope vs slow floor) + timing state machine; Python model in `tools/` is the golden reference | No FPU; testable on a PC | proposed |
| D-09 | 10-20 | ESP-IDF v6.1, C, ESP32-C3 SuperMini socketed, Wi-Fi/BLE off in v1 | Matches ad-tracker toolchain | agreed |
| D-10 | 10-20 | Lamp off after any reset or power cut | Safe default | proposed (Q5) |

## 7. Open questions

| ID | Question | Needed by |
|---|---|---|
| Q1 | Which lamp? Current at full brightness, USB-A or USB-C plug, PWM dimming? ≤ 5 W keeps the SY6280 | M1 (R_SET, fitted connector) |
| Q2 | What hardware is on hand (SuperMini, breadboard mic + LM358)? | M0 last step, M3 capture |
| Q3 | Enclosure: inline box assumed (input one end, lamp the other, sound hole under the board) | M2 (board outline) |
| Q4 | Assembly: JLC top-side SMT + hand-soldered THT, 5 boards? | M2 (order) |
| Q5 | Lamp state after a power cut: off (assumed) or restore? | M5 |
| Q6 | Wi-Fi/BLE later (Home Assistant)? Affects antenna keep-out only for now | M2 |
| Q7 | Level for `clap_dsp` and the capture tools (L1 / L2 / L3)? | M3 start |

## 8. Conventions

- **Pins** live only in `components/board/include/board.h`.
- **Naming:** public symbols have a module prefix (`adc_sampler_`, `lamp_`, `ui_`, `clap_`). Types end in `_t`.
  Macros and constants are `UPPER_CASE` with the prefix.
- **Units in names:** `_ms _s _hz _mv _codes _lsb`.
- **Audio path is integer-only** (the C3 has no FPU). Leaky integrators as `state += x - (state >> k)`.
- **`clap_dsp`** is pure C: standard headers only, no ESP-IDF, no malloc, no logging. Unit-tested on a PC and
  must give the same event log as `tools/clap_model_reference.py` on the same samples.
- **Errors:** platform code returns `esp_err_t`; `clap_dsp` returns plain values.
- **Logging:** `ESP_LOGx` with tag = module name, never in ISRs, never per frame in the audio task.
- **Time:** compare wrap-safely: `(int32_t)(now - deadline) >= 0`.
- **Schematic references** follow `docs/BOARD_TODO.md`; `tools/check_board_todo.py` finds parts by reference.
- **Git:** `main` always builds. `build/`, `test/host/build/` and `sdkconfig` are never committed.
- **Tests:** expected values come from outside the code under test (the Python model, hand-checked vectors).
  Watch each new test fail before making it pass.
- British English in docs.

## 9. Toolchain

| Item | Value |
|---|---|
| ESP-IDF | **v6.1**. Activate with `. ~/esp/esp-idf-v6.1/export.sh` (or the EIM activate script) |
| Target | `esp32c3` (SuperMini). Console on USB-Serial-JTAG, shows up as `/dev/ttyACM0` |
| Host tests | Planned for M3: `test/host/` with Unity, as in ad-tracker |
| Python tools | `tools/check_board_todo.py`, `tools/kicad_netlist.py`, `tools/clap_model_reference.py` (numpy, scipy) |
| KiCad | 10, project to live in `hardware/` with a project-local `easyeda2kicad` library |
| Fab | JLCPCB, 2-layer 1.6 mm, ENIG |
| Repo | https://github.com/JoeGould1878/azura_v1 |
| Claude sandbox build | No PyPI or dl.espressif.com there: clone ESP-IDF v6.1 with submodules, get the riscv toolchain URL from `tools/tools.json` (GitHub assets work), put Python deps from GitHub source trees on PYTHONPATH (esp-idf-kconfig, esp-pylib, esptool, rich, rich-click, pyelftools, pyserial, intelhex, reedsolomon, bitstring), then `cmake -S . -B <build> -G Ninja -DPYTHON_DEPS_CHECKED=1` with `IDF_COMPONENT_MANAGER=0` and `ninja -C <build>` |

## 10. Session log

- **2026-10-20:** Read the repo and schematic, wrote the design doc, DSP model and board to-do. Joe chose the
  SY6280 and a minimal BOM. Phase 0 firmware (PR #1) built and pushed; review fixed R_SET, added C12, R8 22k,
  DNP LED, `check_board_todo.py`.
- **2026-11-12:** Restructured the repo's Claude setup to match ad-tracker and apify-uk-data: CLAUDE.md with
  working levels, CONTEXT.md (this file, was `context.md`), `docs/MILESTONES.md`, PR template, `/tighten`.
  Renamed `docs/design.md` → `DESIGN.md`, `docs/board-todo.md` → `BOARD_TODO.md`.

## 11. Glossary

**SY6280** USB load switch with a resistor-set current limit · **R_SET** the resistor that sets it ·
**DNP** do not populate (footprint only) · **TVS** transient voltage suppressor · **MEMS mic** chip microphone ·
**Bottom port** the mic hears through a hole in the PCB · **Anti-alias filter** RC that removes content above
half the sample rate · **STA/LTA** short-term vs long-term average trigger · **Leaky integrator** one-pole
low-pass, `y += (x − y) >> k` · **Golden model** the reference implementation the C port must match ·
**Netlist** list of which pins connect · **ERC/DRC** KiCad electrical / design rule check
