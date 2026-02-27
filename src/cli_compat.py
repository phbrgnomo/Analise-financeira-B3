"""Compatibility shims for Typer/Click mismatches.

This module centralizes the monkeypatch logic moved out of ``src.main`` so
that the main CLI file can focus purely on command definitions.  The
patches address issues with Python 3.14 / Click 9.x where Typer's bundled
version of Click does not match the signature expected by the newer
runtime.

The original code was introduced during story 1.3 and kept in ``src.main``
for expedience; refactoring it here makes the intent clearer and avoids
polluting the CLI import path with unrelated compatibility logic.
"""

from __future__ import annotations

try:
    from typer.core import TyperArgument

    _orig_make_metavar = TyperArgument.make_metavar

    def _patched_make_metavar(self, *args, **kwargs):
        # drop any extra arguments (e.g. ctx) and call original
        return _orig_make_metavar(self)

    TyperArgument.make_metavar = _patched_make_metavar
except Exception:  # pragma: no cover - best effort
    pass

try:
    import click

    _orig_pt_metavar = click.ParamType.get_metavar

    def _patched_pt_metavar(self, *args, **kwargs):
        try:
            return _orig_pt_metavar(self, *args, **kwargs)
        except TypeError:
            # missing arguments? fall back with placeholders
            try:
                return _orig_pt_metavar(self, None, None)
            except TypeError:
                # last resort, just call without extras
                return _orig_pt_metavar(self)

    click.ParamType.get_metavar = _patched_pt_metavar
except Exception:  # pragma: no cover
    pass
