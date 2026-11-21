"""Aviso de nova versão na janela (offscreen, sem rede): consulta em segundo plano que nunca trava o fechamento."""

import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from tagger.gui import janela as modulo_janela  # noqa: E402
from tagger.nucleo import atualizacao  # noqa: E402


@pytest.fixture
def janela(qtbot, tmp_path, monkeypatch):
    """JanelaPrincipal real com QSettings num .ini temporário (nunca as configurações do usuário)."""
    ini = str(tmp_path / "config" / "tagger.ini")
    monkeypatch.setattr(modulo_janela, "QSettings", lambda *_a: QSettings(ini, QSettings.IniFormat))
    j = modulo_janela.JanelaPrincipal()
    j.show()
    yield j
    j.close()


def test_fechar_com_consulta_pendente_nao_espera_nem_quebra(qtbot, janela, monkeypatch):
    soltar, comecou = threading.Event(), threading.Event()

    def consulta_lenta(*_a, **_k):
        comecou.set()
        soltar.wait(30)                    # como uma rede sem resposta
        return ("9.9.9", "https://github.com/morais1dev/Tagger/releases/tag/v9.9.9")

    monkeypatch.setattr(modulo_janela.atualizacao, "consultar", consulta_lenta)
    janela.verificar_atualizacao()
    assert comecou.wait(5) and janela._verificador.is_alive()

    inicio = time.monotonic()
    assert janela.close() is True
    assert time.monotonic() - inicio < 2                   # não esperou a consulta (o TIMEOUT é de 10 s)

    soltar.set()                                           # a consulta termina com a janela já fechada
    janela._verificador.join(5)
    assert not janela._verificador.is_alive()
    perguntas = []
    monkeypatch.setattr(QMessageBox, "exec", lambda caixa: perguntas.append(caixa.text()) or 0)
    qtbot.wait(100)                                        # o sinal chega com a janela fechada: sem diálogo, sem erro
    assert perguntas == []


def test_consulta_so_acontece_uma_vez_por_dia_e_se_ligada(qtbot, janela, monkeypatch):
    chamadas = []
    monkeypatch.setattr(modulo_janela.atualizacao, "consultar", lambda *a, **k: chamadas.append(1))

    janela.config["avisar_nova_versao"] = False
    janela.verificar_atualizacao()
    assert chamadas == [] and getattr(janela, "_verificador", None) is None      # opção desligada

    janela.config["avisar_nova_versao"] = True
    janela.settings.setValue("ultima_verificacao_versao", time.time())           # já consultou hoje
    janela.verificar_atualizacao()
    assert chamadas == []

    janela.settings.setValue("ultima_verificacao_versao", time.time() - atualizacao.INTERVALO - 1)
    janela.verificar_atualizacao()
    janela._verificador.join(5)
    assert chamadas == [1]


def test_versao_nova_mostra_o_aviso_com_link(qtbot, janela, monkeypatch):
    abertos, perguntas = [], []
    link = "https://github.com/morais1dev/Tagger/releases/tag/v9.9.9"
    monkeypatch.setattr(modulo_janela.atualizacao, "consultar", lambda *a, **k: ("9.9.9", link))

    def exec_falso(caixa):
        perguntas.append(caixa.text())
        caixa.buttons()[0].click()                         # "Abrir a página da versão"
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_falso)
    monkeypatch.setattr(modulo_janela.QDesktopServices, "openUrl", lambda url: abertos.append(url.toString()))
    janela.verificar_atualizacao()
    qtbot.waitUntil(lambda: bool(perguntas), timeout=5000)      # o resultado volta pela thread da interface
    assert "9.9.9" in perguntas[0]
    assert abertos == [link]


def test_falha_na_consulta_nao_mostra_nada(qtbot, janela, monkeypatch):
    perguntas = []
    monkeypatch.setattr(modulo_janela.atualizacao, "consultar", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "exec", lambda caixa: perguntas.append(caixa.text()) or 0)
    janela.verificar_atualizacao()
    janela._verificador.join(5)
    qtbot.wait(50)
    assert perguntas == []
