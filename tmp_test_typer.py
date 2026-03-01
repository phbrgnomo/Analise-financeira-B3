import typer

app = typer.Typer()

@app.command()
def foo(
    source: str = typer.Option("yfinance", "--source", help="help"),
    ticker: str = typer.Argument(...),
):
    print("source", source, "ticker", ticker)

if __name__ == "__main__":
    app()
