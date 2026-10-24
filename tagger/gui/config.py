"""Configurações do usuário (salvas pelo QSettings entre uma sessão e outra)."""

PADROES = {
    # aparência
    "usar_escuro": True,
    "tema_escuro": "grafite",
    "tema_claro": "claro",
    "acento": "tema",       # "tema" = usa a cor de destaque do próprio tema
    "fonte": "",            # "" = automática
    "fonte_mono": "",       # "" = automática
    "tamanho_fonte": 13,    # px
    "densidade": "compacta",
    # comportamento
    "subpastas": True,
    "reabrir_ultima": False,
    "numerar_com_total": True,
    "agrupar_por_album": False,  # desligado: a lista continua na ordem de carga, como sempre foi
    # tags
    "versao_id3": 3,             # só MP3 (FLAC/Ogg/M4A não usam ID3)
    "multivalor": True,          # "A; B" vira vários valores ao salvar (artista, gênero...), em todos os formatos
    "remover_id3v1": False,      # só MP3
    "otimizar_capa": True,       # capas grandes viram JPEG de no máximo lado_max_capa px
    "lado_max_capa": 1000,
    # serviços online: credenciais próprias, opcionais ("" = usa a chave do Tagger); texto puro no QSettings
    "lastfm_api_key": "",
    "discogs_token": "",
    # padrões (renomear pelas tags / tags pelo nome)
    "padrao_renomear": "{tracknumber:02} - {artist} - {title}",
    "padrao_tags": "%artist% - %title%",
    "padrao_organizar": "{albumartist}/{album}/{tracknumber:02} - {title}",
    "recentes_renomear": [],
    "recentes_organizar": [],
    "recentes_tags": [],
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