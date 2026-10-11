#!/usr/bin/env python3
"""Corta a gravação do modo automático (gravar_auto.cjs) em um clipe por jogo.

Lê gameplay/celular.{mp4,webm} + celular.json e gameplay/pc.* + pc.json e gera:
  gameplay/auto/<jogo>_cel.mp4      (9:16, para o celular)
  gameplay/auto/<jogo>_desktop.mp4  (16:9, para o PC)
  gameplay/auto.json                (lista de jogos, usada pelo gerar_videos.py)

Os arquivos brutos são grandes demais para o git; os clipes são comprimidos.

Uso:
    python3 promo/kavix/cortar_auto.py
"""
import json
import os
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
GP = os.path.join(HERE, "gameplay")
OUT = os.path.join(GP, "auto")
SKIP = 0.8  # pula a transição entre um jogo e outro


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def source(kind):
    for ext in (".mp4", ".webm"):
        p = os.path.join(GP, kind + ext)
        if os.path.exists(p) and os.path.exists(os.path.join(GP, kind + ".json")):
            return p
    return None


def segments(kind):
    path = source(kind)
    with open(os.path.join(GP, kind + ".json")) as fh:
        data = json.load(fh)
    real = float(data.get("duracao_real", 0))
    k = duration(path) / real if real else 1.0  # gravação esticada (Playwright)
    return path, [(x["nome"], x["inicio"] * k, x["fim"] * k) for x in data["segmentos"]]


def cut(src, a, b, vf, out):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{a + SKIP:.2f}",
                    "-to", f"{b:.2f}", "-i", src, "-vf", vf + ",fps=30", "-an",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "25",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)


def main():
    if not (source("celular") and source("pc")):
        sys.exit("faltam gameplay/celular.* e pc.* com os .json (rode o gravar_auto.cjs)")
    os.makedirs(OUT, exist_ok=True)
    cel_src, cel = segments("celular")
    pc_src, pc = segments("pc")
    jobs, manifest = [], []
    for i, (nome, a, b) in enumerate(cel):
        s = slug(nome) or f"jogo_{i + 1}"
        c = f"auto/{s}_cel.mp4"
        d = f"auto/{s}_desktop.mp4"
        jobs.append((cel_src, a, b, "scale=1080:1920", os.path.join(GP, c)))
        if i < len(pc):
            jobs.append((pc_src, pc[i][1], pc[i][2], "scale=1280:720", os.path.join(GP, d)))
        manifest.append({"nome": nome, "celular": c, "pc": d})
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        list(ex.map(lambda j: cut(*j), jobs))
    with open(os.path.join(GP, "auto.json"), "w") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"{len(manifest)} jogos cortados em {OUT}")


if __name__ == "__main__":
    main()
