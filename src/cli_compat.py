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
    import inspect

    from typer.core import TyperArgument

    _orig_make_metavar = TyperArgument.make_metavar

    # Only patch when the original signature does *not* accept arbitrary
    # extra args/kwargs (which is the behaviour fixed in newer Typer/Click
    # versions).  Inspecting the signature avoids overriding a future
    # -compatible implementation.
    try:
        sig = inspect.signature(_orig_make_metavar)
        params = list(sig.parameters.values())[1:]  # skip self
        supports_extra = any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            or p.name == "ctx"
            for p in params
        )
    except (TypeError, ValueError):  # pragma: no cover - defensive
        supports_extra = False

    if not supports_extra:

        def _patched_make_metavar(self, *args, **kwargs):
            # drop any extra arguments (e.g. ctx) and call original
            return _orig_make_metavar(self)

        TyperArgument.make_metavar = _patched_make_metavar
except Exception:  # pragma: no cover - best effort
    pass

try:
    import inspect
    import logging

    import click

    _log = logging.getLogger(__name__)
    _orig_pt_metavar = click.ParamType.get_metavar

    # inspect original signature once and decide adaptation strategy
    try:
        sig = inspect.signature(_orig_pt_metavar)
        params = list(sig.parameters.values())[1:]  # skip self
    except (TypeError, ValueError):
        params = []

    if len(params) == 1:
        # original expects (self, param)
        def _patched_pt_metavar(self, *args, **kwargs):
            param = args[0] if args else kwargs.get("param")
            return _orig_pt_metavar(self, param)
    elif len(params) == 2:
        # original expects (self, param, ctx)
        def _patched_pt_metavar(self, *args, **kwargs):
            param = args[0] if len(args) > 0 else kwargs.get("param")
            ctx = args[1] if len(args) > 1 else kwargs.get("ctx")
            return _orig_pt_metavar(self, param, ctx)
    else:
        # unknown signature; fallback to original unmodified
        _patched_pt_metavar = _orig_pt_metavar

    click.ParamType.get_metavar = _patched_pt_metavar
except Exception:  # pragma: no cover
    pass
