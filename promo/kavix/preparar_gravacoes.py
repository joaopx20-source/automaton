#!/usr/bin/env python3
"""Prepara gravações de tela do KAVIX ARCADE para o gerar_videos.py.

Recebe gravações do navegador no PC (1920x1080, com o jogo em pé no meio
da tela) e, para cada uma:
  * encontra a área do jogo automaticamente;
  * corta o trecho de jogo ativo (sem a abertura escura nem o "fim de jogo");
  * gera <slug>_celular.mp4 (só o jogo, em pé, para a tela do celular) e
    <slug>_pc.mp4 (a página inteira com a barra de endereço, para o monitor);
  * escreve gameplay/jogos.json, que o gerar_videos.py usa.

Uso:
    python3 promo/kavix/preparar_gravacoes.py "Espinhos=gravacao1.mp4" \
        "Passagem=gravacao2.mp4" ...
"""
import json
import os
import subprocess
import sys
import unicodedata

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "gameplay")
JOGOS = os.path.join(OUT, "jogos")

HEADER = 71       # altura da barra com o nome do jogo, acima da área do jogo
BROWSER_TOP = 44  # abaixo das abas: mantém a barra com kavixbrasil.com.br


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "".join(ch if ch.isalnum() else "_" for ch in s.lower()).strip("_")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    st = d["streams"][0]
    return st["width"], st["height"], float(d["format"]["duration"])


def frame_rgb(path, t, w, h):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", path,
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3)


def game_box(path, w, h, dur):
    """Área do jogo: o retângulo claro no meio da página escura."""
    boxes = []
    for t in (dur * 0.3, dur * 0.5, dur * 0.7):
        a = frame_rgb(path, t, w, h).astype(int).sum(2) > 120
        a[: int(h * 0.14)] = False  # ignora abas/barra do navegador
        rows = np.where(a[:, w // 2 - 50: w // 2 + 50].any(1))[0]
        cols = np.where(a[int(h * 0.45): int(h * 0.8)].mean(0) > 0.5)[0]
        if len(rows) and len(cols):
            boxes.append((cols[0], rows[0], cols[-1], rows[-1]))
    x0, y0, x1, y1 = np.median(np.array(boxes), axis=0).astype(int)
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def active_window(path, box, dur, margin=0.3):
    """Maior trecho sem tela escurecida (abertura, menus, fim de jogo)."""
    x, y, bw, bh = box
    sw, sh = 64, max(2, int(64 * bh / bw))
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf",
                        f"crop={bw}:{bh}:{x}:{y},fps=4,scale={sw}:{sh}",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True, check=True)
    b = np.frombuffer(r.stdout, np.uint8).reshape(-1, sh, sw).mean((1, 2))
    ok = b > 0.75 * np.median(b)
    best, cur = (0, 0), None
    for i, v in enumerate(list(ok) + [False]):
        if v and cur is None:
            cur = i
        elif not v and cur is not None:
            if i - cur > best[1] - best[0]:
                best = (cur, i)
            cur = None
    a, z = best[0] / 4 + margin, min(dur, best[1] / 4) - margin
    return a, z


def encode(src, start, end, vf, out):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start:.2f}",
                    "-to", f"{end:.2f}", "-i", src, "-vf", vf + ",fps=30",
                    "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                   check=True)


def main():
    pairs = [a.split("=", 1) for a in sys.argv[1:]]
    if not pairs or any(len(p) != 2 for p in pairs):
        sys.exit(__doc__)
    os.makedirs(JOGOS, exist_ok=True)
    manifest = []
    for name, src in pairs:
        w, h, dur = probe(src)
        x, y, bw, bh = game_box(src, w, h, dur)
        start, end = active_window(src, (x, y, bw, bh), dur)
        s = slug(name)
        # celular: barra com o nome do jogo + área do jogo (largura par)
        cw = bw - bw % 2
        top = max(0, y - HEADER)
        ch = (y + bh - top) - (y + bh - top) % 2
        encode(src, start, end, f"crop={cw}:{ch}:{x}:{top}",
               os.path.join(JOGOS, f"{s}_celular.mp4"))
        # pc: página inteira com a barra de endereço, reduzida
        ph = h - BROWSER_TOP
        encode(src, start, end,
               f"crop={w}:{ph - ph % 2}:0:{BROWSER_TOP},scale=1280:-2",
               os.path.join(JOGOS, f"{s}_pc.mp4"))
        manifest.append({"nome": name, "celular": f"jogos/{s}_celular.mp4",
                         "pc": f"jogos/{s}_pc.mp4",
                         "duracao": round(end - start, 2),
                         "origem": os.path.basename(src),
                         "trecho": [round(start, 2), round(end, 2)]})
        print(f"{name}: jogo em {bw}x{bh}+{x}+{y}, trecho {start:.1f}s–{end:.1f}s")
    with open(os.path.join(OUT, "jogos.json"), "w") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("ok:", os.path.join(OUT, "jogos.json"))


if __name__ == "__main__":
    main()
