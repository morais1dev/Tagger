import os, subprocess
from pathlib import Path
from metadata import ler_tags, abrir_arquivo, editar_tags, bulk_edit, TAGS_EDITAVEIS, tags_bulk, validar_valor
from interface import selecionar_arquivo


def limpar_tela():
    comando = 'cls' if os.name == 'nt' else 'clear'
    subprocess.run(comando, shell = True)
    


def mostrar_tags(tags):
    limpar_tela()
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
    audio = abrir_arquivo(arquivo)

    if audio is None:
        print("Formato não suportado.")
        input("\nPressione Enter para continuar...")
        return False

    teve_alteracao = False

    while True:
        mostrar_tags(ler_tags(audio))
        print(f"\nArquivo atual: {Path(arquivo).name}")

        tag = escolher_tag()
        if tag is None:
            break

        while True:
            novo_valor_input = input(f"Novo valor para {tag} (ou 'atual' para ano): ").strip()
            valido, resultado = validar_valor(tag, novo_valor_input)
            
            if not valido:
                print(resultado)
                continue
                
            novo_valor = resultado
            break

        editar_tags(audio, tag, novo_valor)
        print("Tag editada com sucesso.")
        teve_alteracao = True
        input("\nPressione Enter para continuar...")

    print("Edição do arquivo finalizada.")
    return teve_alteracao


def mostrar_arquivos(arquivos, editados):
    limpar_tela()
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
        input("\nPressione Enter para continuar...")
        return

    editados = set()

    while True:
        mostrar_arquivos(arquivos, editados)

        arquivo = escolher_arquivo(arquivos)
        if arquivo is None:
            break

        if editar_arquivo(arquivo):
            editados.add(arquivo)


def mostrar_bulk_arquivos(arquivos):
    limpar_tela()
    print(f"\nQuantidade de arquivos selecionados: {len(arquivos)}")
    for numero, arquivo in enumerate(arquivos, start=1):
        nome = Path(arquivo).name
        print(f"{numero} - {nome}")


def mostrar_bulk_tags():
    print("\nTags disponiveis: ")
    for num, tag in enumerate(tags_bulk(), start=1):
        print(f"{num} - {tag}")
    print("0 - Cancelar")


def selecionar_bulk_tags():
    tags = tags_bulk()
    while True:
        escolha = input("\nQual tag deseja editar em todos os arquivos? ")
        if escolha == "0":
            return None
        try:
            numero = int(escolha)
            if numero < 1:
                raise IndexError
            return tags[numero - 1]
        except (ValueError, IndexError):
            print("Opção inválida.")


def modo_bulk():
    arquivos = selecionar_arquivo()

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        input("\nPressione Enter para continuar...")
        return

    mostrar_bulk_arquivos(arquivos)

    mostrar_bulk_tags()
    tag = selecionar_bulk_tags()

    if tag is None:
        print("Operação cancelada.")
        input("\nPressione Enter para continuar...")
        return
    
    print(f"Tag escolhida: {tag}")

    while True:
        valor_input = input(f"Insira o novo valor para a tag {tag} (ou 'atual' para ano): ").strip()
        valido, resultado = validar_valor(tag, valor_input)
        
        if not valido:
            print(resultado)
            continue
            
        valor = resultado
        break

    while True:
        confirmacao = input(f"Confirmar alteração da tag '{tag}' para '{valor}' em {len(arquivos)} arquivo(s)? (S/N): ").strip().upper()
        
        if confirmacao in ['S', 'N']:
            break 
            
        print("Entrada inválida! Digite 'S' para confirmar ou 'N' para cancelar.")

    if confirmacao == 'S':
        print(f"\nAplicando alterações...")
        bulk_edit(arquivos, tag, valor)
        print("Alterações aplicadas com sucesso!")
    else:
        print("\nOperação cancelada pelo usuário.")
        
    input("\nPressione Enter para continuar...")


def mostrar_menu():
    limpar_tela()
    print("\n=== Tagger ===")
    print("1 - Edição individual")
    print("2 - Bulk edit")
    print("0 - Sair")


def main():

    if os.name == "nt":
        subprocess.run('title Tagger v1.0', shell=True)

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
            input("\nPressione Enter para continuar...")

    print("\nPrograma finalizado.")
    input("\nPressione Enter para fechar a aplicação...")

if __name__ == "__main__":
    main()