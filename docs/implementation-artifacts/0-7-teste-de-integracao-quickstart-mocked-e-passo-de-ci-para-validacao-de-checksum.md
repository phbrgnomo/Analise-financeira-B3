# Story 0.7: teste-de-integracao-quickstart-mocked-e-passo-de-ci-para-validacao-de-checksum

Status: ready-for-dev

## Story

As a QA engineer,
I want an integration test that runs quickstart mocked and validates snapshot checksum,
so that CI can assert end-to-end correctness without external provider dependency.

## Acceptance Criteria

1. Test harness mocks provider responses and runs `pipeline.ingest` for sample ticker.
2. Test verifies snapshot CSV exists and SHA256 checksum matches expected sample.
3. CI job template references this test and fails on mismatch.

## Tasks
- [ ] Implement pytest integration test using mocking (responses/vcrpy or monkeypatch).
- [ ] Add expected checksum sample in `tests/samples/`.
- [ ] Add CI job placeholder to run integration test in CI.

## Dev Notes
- Use lightweight mocking; avoid network calls in CI.
- Keep sample data small to keep CI fast.
