from pathlib import Path
from metadata import ler_tags, abrir_arquivo, editar_tags, bulk_edit, TAGS_EDITAVEIS, TAGS_BULK
from interface import selecionar_arquivo

def mostrar_tags(tags):
    print("\nTags disponíveis:")

    for numero, valor in tags.items():
        tag = TAGS_EDITAVEIS[numero]
        print(f"{numero} - {tag}: {valor}")

    print("0 - Finalizar edição deste arquivo")


def escolher_tag():
    while True:
        escolha = input("\nQual tag deseja editar? ")

        if escolha == "0":
            return None

        try:
            return TAGS_EDITAVEIS[int(escolha)]
        except (ValueError, KeyError):
            print("Opção inválida.")


def editar_arquivo(arquivo):
    print(f"\nArquivo: {arquivo}")

    audio = abrir_arquivo(arquivo)

    if audio is None:
        print("Formato não suportado.")
        return False

    while True:
        mostrar_tags(ler_tags(audio))

        tag = escolher_tag()
        if tag is None:
            break

        novo_valor = input(f"Novo valor para {tag}: ")
        editar_tags(audio, tag, novo_valor)
        print("Tag editada com sucesso.")

    print("Edição do arquivo finalizada.")
    return True


def mostrar_arquivos(arquivos, editados):
    print("\nArquivos selecionados:")

    for numero, arquivo in enumerate(arquivos, start=1):
        nome = Path(arquivo).name
        marcador = " [editado]" if arquivo in editados else ""
        print(f"{numero} - {nome}{marcador}")

    print("0 - Voltar ao menu")


def escolher_arquivo(arquivos):
    while True:
        escolha = input("\nQual arquivo deseja editar? ")

        if escolha == "0":
            return None

        try:
            numero = int(escolha)
            if numero < 1:
                raise IndexError
            return arquivos[numero - 1]
        except (ValueError, IndexError):
            print("Opção inválida.")


def modo_individual():
    arquivos = selecionar_arquivo()

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        return

    editados = set()

    while True:
        mostrar_arquivos(arquivos, editados)

        arquivo = escolher_arquivo(arquivos)
        if arquivo is None:
            break

        if editar_arquivo(arquivo):
            editados.add(arquivo)

def mostrar_bulk_tags():
    pass

def selecionar_bulk_tags():
    pass

def modo_bulk():
    arquivos = selecionar_arquivo()
    
    if not arquivos:
        print("Nenhum arquivo selecionado")
        return
    
    editados = set()
    
    while True:
        mostrar_arquivos(arquivos, editados)

        arquivo = escolher_arquivo(arquivos)
        if arquivo is None:
            break
    
    #TODO 
    # 1. selecionar arquivos
    # 2. escolher uma tag permitida pro bulk
    # 3. pedir o novo valor
    # 4. confirmar (S/N)
    # 5. chamar bulk_edit(arquivos, tag, valor)
    
    print("\nBulk edit ainda não implementado.")


def mostrar_menu():
    print("\n=== Tagger ===")
    print("1 - Edição individual")
    print("2 - Bulk edit")
    print("0 - Sair")


def main():
    while True:
        mostrar_menu()
        escolha = input("\nEscolha uma opção: ")

        if escolha == "1":
            modo_individual()
        elif escolha == "2":
            modo_bulk()
        elif escolha == "0":
            break
        else:
            print("Opção inválida.")

    print("\nPrograma finalizado.")


if __name__ == "__main__":
    main()