# Milestones

**Version 0.1** · 2026-11-12

**Rules:**
- Firmware version is **`0.<milestone>.<patch>`** until v1 ships, which is **`1.0.0`**.
- When a milestone is finished:
  - its exit criteria are ticked,
  - `CONTEXT.md` §5 is updated in the same PR,
  - the merge commit is tagged `v0.N.0`.
- **A milestone isn't done until its exit criteria are ticked.** "It mostly works" goes on the next
  milestone's list.
- **Size** is relative effort for one part-time person: S = days, M = 1–2 weeks, L = several weeks.
- M1–M2 (board) and M3 (detector on a PC) can run at the same time; M3 fills the wait while JLC builds the boards.

| M | Version | Name | Goal | Biggest risk it retires | Size | Status |
|---|---|---|---|---|---|---|
| M0 | 0.0 | Toolchain & bring-up firmware | Firmware builds; lamp, LED, button and ADC work on a bare module | Toolchain, ADC sample rate | S | software done, not run on hardware |
| M1 | 0.1 | Schematic | `docs/BOARD_TODO.md` applied, checker clean, reviewed | The two must-fix bugs | S | not started |
| M2 | 0.2 | Layout & order | Board laid out, reviewed and ordered from JLC | Analogue noise, mic port | M | not started |
| M3 | 0.3 | Detector on a PC | `clap_dsp` in C matches the Python model; capture tools ready | DSP correctness | M | not started |
| M4 | 0.4 | Board bring-up | Every bring-up check in DESIGN.md passes on a real board | Hardware bugs | S | waits for M2 boards |
| M5 | 0.5 | Detector on the device | Dataset recorded on the board; detector tuned to the §3 targets | False triggers | M | waits for M3 + M4 |
| M6 | 1.0 | Soak & ship v1 | 72 h soak passes; v1.0.0 tagged | Real-room reliability | S | — |
| M7 | 1.1 | v1.1 (optional) | Rail-to-rail op-amp, lamp detect, VBUS monitor, enclosure polish | — | M | — |

---

## M0 — Toolchain & bring-up firmware · v0.0 · S

**Goal:** the firmware builds for everyone and the basic I/O works on a real SuperMini.

