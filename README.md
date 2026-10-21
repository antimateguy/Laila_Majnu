# laila-majnu

Privacy-first conversational analytics for adults (18+). A WhatsApp or Instagram DM export is parsed, sanitized and scored in the browser by a C++ engine compiled to WebAssembly; raw chat text never leaves the device.

- Design source of truth: [`docs/LLD.md`](docs/LLD.md)
- Scope boundary: [`docs/FEATURES.md`](docs/FEATURES.md)
- Deviations and gap-fills: [`docs/DECISIONS.md`](docs/DECISIONS.md)
- Contracts: [`schemas/`](schemas/) (JSON Schema 2020-12), generated into `web/src/types/gen.ts` and `api/app/models/`

## Layout

| Path | What |
| --- | --- |
| `schemas/` | JSON Schemas for every DTO, `LocalReport`, policies and archetypes, plus example documents |
| `tools/` | Codegen, schema tests, archetype approval gate |
| `engine/` | C++20 engine (CMake, Catch2) |
| `web/` | Vite + React 18 + TypeScript + Tailwind |
| `api/` | FastAPI on Python 3.12 |
| `fixtures/` | Seeded synthetic exports, expected outputs, labelled PII set |

## Checks

```bash
npm ci
python -m venv api/.venv && api/.venv/Scripts/pip install -r api/requirements-dev.txt   # bin/ on Linux/macOS

npm run test:tools            # schema + archetype gate tests
npm run codegen:check         # generated types match schemas/
npm run archetypes:check      # development gate (production: archetypes:check:prod)
npm run lint -w web && npm run typecheck -w web && npm test -w web && npm run build -w web
python -m unittest discover -s fixtures/generator
```

The API and engine checks run from their own folders (`api/`: ruff, mypy, pytest; `engine/`: `cmake --preset native-asan`, then build and `ctest`). The engine needs clang and CMake ≥ 3.24 (Linux, or Docker on Windows).
