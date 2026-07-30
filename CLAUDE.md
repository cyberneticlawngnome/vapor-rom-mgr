# Vapor ROM Manager

Python CLI for managing game ROMs and assets across flash carts (3DS XL, DS-Pico).

## Key Files
- `vapor/` — main package (config loader, system plugins, asset handlers)
- `config/` — JSON configs (systems.json, devices/, roms/default.json)
- `tests/` — pytest test suite

## Response Rules
- Be brief. No preamble, no recaps unless asked.
- Skip verifying trivial edits — if Edit/Write succeeded, assume it worked.
- Show code diffs only when the result matters architecturally.
- Assume Python 3.10+. Virtualenv at `.veng/`.
