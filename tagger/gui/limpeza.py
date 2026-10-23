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

# O mesmo para FLAC/Ogg (Vorbis comments, sempre em maiúsculas aqui) e M4A (átomos do iTunes).
# Átomos técnicos do M4A (gapless, iTunNORM, cpil, tmpo...) não aparecem: a limpeza não os remove
# (ver nucleo/formatos/mp4.TECNICOS).
NOMES_VORBIS = {
    "ENCODER": "programa/configuração do encoder",
    "ENCODEDBY": "codificado por",
    "ENCODED-BY": "codificado por",
    "ENCODING": "configuração do encoder",
    "COPYRIGHT": "copyright",
    "LABEL": "gravadora",
    "ORGANIZATION": "gravadora",
    "PUBLISHER": "gravadora",
    "BPM": "BPM",
    "KEY": "tom",
    "INITIALKEY": "tom",
    "ISRC": "ISRC",
    "BARCODE": "código de barras",
    "CATALOGNUMBER": "número de catálogo",
    "MEDIA": "mídia de origem",
    "SOURCEMEDIA": "mídia de origem",
    "LENGTH": "duração gravada na tag",
    "COMPILATION": "compilação",
    "RATING": "avaliação (estrelas)",
    "MOOD": "humor",
    "GROUPING": "agrupamento",
    "ARTISTSORT": "artista para ordenação",
    "ALBUMSORT": "álbum para ordenação",
    "TITLESORT": "título para ordenação",
    "ALBUMARTISTSORT": "artista do álbum para ordenação",
    "COMPOSERSORT": "compositor para ordenação",
    "ORIGINALDATE": "data original de lançamento",
    "ORIGINALYEAR": "ano original de lançamento",
    "RELEASECOUNTRY": "país de lançamento",
    "RELEASESTATUS": "situação do lançamento (MusicBrainz)",
    "RELEASETYPE": "tipo de lançamento (MusicBrainz)",
    "SCRIPT": "escrita (MusicBrainz)",
    "WWW": "links",
    "DISCID": "identificador do CD",
    "CDDB": "identificador do CD",
}

NOMES_MP4 = {
    "\xa9too": "programa/configuração do encoder",
    "\xa9enc": "codificado por",
    "\xa9grp": "agrupamento",
    "cprt": "copyright",
    "desc": "descrição",
    "ldes": "descrição longa",
    "soar": "artista para ordenação",
    "soal": "álbum para ordenação",
    "sonm": "título para ordenação",
    "soaa": "artista do álbum para ordenação",
    "soco": "compositor para ordenação",
    "purd": "data de compra (iTunes)",
    "apID": "conta da loja (iTunes)",
    "ownr": "dono (iTunes)",
    "xid ": "identificador da loja (iTunes)",
    "plID": "identificador da loja (iTunes)",
    "cnID": "identificador da loja (iTunes)",
    "geID": "identificador da loja (iTunes)",
    "atID": "identificador da loja (iTunes)",
    "sfID": "identificador da loja (iTunes)",
    "cmID": "identificador da loja (iTunes)",
    "akID": "identificador da loja (iTunes)",
    "iTunes_CDDB_IDs": "identificador do CD",
}

# Famílias de chaves com prefixo comum (em maiúsculas).
PREFIXOS = {
    "REPLAYGAIN_": "ajuste de volume (ReplayGain)",
    "MUSICBRAINZ_": "identificadores do MusicBrainz",
    "MUSICBRAINZ ": "identificadores do MusicBrainz",
    "ACOUSTID_": "identificadores do AcoustID",
    "ACOUSTID ": "identificadores do AcoustID",
    "DISCOGS_": "dados do Discogs",
}

# Campos livres do M4A ("----:com.apple.iTunes:NOME"): mostrados só pelo NOME.
_PREFIXO_LIVRE_MP4 = "----:"


def nome_extra(chave):
    """(chave curta para mostrar, descrição) de um frame ID3, chave Vorbis ou átomo MP4 extra."""
    curta = chave
    if chave.startswith(_PREFIXO_LIVRE_MP4):
        curta = chave.rsplit(":", 1)[-1]
    descricao = (NOMES_FRAMES.get(curta) or NOMES_MP4.get(curta) or NOMES_VORBIS.get(curta.upper())
                 or next((d for prefixo, d in PREFIXOS.items() if curta.upper().startswith(prefixo)), None))
    return curta, descricao or "outro"


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

        self.ck_id3v1 = QCheckBox(f"Remover a tag ID3v1 antiga (só MP3) — {com_v1} de {n} arquivo(s)")
        self.ck_id3v1.setChecked(bool(com_v1))
        self.ck_id3v1.setEnabled(bool(com_v1))
        self.ck_desconhecidos = QCheckBox(
            "Remover frames ID3 não reconhecidos (só MP3; corrompidos ou de formato desconhecido) — "
            f"{com_desconhecidos} arquivo(s)")
        self.ck_desconhecidos.setChecked(bool(com_desconhecidos))
        self.ck_desconhecidos.setEnabled(bool(com_desconhecidos))
        self.ck_extras = QCheckBox(f"Remover tudo o que o Tagger não mostra — {com_extras} arquivo(s)")
        self.ck_extras.setEnabled(bool(extras))

        linhas = []
        for chave, quantidade in sorted(extras.items(), key=lambda i: -i[1]):
            curta, descricao = nome_extra(chave)
            linhas.append(f"•  {curta} ×{quantidade}  —  {descricao}")
        lista = "\n".join(linhas)
        detalhes = _rotulo(lista or "Nenhuma tag extra encontrada.", "ajuda")
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
        v.addWidget(_rotulo("Título, artista, capa e todos os campos do editor são sempre mantidos. "
                            "Em FLAC, Ogg e M4A só a última opção se aplica (ID3v1 e frames ID3 são coisa do MP3).",
                            "ajuda"))
        v.addLayout(rodape)
        self._atualizar()

    def _atualizar(self):
        self.btn_ok.setEnabled(any(ck.isChecked() for ck in (self.ck_id3v1, self.ck_desconhecidos, self.ck_extras)))

    def opcoes(self):
        return {"id3v1": self.ck_id3v1.isChecked(), "desconhecidos": self.ck_desconhecidos.isChecked(),
                "extras": self.ck_extras.isChecked()}
