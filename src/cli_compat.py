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
    #-compatible implementation.
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
    import logging

    import click

    _log = logging.getLogger(__name__)
    _orig_pt_metavar = click.ParamType.get_metavar

    def _patched_pt_metavar(self, *args, **kwargs):
        """
        Compatibility wrapper around click.ParamType.get_metavar.

        Some Click versions changed the signature of this method.  We try the
        original call and, on a signature-related ``TypeError``, retry with
        reduced arguments.  Non-signature TypeErrors are propagated so errors
        in custom ParamTypes surface normally.
        """
        try:
            return _orig_pt_metavar(self, *args, **kwargs)
        except TypeError as exc:
            msg = str(exc)
            signature_mismatch = any(
                hint in msg
                for hint in (
                    "positional argument",
                    "positional arguments",
                    "required positional argument",
                    "unexpected keyword argument",
                    "takes from",
                    "takes 1 positional argument",
                    "takes 2 positional arguments",
                )
            )
            if not signature_mismatch:
                raise

            _log.debug(
                "cli_compat: falling back in ParamType.get_metavar for %s due to %r; "
                "this usually indicates a Click version/signature mismatch",
                type(self).__name__,
                exc,
            )

            try:
                return _orig_pt_metavar(self, None, None)
            except TypeError:
                return _orig_pt_metavar(self)

    click.ParamType.get_metavar = _patched_pt_metavar
except Exception:  # pragma: no cover
    pass
