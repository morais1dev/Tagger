from metadata import abrir_arquivo
from interface import selecionar_arquivo

def main():
    arquivos = selecionar_arquivo()

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        return

    for arquivo in arquivos:
        print(f"\nLendo arquivo: {arquivo}")
        audio = abrir_arquivo(arquivo)
        print(audio)

if __name__ == "__main__":
    main()