"""
Gera tagger/nucleo/chaves.json a partir das variáveis de ambiente (Secrets do GitHub Actions).

    LASTFM_API_KEY=... DISCOGS_KEY=... DISCOGS_SECRET=... python scripts/gerar_chaves.py

Variável vazia vira aviso do Actions (::warning::), sem falhar o build: o serviço só fica
desativado no .exe. Os valores nunca são impressos.
"""

import json
import os
import sys
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "tagger" / "nucleo" / "chaves.json"
# chave no chaves.json -> (variável de ambiente, o que fica sem ela)
CHAVES = {
    "lastfm_api_key": ("LASTFM_API_KEY", "a busca no Last.fm"),
    "discogs_key": ("DISCOGS_KEY", "a busca no Discogs (sem token do usuário)"),
    "discogs_secret": ("DISCOGS_SECRET", "a busca no Discogs (sem token do usuário)"),
}


def gerar(destino=None, ambiente=None):
    """Grava o chaves.json e devolve a lista de avisos (um por variável vazia)."""
    ambiente = os.environ if ambiente is None else ambiente
    dados, avisos = {}, []
    for chave, (variavel, servico) in CHAVES.items():
        dados[chave] = (ambiente.get(variavel) or "").strip()
        if not dados[chave]:
            avisos.append(f"::warning::Sem {variavel}: {servico} vai ficar desativada no .exe")
    destino = Path(destino or DESTINO)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados), encoding="utf-8")
    return avisos


def main():
    for aviso in gerar():
        print(aviso)
    print("chaves.json gerado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
