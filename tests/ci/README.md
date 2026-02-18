CI helpers for repository

- `smoke.sh`: script de smoke test executado pelo job `smoke` no workflow CI.

Guidance:
- Place mock fixtures and helper functions here to support CI deterministic runs.
- Keep external network calls mocked using `pytest` fixtures and monkeypatching.
