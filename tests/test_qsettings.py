"""Isolamento do QSettings nos testes: nada pode ir para o registro/arquivo real do usuário."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_qsettings_dos_testes_fica_num_ini_temporario(qsettings_isolado):
    from PySide6.QtCore import QSettings
    from tagger.gui import erros, janela

    for modulo in (janela, erros):
        settings = modulo.QSettings("Tagger", "Tagger")
        assert settings.format() == QSettings.IniFormat
        assert Path(settings.fileName()).parent == qsettings_isolado
    assert erros.credenciais_das_configuracoes() == ()          # lê do INI temporário, não do registro real
