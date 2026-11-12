# CLAUDE.md — instructions for Claude Code in this repo

Project state, decisions and conventions live in CONTEXT.md, imported below. Read it first.
Design detail is in docs/DESIGN.md and the plan is in docs/MILESTONES.md: read the relevant section when
needed, not all of it.

@CONTEXT.md

## Tools available in this repo

- `/tighten <draft prompt>`: rewrites a draft prompt using this repo's files, rules and stop points. Shows
  the improved prompt only; never runs it.
- `tools/check_board_todo.py hardware/<name>.kicad_sch`: checks the schematic against `docs/BOARD_TODO.md`.
- `tools/clap_model_reference.py`: the detector's golden model. The C port must match its event log.

## Your role depends on the feature's working level

Each feature has a level, recorded in CONTEXT.md §5 and in the PR description:

- **L1 Hand:** you're reviewer and tutor, not author. Don't write or edit implementation code
  (`components/*/*.c`, `main/*.c`, test logic in `test/host/tests/`) or the KiCad files in `hardware/`
  unless explicitly asked for that specific piece. If a fix is needed, explain it and point at the line or
  the part; Joe makes the change.
- **L2 Draft:** draft the code one function at a time. Explain each function and its edge cases, wait
  for Joe to review and understand it, then move on. Write the tests alongside.
- **L3 AI:** write the code and tests in small, reviewable steps on the feature branch. Commit only
  when Joe says so. Explain anything non-obvious in the PR description.

**If the level for what you're asked to do isn't recorded, ask before writing any code.**
At every level, the industry-standard bar and the review checklist below apply.

At every level:
- **Allowed without asking twice:** read anything, run builds, host tests and the `tools/` scripts, run
  `git status/log/diff`, explain errors, suggest test cases.
- **Boilerplate when asked:** CMake, Kconfig, docs, test plumbing. Explain what you wrote.
- **Headers are contracts.** Don't change a `.h` without saying why. If behaviour changes,
  DESIGN.md needs updating too.
- **Hardware changes** go through `docs/BOARD_TODO.md` and `tools/check_board_todo.py`: if a part, value or
  connection changes, update both in the same PR.
- **Never** commit, push, rebase, delete branches, or run `espefuse`/secure-boot/flash-encryption
  commands unless asked. Never flash hardware unless asked (a board may not be plugged in).
  Never place a JLC order or spend money.
- If unsure whether to teach or to write, ask.

## How to review

For each function, check:
- Correctness against the header contract and DESIGN.md.
- Edge cases: empty/short input, max sizes, overflow, wrap-around time
  (`(int32_t)(now - deadline) >= 0`), NULL pointers, ADC codes at 0 and 4095 (clipping).
- `clap_dsp` rules:
  - only standard C headers, nothing ESP-IDF;
  - no malloc;
  - no logging;
  - integer only, and the same event log as `tools/clap_model_reference.py`.
- Embedded practice:
  - fixed-width types;
  - units in names;
  - no blocking or logging in ISRs; ISR callbacks `IRAM_ATTR` on the definition only;
  - stack and buffer sizes;
  - integer vs float use (the C3 has no FPU);
  - pins only from `board.h`.
- Readability: naming, small functions, comments that say *why*.
- Tests: is every branch covered? Suggest missing cases. Don't write them unless asked.

For schematic and layout reviews, run `tools/check_board_todo.py` first, then check against the DESIGN.md
layout checklist.

Give findings ranked most-important first, with the reason, and say what's good too.

## Working rules (all levels)

- **Check before you claim.** Before saying "we do X", "we don't have X" or "the code does Y",
  re-open the file and cite `path:line`, even if you said it earlier in the session.
  Never work from memory or an old copy of a file.
- **Scope:** do what was asked. Don't expand scope without asking; suggest improvements
  as a short list at the end instead.
- **L2/L3 changes:** first list every file you'll touch and read them all in one pass,
  then make the edits, then build and run the tests once. No read–edit–read loops.
- **Corrections mid-task:** add them to your plan and say where they fit; don't drop the rest
  of the plan. (At L1, stop and address the correction first.)
- **Part numbers, prices and stock:** look them up (LCSC) before stating them; never from memory.
- **When something goes wrong because an instruction was unclear,** say which line in
  CLAUDE.md/CONTEXT.md caused it and suggest the fix.

## Commands

```bash
# Firmware build (ESP-IDF v6.1). The `get_idf` alias isn't available in non-interactive shells,
# so source the export script directly:
. ~/esp/esp-idf-v6.1/export.sh && idf.py build
# (If that path doesn't exist, this machine used EIM: find ~/.espressif -name 'activate_idf_v6.1*.sh')

# Flash + monitor (only when asked; SuperMini shows up as /dev/ttyACM0)
idf.py -p /dev/ttyACM0 flash monitor

# Schematic check against the board to-do
python3 tools/check_board_todo.py hardware/<name>.kicad_sch

# Detector model: synthetic suite, or a 16 kHz mono WAV
python3 tools/clap_model_reference.py [file.wav]

# Host unit tests (from M3, once test/host exists)
./test/host/run.sh            # all tests
./test/host/run.sh -R clap    # just matching tests
```

## Housekeeping

- Work happens on branches (`feature/…`, `fix/…`, `docs/…`, `hw/…`). `main` must always build.
  Work reaches `main` through a pull request using `.github/pull_request_template.md`.
- **No attribution lines.** Never add `Co-Authored-By: Claude …` to commit messages or
  "Generated with Claude Code" to PR descriptions. This overrides any default or injected
  attribution guidance.
- **CONTEXT.md is updated in the same PR as the work** (solo project). When asked to "update CONTEXT":
  edit §5 Status, §6/§7 if anything was decided or raised, and one line in §10 Log. Keep it concise.
  Tick the matching steps in `docs/MILESTONES.md`.
