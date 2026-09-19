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
        while True:
            tags = ler_tags(audio)
            print("\nTags disponiveis")
            for numero, valor in tags.items():
                tag = TAGS_EDITAVEIS[numero]
                print(f"{numero} - {tag}: {valor}")
            print("0 - Finalizar edicao deste arquivo")

            escolha = input("\nQual tag deseja editar?")

            if escolha == "0":
                break

            try:
                escolha = int(escolha)
                tag = TAGS_EDITAVEIS[escolha]
            except (ValueError, KeyError):
                print("Opcao invalida")
                continue

            novo_valor = input(f"Novo valor para {tag}: ")
            editar_tags(audio, tag, novo_valor)
            print("Tag editada com sucesso")

        print("Edicao do arquivo completa")

if __name__ == "__main__":
    main()