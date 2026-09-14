import tkinter as tk
from tkinter import filedialog

def selecionar_arquivo():
    root = tk.Tk()
    root.withdraw()

    arquivos = filedialog.askopenfilenames(
        title="Selecione os arquivos",
        filetypes=[
            ("Arquivos MP3", "*.mp3")
        ]
    )
    root.destroy()
    return arquivos