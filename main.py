from metadata import ler_tags, abrir_arquivo, editar_tags, TAGS_EDITAVEIS
from interface import selecionar_arquivo


def editar_arquivo(arquivo):
    print(f"\nArquivo: {arquivo}")

    audio = abrir_arquivo(arquivo)

    if audio is None:
        print("Formato não suportado.")
        return False

    while True:
        tags = ler_tags(audio)

        print("\nTags disponíveis:")

        for numero, valor in tags.items():
            tag = TAGS_EDITAVEIS[numero]
            print(f"{numero} - {tag}: {valor}")

        print("0 - Finalizar edição deste arquivo")

        escolha = input("\nQual tag deseja editar? ")

        if escolha == "0":
            break

        try:
            escolha = int(escolha)
            tag = TAGS_EDITAVEIS[escolha]
        except (ValueError, KeyError):
            print("Opção inválida.")
            continue

        novo_valor = input(f"Novo valor para {tag}: ")

        editar_tags(audio, tag, novo_valor)

        print("Tag editada com sucesso.")

    print("Edição do arquivo finalizada.")
    return True


def main():
    arquivos = selecionar_arquivo()

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        return

    editados = set()

    while True:
        print("\nArquivos selecionados:")

        for numero, arquivo in enumerate(arquivos, start=1):
            nome = arquivo.split("/")[-1]

            if arquivo in editados:
                print(f"{numero} - {nome} [editado]")
            else:
                print(f"{numero} - {nome}")

        print("0 - Finalizar programa")

        escolha = input("\nQual arquivo deseja editar? ")

        if escolha == "0":
            break

        try:
            escolha = int(escolha)
            arquivo = arquivos[escolha - 1]
        except (ValueError, IndexError):
            print("Opção inválida.")
            continue

        if editar_arquivo(arquivo):
            editados.add(arquivo)

    print("\nPrograma finalizado.")


if __name__ == "__main__":
    main()
