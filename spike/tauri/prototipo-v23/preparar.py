"""Copia a lofty 0.25.5 do cache do cargo para ../vendor e aplica lofty-tcon-v23.patch.

Precisa de um `cargo fetch` antes (em ../nucleo). Usa `git apply` (sem rede)."""

import shutil
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DESTINO = AQUI.parent / "vendor" / "lofty-0.25.5"
registros = sorted((Path.home() / ".cargo" / "registry" / "src").glob("*/lofty-0.25.5"))
if not registros:
    raise SystemExit("lofty 0.25.5 não está no cache do cargo: rode `cargo fetch` em spike/tauri/nucleo")
if DESTINO.exists():               # esvazia sem apagar a pasta (no Windows ela pode estar aberta)
    for item in DESTINO.iterdir():
        shutil.rmtree(item) if item.is_dir() else item.unlink()
shutil.copytree(registros[0], DESTINO, dirs_exist_ok=True)
subprocess.run(["git", "apply", "--directory=spike/tauri/vendor/lofty-0.25.5", "--unsafe-paths",
                str(AQUI / "lofty-tcon-v23.patch")], check=True, cwd=AQUI.parents[2])
print(f"lofty corrigida em {DESTINO}")
