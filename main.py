import os, subprocess
from pathlib import Path
from metadata import CAMPOS, CAMPOS_BULK, carregar, salvar, salvar_varios, validar_valor, rotulo
from interface import selecionar_arquivo

# Na CLI os campos são escolhidos por número: 1 = primeiro campo de CAMPOS, etc.
LISTA_CAMPOS = list(CAMPOS)


def limpar_tela():
    comando = 'cls' if os.name == 'nt' else 'clear'
    subprocess.run(comando, shell = True)



def mostrar_tags(tags):
    limpar_tela()
    print("\nTags disponíveis:")

    for numero, campo in enumerate(LISTA_CAMPOS, start=1):
        print(f"{numero} - {rotulo(campo)}: {tags.get(campo, '')}")

    print("0 - Finalizar edição deste arquivo")


def escolher_tag():
    while True:
        escolha = input("\nQual tag deseja editar? ")

        if escolha == "0":
            return None

        try:
            numero = int(escolha)
            if numero < 1:
                raise IndexError
            return LISTA_CAMPOS[numero - 1]
        except (ValueError, IndexError):
            print("Opção inválida.")


def pedir_valor(campo):
    """Pede um valor válido. Enter vazio cancela; '-' remove a tag."""
    while True:
        dica = " ('atual' = ano atual)" if campo == "date" else ""
        entrada = input(f"Novo valor para {rotulo(campo)}{dica} (Enter cancela, '-' remove): ").strip()

        if entrada == "":
            return None
        if entrada == "-":
            return ""

        valido, resultado = validar_valor(campo, entrada)
        if valido:
            return resultado
        print(resultado)


def editar_arquivo(arquivo):
    faixa = carregar(arquivo)

    if faixa is None:
        print("Formato não suportado ou arquivo inválido.")
        input("\nPressione Enter para continuar...")
        return False

    teve_alteracao = False

    while True:
        mostrar_tags(faixa.tags)
        print(f"\nArquivo atual: {faixa.nome}")

        campo = escolher_tag()
        if campo is None:
            break

        novo_valor = pedir_valor(campo)
        if novo_valor is None:
            continue

        salvar(arquivo, {campo: novo_valor})
        faixa = carregar(arquivo)
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
    for num, campo in enumerate(CAMPOS_BULK, start=1):
        print(f"{num} - {rotulo(campo)}")
    print("0 - Cancelar")


def selecionar_bulk_tags():
    tags = CAMPOS_BULK
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
    
    print(f"Tag escolhida: {rotulo(tag)}")

    valor = pedir_valor(tag)
    if valor is None:
        print("Operação cancelada.")
        input("\nPressione Enter para continuar...")
        return

    descricao = f"para '{valor}'" if valor else "(remover)"
    while True:
        confirmacao = input(f"Confirmar alteração da tag '{rotulo(tag)}' {descricao} em {len(arquivos)} arquivo(s)? (S/N): ").strip().upper()
        
        if confirmacao in ['S', 'N']:
            break 
            
        print("Entrada inválida! Digite 'S' para confirmar ou 'N' para cancelar.")

    if confirmacao == 'S':
        print(f"\nAplicando alterações...")
        falhas = salvar_varios(arquivos, {tag: valor})
        if falhas:
            print(f"{len(arquivos) - len(falhas)} arquivo(s) alterado(s). Falharam:")
            for caminho, erro in falhas.items():
                print(f"  - {caminho.name}: {erro}")
        else:
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