"""Configurações do usuário (salvas pelo QSettings entre uma sessão e outra)."""

PADROES = {
    # aparência
    "usar_escuro": True,
    "tema_escuro": "grafite",
    "tema_claro": "claro",
    "acento": "#3ddc97",
    "fonte": "",            # "" = automática
    "fonte_mono": "",       # "" = automática
    "tamanho_fonte": 13,    # px
    "densidade": "compacta",
    # comportamento
    "subpastas": True,
    "reabrir_ultima": False,
    "numerar_com_total": True,
    # tags
    "versao_id3": 3,
    "generos": [
        "Alternative", "Ambient", "Axé", "Blues", "Bossa Nova", "Classical", "Country", "Dance",
        "Disco", "Drum & Bass", "Electronic", "Folk", "Forró", "Funk", "Gospel", "Hard Rock",
        "Heavy Metal", "Hip-Hop", "House", "Indie", "Indie Rock", "Jazz", "Lo-Fi", "Metal",
        "MPB", "Pagode", "Pop", "Pop Rock", "Punk", "R&B", "Rap", "Reggae", "Rock", "Samba",
        "Sertanejo", "Soul", "Soundtrack", "Synthpop", "Techno", "Trap",
    ],
}

DENSIDADES = {"compacta": "Compacta", "confortavel": "Confortável", "espacosa": "Espaçosa"}


def carregar_config(settings):
    config = {}
    for chave, padrao in PADROES.items():
        valor = settings.value(f"config/{chave}", padrao)
        try:
            if isinstance(padrao, bool):
                valor = valor if isinstance(valor, bool) else str(valor).lower() in ("true", "1")
            elif isinstance(padrao, int):
                valor = int(valor)
            elif isinstance(padrao, list):
                valor = [valor] if isinstance(valor, str) else list(valor or [])
        except (TypeError, ValueError):
            valor = padrao
        config[chave] = valor
    return config


def salvar_config(settings, config):
    for chave, valor in config.items():
        settings.setValue(f"config/{chave}", valor)
