# Notes for Claude sessions in this repo

Read `context.md` first: it holds the current state, decisions, open questions and how to build in a sandbox.
The design and plan are in `docs/design.md` (snapshot of the living Claude Doc linked from `context.md`).

- Target: ESP32-C3 SuperMini, ESP-IDF v6.1, C. Pin numbers live only in `components/board/include/board.h`.
- The audio path is integer-only (no FPU on the C3).
- Work on a branch and open a PR; update `context.md` (State and Session log) before finishing.
