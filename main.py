from src.dados_b3 import cotacao_ativo


if __name__ == '__main__':
    ativos_entrada = input("Lista de Ativos, separados por vírgula (exemplo: PETR4,BBDC3): ")
    ativos = ativos_entrada.split(',')
    data_in = input("Data de inicio (MM-DD-AAAA): ")
    data_fim = input("Data de fim (MM-DD-AAAA): ")
    for a in ativos:
        data = cotacao_ativo(a, data_in, data_fim)
        print(data)