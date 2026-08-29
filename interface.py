import tkinter as tk
from tkinter import filedialog


def selecionar_arquivo():
    arquivo = filedialog.askopenfilename()
    return arquivo