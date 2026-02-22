import json
import subprocess
from pathlib import Path

import pytest


def test_example_metadata_matches_schema():
    pytest.importorskip("jsonschema")
    from jsonschema import validate

    base = Path(__file__).resolve().parents[1]
    schema_path = base / "docs" / "metadata_schema.json"
    example_path = base / "examples" / "metadata" / "petr4_snapshot.json"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(example_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Should not raise
    validate(instance=data, schema=schema)


def test_validate_script_returns_ok(tmp_path, capsys):
    pytest.importorskip("jsonschema")

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "validate_metadata.py"
    )
    example = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "metadata"
        / "petr4_snapshot.json"
    )

    res = subprocess.run(
        ["python3", str(script), str(example)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, (
        f"Script failed: {res.stdout}\n{res.stderr}"
    )
    assert "OK: metadata is valid" in res.stdout
