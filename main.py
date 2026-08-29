from metadata import abrir_arquivo
from interface import selecionar_arquivo


arquivo = selecionar_arquivo()

audio = abrir_arquivo(arquivo)

print(audio)