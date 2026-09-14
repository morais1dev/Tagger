from metadata import ler_tags, abrir_arquivo, editar_tags, TAGS_EDITAVEIS
from interface import selecionar_arquivo

def main():
    arquivos = selecionar_arquivo()

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        return

    for arquivo in arquivos:
        print(f"\nArquivo: {arquivo}")
        audio = abrir_arquivo(arquivo)

        if audio is None:
            print("Formato não suportado.")
            continue
        tags = ler_tags(audio)
        for numero, valor in tags.items():
            tag = TAGS_EDITAVEIS[numero]
            print(f"{numero} - {tag}: {valor}")
        escolha = int(input("\nQual tag deseja editar? "))

        tag = TAGS_EDITAVEIS[escolha]

        novo_valor = input(f"Novo valor para {tag}: ")

        editar_tags(audio, tag, novo_valor)

        print("Tag editada com sucesso.")

if __name__ == "__main__":
    main()