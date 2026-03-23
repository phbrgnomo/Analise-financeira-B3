import src.main as mainmod


def test_streamlit_command_registered():
    """Smoke test: Typer app should expose a command named 'streamlit'."""
    # Typer stores commands on the app object; gather registered names.
    names = [c.name for c in mainmod.app.registered_commands]
    assert "streamlit" in names
