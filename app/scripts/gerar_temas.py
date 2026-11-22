"""
Gera os temas da interface nova (CSS e TypeScript) a partir de TEMAS em tagger/gui/tema.py.

    python app/scripts/gerar_temas.py             grava app/src/temas.css e app/src/temas.ts
    python app/scripts/gerar_temas.py --verificar  só confere se os arquivos commitados estão em dia

O Python continua sendo a fonte da verdade (nomes e valores iguais aos da v2): ninguém edita os
arquivos gerados à mão. O tema.py é lido como árvore sintática, sem importar (não precisa de Qt).
"""

import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
ORIGEM = RAIZ / "tagger" / "gui" / "tema.py"
DESTINO_CSS = RAIZ / "app" / "src" / "temas.css"
DESTINO_TS = RAIZ / "app" / "src" / "temas.ts"
# chave do TEMAS -> nome da variável CSS (o acento vira --acento; nome e escuro não são cores)
CORES = ("bg", "surface", "surface2", "field", "line", "line2", "text", "muted", "faint", "hover", "erro", "acento")
CABECALHO = "Gerado por app/scripts/gerar_temas.py a partir de tagger/gui/tema.py. Não edite à mão."


def ler_temas(origem=ORIGEM):
    """O dicionário TEMAS do tema.py, sem executar o módulo."""
    for no in ast.parse(origem.read_text(encoding="utf-8")).body:
        if isinstance(no, ast.Assign) and any(getattr(t, "id", None) == "TEMAS" for t in no.targets):
            return ast.literal_eval(no.value)
    raise SystemExit("TEMAS não encontrado em tema.py")


def gerar_css(temas):
    blocos = [f"/* {CABECALHO} */\n"]
    for id_tema, tema in temas.items():
        linhas = "".join(f"  --{cor}: {tema[cor]};\n" for cor in CORES)
        blocos.append(f'[data-tema="{id_tema}"] {{\n  color-scheme: {"dark" if tema["escuro"] else "light"};\n{linhas}}}\n')
    return "\n".join(blocos)


def gerar_ts(temas):
    itens = []
    for id_tema, tema in temas.items():
        cores = {cor: tema[cor] for cor in CORES}
        itens.append(f'  {json.dumps(id_tema)}: {{ nome: {json.dumps(tema["nome"], ensure_ascii=False)}, '
                     f'escuro: {json.dumps(tema["escuro"])}, cores: {json.dumps(cores)} }},')
    return (f"// {CABECALHO}\n\n"
            "export interface Tema {\n  nome: string;\n  escuro: boolean;\n  cores: Record<string, string>;\n}\n\n"
            "export const TEMAS: Record<string, Tema> = {\n" + "\n".join(itens) + "\n};\n\n"
            f"export const TEMA_PADRAO = {json.dumps(next(iter(temas)))};\n")


def main(argv):
    temas = ler_temas()
    gerados = {DESTINO_CSS: gerar_css(temas), DESTINO_TS: gerar_ts(temas)}
    if "--verificar" in argv:
        defasados = [c.name for c, t in gerados.items() if not c.exists() or c.read_text(encoding="utf-8") != t]
        if defasados:
            print("Fora de dia com tema.py: " + ", ".join(defasados) + " (rode gerar_temas.py)")
            return 1
        print(f"{len(temas)} temas em dia.")
        return 0
    for caminho, texto in gerados.items():
        caminho.write_text(texto, encoding="utf-8", newline="\n")
    print(f"{len(temas)} temas gerados.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
