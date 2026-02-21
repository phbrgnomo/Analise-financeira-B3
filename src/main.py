import os
from datetime import date, timedelta

import typer

# Instância principal da aplicação de linha de comando usando Typer
app = typer.Typer()

d_atual = date.today()


@app.command()
def main():
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
        if os.path.isfile(f"dados/{a}.csv"):
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
        df.to_csv(f"dados/{a}.csv")

    for a in ativos:
        # Abre o arquivo de dados
        try:
            df = pd.read_csv(f"dados/{a}.csv")
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
        ultimo_preco = round(df.tail(1).values[0][6], 2)
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
