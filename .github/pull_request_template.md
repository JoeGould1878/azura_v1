## Level
<!-- L1 hand-written / L2 AI-drafted, line-by-line reviewed / L3 AI-written (see CONTEXT.md §2) -->

## What
<!-- One or two lines: what does this PR add or change? e.g. "Applies BOARD_TODO steps 0–10" -->

## Why
<!-- Which milestone or decision it serves (e.g. M1, D-04, DESIGN "Double-clap DSP"). Anything surprising. -->

## How it was tested
- [ ] `idf.py build` passes, no warnings
- [ ] `./test/host/run.sh` passes (from M3; paste the summary line)
- [ ] Hardware change: `python3 tools/check_board_todo.py hardware/<name>.kicad_sch` reports 0 to fix, ERC/DRC clean
- [ ] On hardware (if relevant): which board, what you saw

## Checklist
- [ ] Follows the header contract (or the header was updated, and that's explained above)
- [ ] `clap_dsp` code uses no ESP-IDF includes, no malloc, no logging, integer only
- [ ] Pins only from `board.h`; units in names; fixed-width types; edge cases handled
- [ ] DESIGN.md / BOARD_TODO.md / `check_board_todo.py` updated if the design changed
- [ ] CONTEXT.md §5 (and §6/§7, §10) updated, matching MILESTONES.md boxes ticked
- [ ] Reviewed by Claude, comments resolved
