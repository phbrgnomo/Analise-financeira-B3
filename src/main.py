from datetime import date, timedelta

import typer

from src.paths import DATA_DIR

# Instância principal da aplicação de linha de comando usando Typer
app = typer.Typer()

d_atual = date.today()


@app.command()
def main(validation_tolerance: float | None = typer.Option(None, "--validation-tolerance", help="Tolerância de inválidas (ex: 0.10)")):  # noqa: C901
    # importações locais para evitar exigir dependências apenas para `--help`
    import pandas as pd

    import src.dados_b3 as dados
    import src.retorno as rt

    # ativos_entrada = input(
    #     "Lista de Ativos, separados por vírgula (exemplo: PETR4,BBDC3): "
    # )
    # ativos = ativos_entrada.split(',')
    # data_in = input("Data de inicio (MM-DD-AAAA): ")
    # data_fim = input("Data de fim (MM-DD-AAAA): ")

    # Define ativos a serem pesquisados
    ativos = ["PETR4", "ITUB3", "BBDC4"]

    periodo_dados = 52  # Periodo total dos dados em semanas
    time_skew = timedelta(weeks=periodo_dados)

    d_fim = d_atual.strftime("%m-%d-%Y")
    d_in = (d_atual - time_skew).strftime("%m-%d-%Y")
    print(d_in, d_fim)

    for a in ativos:
        # Verifica se os arquivo já existem
        # {TODO} adicionar verificação se os dados correspondem às datas solicitadas
        data_path = DATA_DIR / f"{a}.csv"
        if data_path.is_file():
            print(f"Dados encontrados para {a}")
            continue
        # Se os dados não existirem, realiza o download
        print(f"Baixando dados de {a}")
        try:
            df = dados.cotacao_ativo_dia(a, d_in, d_fim)
        except Exception as e:
            print(f"Problemas baixando dados: {e}")
            continue
        # Persistir raw provider e registrar metadados
        from datetime import datetime  # import local para minimizar impacto no startup
        from datetime import timezone as _tz

        from src.ingest.pipeline import save_raw_csv
        ts_raw = datetime.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
        save_meta = save_raw_csv(df, "yfinance", f"{a}.SA", ts_raw)
        if save_meta.get("status") != "success":
            print(f"Falha ao salvar raw para {a}: {save_meta.get('error_message')}")
            continue

        # Map to canonical using the checksum and fetched_at produced when saving raw
        try:
            from src.etl.mapper import to_canonical

            canonical = to_canonical(
                df,
                provider_name="yfinance",
                ticker=f"{a}.SA",
                raw_checksum=save_meta.get("raw_checksum"),
                fetched_at=save_meta.get("fetched_at"),
            )
            print(f"Mapper produced {len(canonical)} canonical rows for {a}")
            # Validation step: run validator, persist invalid rows and log them
            try:
                from src.validation import validate_and_handle, ValidationError

                valid_df, invalid_df, summary, details = validate_and_handle(
                    canonical,
                    provider="yfinance",
                    ticker=f"{a}.SA",
                    raw_file=save_meta.get("filepath"),
                    ts=save_meta.get("fetched_at"),
                    raw_root="raw",
                    metadata_path="metadata/ingest_logs.json",
                    threshold=validation_tolerance,
                    abort_on_exceed=True,
                    persist_invalid=True,
                )
                print(
                    f"Validation summary for {a}: rows_total={summary.rows_total}, rows_valid={summary.rows_valid}, rows_invalid={summary.rows_invalid}, invalid_percent={summary.invalid_percent:.4f}"
                )
            except ValidationError as e:
                print(f"Ingest aborted for {a} due to validation threshold: {e}")
                continue
            except Exception as e:
                print(f"Validation step failed for {a}: {e}")

        except Exception as e:
            print(f"Mapper failed for {a}: {e}")
        # Calcula o retorno (usa coluna ajustada quando disponível, senão `close`)
        print(f"Calculado retornos de {a}")
        price_candidates = (
            "Adj Close",
            "adj_close",
            "Close",
            "close",
        )
        price_col = next((c for c in price_candidates if c in df.columns), None)
        if price_col is not None:
            df["Return"] = rt.r_log(df[price_col], df[price_col].shift(1))
        else:
            df["Return"] = None
        # Salva dados em .csv
        # Garantir que o diretório exista e salvar
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path)

    for a in ativos:
        # Abre o arquivo de dados
        try:
            df = pd.read_csv(DATA_DIR / f"{a}.csv")
        except Exception as e:
            print(f"Dados para {a} não encontrados: {e}")
            continue
        retorno_total = df["Return"].sum()
        retorno_medio = df["Return"].mean()
        risco = df["Return"].std()
        retorno_anual = rt.conv_retorno(retorno_medio, 252)
        risco_anual = rt.conv_risco(risco, 252)

        print(f"\n--------{a}--------")
        print(f"Retorno total do período: {round((retorno_total * 100), 4)}%")
        print(f"Retorno médio ao dia: {round((retorno_medio * 100), 4)}%")
        print(f"Risco ao dia: {round((risco * 100), 4)}%")
        print(f"Retorno médio ao ano: {round((retorno_anual * 100), 4)}%")
        print(f"Risco ao ano: {round(risco_anual * 100, 4)}%")
        print(f"Coeficiente de variação(dia):{rt.coef_var(risco, retorno_medio)}")

        # Calcula projeção de faixa de expectativa de retorno
        # Evita índices literais: busca coluna de preço preferida e pega último valor
        price_candidates = ("Adj Close", "adj_close", "Close", "close")
        last_price = None
        for c in price_candidates:
            if c in df.columns:
                try:
                    last_price = float(df[c].iloc[-1])
                except Exception:
                    last_price = None
                break
        if last_price is None:
            # fallback: tentar última célula existente (evita index literal)
            try:
                last_row = df.iloc[-1]
                # prefer coluna 'close' se existir
                if "close" in df.columns:
                    last_price = float(last_row["close"])
                else:
                    # pega primeiro valor numérico na linha
                    for v in last_row:
                        try:
                            last_price = float(v)
                            break
                        except Exception:
                            continue
            except Exception:
                last_price = 0.0
        ultimo_preco = round(last_price, 2)
        proj_preco = ultimo_preco * (1 + retorno_anual)
        print("\nProjeçoes para o 1 ano:")
        print(f"Ultimo Preco: {ultimo_preco}")
        print(f"Retorno máximo: {round(((retorno_anual + risco_anual) * 100), 4)}%")
        print(f"Preço máximo: {proj_preco * (1 + risco_anual)}")
        print(f"Retorno mínimo: {round(((retorno_anual - risco_anual) * 100), 4)}%")
        print(f"Preço mínimo: {proj_preco * (1 - risco_anual)}")

    # Calcula correlação entre os ativos
    newdf = rt.correlacao(ativos)
    print(newdf)


if __name__ == "__main__":
    app()