**Already done (PR #1, merged 2026-11-02):** build fixes, `adc_sampler` rework, `board`/`lamp`/`ui` components,
bring-up app, `sdkconfig.defaults`.

**Exit criteria:**
- [x] `idf.py set-target esp32c3 && idf.py build` passes, warnings-as-errors left on
- [ ] `idf.py --version` recorded in CONTEXT §9 for Joe's machine
- [ ] Bare SuperMini: `idf.py -p /dev/ttyACM0 flash monitor`, LED blinks every 2 s, BOOT toggles GPIO3 (meter or LED on the pin)
- [ ] The 1 s ADC log shows about 16 000 samples/s and 0 overflows
- [ ] *(optional)* GitHub Actions builds the firmware on every PR

**Claude can help with:** IDF install problems, reading the monitor output, the CI workflow.

---

## M1 — Schematic · v0.1 · S

**Goal:** the schematic has every fix in `docs/BOARD_TODO.md` and nothing else changed by accident.

**You do (KiCad, branch `hw/board-todo`, L1):**
1. Step 0: KiCad project into `hardware/`, project-local `easyeda2kicad` library, import the SY6280.
2. Steps 1–9 of `docs/BOARD_TODO.md`, top to bottom.
3. Step 10: ERC clean, then `python3 tools/check_board_todo.py hardware/<name>.kicad_sch`.

**Decide first:** Q1 (lamp). It sets R_SET and which lamp connector is fitted.

**Exit criteria:**
- [ ] Q1 answered; R_SET value and fitted connector recorded in CONTEXT §6
- [ ] `check_board_todo.py` reports 0 to fix
- [ ] KiCad ERC: 0 errors; any warnings explained in the PR
- [ ] Every new footprint checked 1:1 against its datasheet (U3 pin 1, D1/D3 cathodes, U2 sound hole, J5)
- [ ] Claude review of the schematic done, comments resolved; PR merged

**Claude can help with:** running the checker and explaining each failure, reviewing footprints, part lookups.

---

## M2 — Layout & order · v0.2 · M

**Goal:** a board that can be ordered with confidence.

**You do (branch `hw/layout`, L1):** follow "Layout settings to enter first" in `docs/BOARD_TODO.md`, then the
PCB layout guide and checklist in `docs/DESIGN.md`.

**Decide first:** Q3 (enclosure: board outline, sound hole, connector ends), Q4 (assembly), Q6 (Wi-Fi later?).

**Exit criteria:**
- [ ] Every box in the DESIGN.md layout checklist ticked
- [ ] DRC clean; 3D view checked for heights
- [ ] 1:1 printout test-fitted with the real SuperMini and connectors
- [ ] JLC placement preview checked part by part (rotations, polarity)
- [ ] Claude review of the layout done; PR merged
- [ ] Boards ordered (Joe only; Claude never orders). Order number in CONTEXT §5

**Spend:** about the cost of 5 assembled boards at JLC, plus extended-part fees.

---

## M3 — Detector on a PC · v0.3 · M

**Goal:** the clap detector runs in C, is proven identical to the Python model, and the capture tools are ready
for M5. Runs alongside M2 and the fab wait.

**Decide first:** Q7, the working level for `clap_dsp` and for the tools.

**You build:**
1. `test/host/` with Unity and `run.sh`, as in ad-tracker.
2. `components/clap_dsp`: pure C port of `tools/clap_model_reference.py` (no ESP-IDF, no malloc, no logging).
3. Host tests: unit tests per stage, then whole-file tests where the C event log must equal the Python one.
4. Capture mode: stream raw samples over USB-Serial-JTAG; `tools/capture.py` turns them into WAV files.
5. `tools/eval.py`: scores the labelled dataset (detection by distance, false toggles per hour, latency).
6. Wire `clap_dsp` into the audio task behind a Kconfig switch.

**Exit criteria:**
- [ ] `./test/host/run.sh` passes; every `clap_dsp` branch covered
- [ ] C and Python event logs identical on the synthetic suite and on phone-recorded WAVs
- [ ] `idf.py build` passes with `clap_dsp` linked; per-sample cost measured or estimated
- [ ] Capture works end to end on a bare SuperMini (a WAV of noise is enough before the board exists)

---

## M4 — Board bring-up · v0.4 · S

**Goal:** prove the hardware before trusting any detector result on it.

**You do:** the bring-up checklists in DESIGN.md "Test & validation", in order: board without the module, then
with the module, then the analogue checks in capture mode.

**Exit criteria:**
- [ ] Every bring-up box ticked, with measurements recorded in the PR
- [ ] Lamp stays off through power-up, reset and flashing
- [ ] Short on the lamp port: the switch limits, the ESP32 keeps running; D2 fitted only if needed
- [ ] Hot-plug peaks on J1 stay under 6 V
- [ ] Noise floor and clap levels at 0.5–4 m recorded in CONTEXT §5
- [ ] Any board bugs listed for rev B (or "none")

---

## M5 — Detector on the device · v0.5 · M

**Goal:** the detector meets the CONTEXT §3 targets on recordings made through the real board.

**You do:**
1. Record the dataset with capture mode (DESIGN.md "Detector dataset"): positives, hard negatives, background.
2. Label it; run `tools/eval.py`.
3. Tune parameters in the Python model first, then the same values in Kconfig. Re-score everything after each change.

**Exit criteria:**
- [ ] Dataset recorded and labelled (ship-fast size at least: 50 double claps, 100 hard negatives, 2 h background)
- [ ] §3 detection and false-toggle targets met on the dataset
- [ ] Host and device give the same event log on the same capture
- [ ] Q5 (lamp state after a power cut) answered and implemented

---

## M6 — Soak & ship v1 · v1.0.0 · S

**Exit criteria:**
- [ ] 24 h soak (ship-fast) or 72 h (good), every candidate event logged; each false toggle explained
- [ ] All must-fix items closed; agreed should-fix items closed
- [ ] README updated for users: what it does, how to set it up, the BOOT-button fallback
- [ ] Tagged `v1.0.0`

---

## M7 — v1.1 (optional)

Rail-to-rail op-amp (#18), J4 lamp detect (#15), VBUS monitor (#17), fit the parked LED and button if the
enclosure needs them, enclosure polish, Wi-Fi/Home Assistant if wanted (Q6).
