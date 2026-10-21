"""Diálogo "Limpar tags extras": mostra o que existe nos arquivos e deixa escolher o que remover."""

from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

# Frames comuns que o Tagger não mostra, com um nome que dá para entender.
NOMES_FRAMES = {
    "PRIV": "dados privados de programas (Windows Media, Amazon...)",
    "TXXX": "campos personalizados (inclui ReplayGain, MusicBrainz IDs...)",
    "WXXX": "links",
    "GEOB": "objetos embutidos",
    "POPM": "avaliação (estrelas)",
    "PCNT": "contagem de execuções",
    "TENC": "codificado por",
    "TSSE": "programa/configuração do encoder",
    "TLEN": "duração gravada na tag",
    "TCOP": "copyright",
    "TPUB": "gravadora",
    "TBPM": "BPM",
    "TKEY": "tom",
    "TSRC": "ISRC",
    "TMED": "mídia de origem",
    "TSOP": "artista para ordenação",
    "TSOA": "álbum para ordenação",
    "TSOT": "título para ordenação",
    "TSO2": "artista do álbum para ordenação",
    "TCMP": "compilação (iTunes)",
    "RVA2": "ajuste de volume",
    "MCDI": "identificador do CD",
    "UFID": "identificador único (MusicBrainz...)",
}


def _rotulo(texto, papel):
    lbl = QLabel(texto)
    lbl.setProperty("papel", papel)
    lbl.setWordWrap(True)
    return lbl


class DialogoLimpeza(QDialog):
    def __init__(self, analises, parent=None):
        """analises: lista de metadata.analisar_extras(), um por arquivo selecionado."""
        super().__init__(parent)
        self.setWindowTitle("Limpar tags extras")
        self.setMinimumWidth(560)

        n = len(analises)
        com_v1 = sum(a["id3v1"] for a in analises)
        com_desconhecidos = sum(1 for a in analises if a["desconhecidos"])
        extras = {}
        for analise in analises:
            for frame_id, quantidade in analise["extras"].items():
                extras[frame_id] = extras.get(frame_id, 0) + quantidade
        com_extras = sum(1 for a in analises if a["extras"])

        self.ck_id3v1 = QCheckBox(f"Remover a tag ID3v1 antiga — {com_v1} de {n} arquivo(s)")
        self.ck_id3v1.setChecked(bool(com_v1))
        self.ck_id3v1.setEnabled(bool(com_v1))
        self.ck_desconhecidos = QCheckBox(
            f"Remover frames não reconhecidos (corrompidos ou de formato desconhecido) — {com_desconhecidos} arquivo(s)")
        self.ck_desconhecidos.setChecked(bool(com_desconhecidos))
        self.ck_desconhecidos.setEnabled(bool(com_desconhecidos))
        self.ck_extras = QCheckBox(f"Remover tudo o que o Tagger não mostra — {com_extras} arquivo(s)")
        self.ck_extras.setEnabled(bool(extras))

        lista = "\n".join(f"•  {frame_id} ×{quantidade}  —  {NOMES_FRAMES.get(frame_id, 'outro')}"
                          for frame_id, quantidade in sorted(extras.items(), key=lambda i: -i[1]))
        detalhes = _rotulo(lista or "Nenhum frame extra encontrado.", "ajuda")
        detalhes.setContentsMargins(26, 0, 0, 0)

        for ck in (self.ck_id3v1, self.ck_desconhecidos, self.ck_extras):
            ck.toggled.connect(self._atualizar)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Limpar")
        self.btn_ok.setProperty("tipo", "primario")
        self.btn_ok.clicked.connect(self.accept)
        rodape = QHBoxLayout()
        rodape.addStretch()
        rodape.addWidget(btn_cancelar)
        rodape.addWidget(self.btn_ok)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 16)
        v.setSpacing(10)
        v.addWidget(_rotulo(f"{n} arquivo(s) selecionado(s). A limpeza é gravada na hora e "
                            "não pode ser desfeita.", "ajuda"))
        v.addWidget(self.ck_id3v1)
        v.addWidget(self.ck_desconhecidos)
        v.addWidget(self.ck_extras)
        v.addWidget(detalhes)
        v.addWidget(_rotulo("Título, artista, capa e todos os campos do editor são sempre mantidos.", "ajuda"))
        v.addLayout(rodape)
        self._atualizar()

    def _atualizar(self):
        self.btn_ok.setEnabled(any(ck.isChecked() for ck in (self.ck_id3v1, self.ck_desconhecidos, self.ck_extras)))

    def opcoes(self):
        return {"id3v1": self.ck_id3v1.isChecked(), "desconhecidos": self.ck_desconhecidos.isChecked(),
                "extras": self.ck_extras.isChecked()}
