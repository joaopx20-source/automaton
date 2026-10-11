#!/usr/bin/env python3
"""Gera os vídeos promocionais do KAVIX ARCADE (kavixbrasil.com.br).

Estilo "TikTok/Reels": jogabilidade real em tela cheia (2x), legendas que
entram palavra por palavra, etiquetas brancas inclinadas, emojis, barra de
progresso no topo, cortes com zoom e trilha trap sintetizada. As cores da
marca vêm do próprio site (degradê roxo -> ciano do botão "Jogar de novo").

Uso:
    python3 promo/kavix/gerar_videos.py              # gera todos
    python3 promo/kavix/gerar_videos.py arcade       # gera só alguns

Requer: python3, pillow, numpy, ffmpeg e as gravações preparadas pelo
preparar_gravacoes.py (gameplay/jogos.json).
"""
import functools
import json
import math
import os
import subprocess
import sys
import unicodedata
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FPS = 30
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("KAVIX_OUT_DIR") or os.path.join(HERE, "videos")
GAMEPLAY_DIR = os.environ.get("KAVIX_GAMEPLAY_DIR") or os.path.join(HERE, "gameplay")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi")

URL = "kavixbrasil.com.br"
HANDLE = "@kavixarcade"  # perfil no Instagram
LOGO = os.path.join(HERE, "marca", "logo.png")  # foto do perfil
TOTAL_JOGOS = "+20"  # quantidade de jogos do site (não só os gravados)
SPEED = float(os.environ.get("KAVIX_SPEED", "2"))  # jogabilidade em 2x


def _first(*paths):
    return next(p for p in paths if os.path.exists(p))


F_BLACK = _first("/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
                 "/usr/share/fonts/opentype/inter/Inter-Black.otf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
F_BOLD = _first("/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
                "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
F_SEMI = _first("/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf",
                "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
                F_BOLD)
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
# fonte das etiquetas (nomes dos jogos, ranking): Unbounded, licença OFL
F_DISPLAY = _first(os.path.join(HERE, "marca", "fontes", "Unbounded-ExtraBold.woff2"),
                   F_BOLD)

# Cores: marca (site) + destaque jovem
WHITE = (255, 255, 255)
BLACK = (10, 10, 14)
VIOLET = (124, 92, 255)   # botão do site: degradê roxo -> ciano
SKY = (56, 210, 255)
LIME = (198, 255, 61)     # destaque das legendas
ACCENT = [LIME]           # cor de destaque do vídeo atual (muda por vídeo)
INK = (16, 14, 40)


# ---------------------------------------------------------------- utilidades

def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def prog(t, a, b):
    return clamp01((t - a) / (b - a)) if b > a else float(t >= a)


def ease_out_back(x, s=1.9):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def spring(x):
    """Mola: passa um pouco do ponto e assenta."""
    x = clamp01(x)
    return 1 - math.exp(-6 * x) * math.cos(9 * x)


def lerp(a, b, x):
    return a + (b - a) * x


_fonts = {}


def font(size, path=F_BLACK):
    key = (path, max(6, int(size)))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, key[1])
    return _fonts[key]


def composite(base, layer, x, y):
    x, y = int(round(x)), int(round(y))
    lw, lh = layer.size
    bw, bh = base.size
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(lw, bw - x), min(lh, bh - y)
    if ex > sx and ey > sy:
        base.alpha_composite(layer.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def put(base, layer, cx, cy):
    composite(base, layer, cx - layer.width / 2, cy - layer.height / 2)


def set_alpha(layer, alpha):
    if alpha >= 0.999:
        return layer
    a = np.asarray(layer.getchannel("A"), np.float32) * max(0.0, alpha)
    layer = layer.copy()
    layer.putalpha(Image.fromarray(a.astype(np.uint8)))
    return layer


def scaled(layer, s):
    if abs(s - 1) < 0.004:
        return layer
    return layer.resize((max(1, int(layer.width * s)),
                         max(1, int(layer.height * s))), Image.BICUBIC)


def hgradient(w, h, c1, c2):
    t = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    arr = np.zeros((h, w, 4), np.uint8)
    for i in range(3):
        arr[..., i] = (c1[i] + (c2[i] - c1[i]) * t).astype(np.uint8)
    arr[..., 3] = 255
    return Image.fromarray(arr, "RGBA")


def rounded(size, radius, fill, outline=None, width=0, ss=2):
    w, h = size
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1),
                                         radius * ss, fill=fill,
                                         outline=outline, width=width * ss)
    return im.resize((w, h), Image.LANCZOS)


def shadow(size, radius, blur, alpha=150):
    w, h = size
    pad = int(blur * 3)
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), radius,
                                         fill=(0, 0, 0, alpha))
    return im.filter(ImageFilter.GaussianBlur(blur))


# ------------------------------------------------------------- texto/emoji

def is_emoji(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o == 0x2B50


@functools.lru_cache(maxsize=256)
def emoji_layer(ch, size):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    s = size / im.height
    return im.resize((max(1, int(im.width * s)), max(1, int(size))),
                     Image.LANCZOS)


def runs(text):
    """Separa o texto em pedaços de texto comum e emojis (um por pedaço)."""
    out, cur = [], ""
    for ch in text.replace("️", ""):
        if is_emoji(ch):
            if cur:
                out.append((cur, False))
                cur = ""
            out.append((ch, True))
        else:
            cur += ch
    if cur:
        out.append((cur, False))
    return out


@functools.lru_cache(maxsize=2048)
def text_layer(text, size, fill=WHITE, stroke=0, stroke_fill=BLACK,
               path=F_BLACK, shadow_a=0):
    """Texto (com emojis) numa camada RGBA, com contorno e sombra opcionais."""
    size = int(size)
    f = font(size, path)
    asc, desc = f.getmetrics()
    parts = []
    for chunk, emo in runs(text):
        if emo:
            parts.append(emoji_layer(chunk, int(size * 0.92)))
            continue
        w = int(f.getlength(chunk)) + 2 * stroke + 2
        im = Image.new("RGBA", (w, asc + desc + 2 * stroke), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((stroke, stroke), chunk, font=f, fill=fill,
                                stroke_width=stroke, stroke_fill=stroke_fill)
        parts.append(im)
    gap = int(size * 0.06)
    W = sum(p.width for p in parts) + gap * (len(parts) - 1)
    H = max([asc + desc + 2 * stroke] + [p.height for p in parts])
    pad = int(size * 0.25) if shadow_a else 2
    out = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    x = pad
    for p in parts:
        out.alpha_composite(p, (x, pad + (H - p.height) // 2))
        x += p.width + gap
    if shadow_a:
        a = out.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.08))
        sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * shadow_a / 255)))
        base = Image.new("RGBA", out.size, (0, 0, 0, 0))
        base.alpha_composite(sh, (0, int(size * 0.06)))
        base.alpha_composite(out)
        out = base
    return out


@functools.lru_cache(maxsize=512)
def sticker(text, size, bg=WHITE, fg=BLACK, path=F_BOLD):
    """Etiqueta no estilo do 'texto com fundo' do TikTok."""
    tl = text_layer(text, size, fill=fg, path=path)
    w, h = int(tl.width + size * 0.9), int(tl.height + size * 0.45)
    if bg == "brand":
        box = hgradient(w, h, VIOLET, SKY)
        box.putalpha(rounded((w, h), int(h * 0.3), WHITE).getchannel("A"))
    else:
        box = rounded((w, h), int(h * 0.3), bg + (255,))
    box.alpha_composite(tl, ((w - tl.width) // 2, (h - tl.height) // 2))
    sh = shadow(box.size, int(h * 0.3), size * 0.18, 110)
    pad = (sh.width - w) // 2
    sh.alpha_composite(box, (pad, pad - int(size * 0.08)))
    return sh


def draw_sticker(img, text, cx, cy, size, t, rot=-3.0, bg=WHITE, fg=BLACK,
                 alpha=1.0, max_w=None, path=F_BOLD):
    """Etiqueta que entra com mola e fica levemente inclinada."""
    if t < 0 or alpha <= 0:
        return
    if path == F_DISPLAY and F_DISPLAY != F_BOLD:
        size *= 0.8  # a Unbounded é bem mais larga
    lay = sticker(text, int(size), bg, fg, path)
    if max_w and lay.width > max_w:
        lay = scaled(lay, max_w / lay.width)
    s = lerp(0.3, 1.0, spring(t / 0.45))
    lay = lay.rotate(rot * (1 + 2 * (1 - clamp01(t / 0.3))), expand=True,
                     resample=Image.BICUBIC)
    put(img, set_alpha(scaled(lay, s), alpha * clamp01(t / 0.08)), cx, cy)


def caption(img, text, cx, cy, size, t, max_w, highlight=(), per_word=0.07,
            alpha=1.0):
    """Legenda estilo TikTok: palavra por palavra, contorno preto, destaques
    em verde-limão. `highlight` = índices das palavras destacadas."""
    if t < 0 or alpha <= 0:
        return
    words = text.split()
    stroke = max(3, int(size * 0.11))
    lays = [text_layer(w, int(size), fill=ACCENT[0] if i in highlight else WHITE,
                       stroke=stroke, shadow_a=170)
            for i, w in enumerate(words)]
    pad = int(int(size) * 0.25)  # margem da sombra em volta de cada palavra
    adv = [L.width - 2 * pad for L in lays]
    space = size * 0.24
    lines, cur, cw = [], [], 0
    for i, L in enumerate(lays):
        if cur and cw + space + adv[i] > max_w:
            lines.append(cur)
            cur, cw = [], 0
        cw += (space if cur else 0) + adv[i]
        cur.append(i)
    lines.append(cur)
    lh = size * 1.1
    y0 = cy - lh * (len(lines) - 1) / 2
    for li, line in enumerate(lines):
        total = sum(adv[i] for i in line) + space * (len(line) - 1)
        x = cx - total / 2
        for i in line:
            L = lays[i]
            lt = t - i * per_word
            if lt >= 0:
                s = lerp(0.5, 1.0, ease_out_back(lt / 0.16, 2.6))
                put(img, set_alpha(scaled(L, s), alpha * clamp01(lt / 0.05)),
                    x + adv[i] / 2, y0 + li * lh)
            x += adv[i] + space


# ------------------------------------------------------------------ mascote

@functools.lru_cache(maxsize=16)
def mascot(s=600, c1=(255, 222, 110), c2=(236, 84, 24)):
    """Mascote do KAVIX: bolinha com coroa e olhos de pixel."""
    S = s * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    R, cx, cy = S * 0.33, S / 2, S * 0.58
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    dist = np.sqrt((xx - cx + R * 0.3) ** 2 + (yy - cy + R * 0.35) ** 2) / (R * 1.7)
    dist = np.clip(dist, 0, 1)[..., None]
    rgb = np.array(c1, np.float32) * (1 - dist) + np.array(c2, np.float32) * dist
    body = Image.fromarray(np.dstack([rgb, np.full((S, S, 1), 255,
                                                   np.float32)]).astype(np.uint8))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((cx - R, cy - R, cx + R, cy + R), fill=255)
    im.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(im)
    for sx in (-1, 1):
        ex = cx + sx * R * 0.34
        d.rectangle((ex - R * 0.12, cy - R * 0.3, ex + R * 0.12, cy + R * 0.12),
                    fill=(15, 10, 20))
        hx = ex + sx * R * 0.04
        d.rectangle((hx - R * 0.035, cy - R * 0.22, hx + R * 0.035, cy - R * 0.02),
                    fill=WHITE)
    top = cy - R * 0.86
    d.polygon([(cx - R * 0.42, top), (cx - R * 0.48, top - R * 0.36),
               (cx - R * 0.2, top - R * 0.16), (cx, top - R * 0.46),
               (cx + R * 0.2, top - R * 0.16), (cx + R * 0.48, top - R * 0.36),
               (cx + R * 0.42, top)], fill=(255, 196, 40),
              outline=(255, 238, 150), width=8)
    return im.resize((s, s), Image.LANCZOS)


MASCOT_SKINS = [((255, 222, 110), (236, 84, 24)),   # laranja
                ((160, 255, 180), (20, 160, 80)),   # verde
                ((150, 230, 255), (40, 90, 230)),   # azul
                ((255, 170, 230), (200, 40, 150))]  # rosa


# ---------------------------------------------------------------- gameplay

def clip_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def find_clip(kind):
    """gameplay/<kind>.<ext> (kind = 'celular' ou 'pc'), do gravar_auto.cjs."""
    if not os.path.isdir(GAMEPLAY_DIR):
        return None
    for f in sorted(os.listdir(GAMEPLAY_DIR)):
        base, ext = os.path.splitext(f)
        if base.lower() == kind and ext.lower() in VIDEO_EXT:
            return os.path.join(GAMEPLAY_DIR, f)
    return None


def segments(kind):
    """Trechos de cada modo, do .json gerado pelo gravar_auto.cjs."""
    clip = find_clip(kind)
    if not clip:
        return []
    try:
        with open(os.path.splitext(clip)[0] + ".json") as fh:
            data = json.load(fh)
        # o vídeo gravado sai esticado em relação ao relógio real
        real, dur = float(data.get("duracao_real", 0)), clip_duration(clip)
        k = dur / real if real > 0 and dur > 0 else 1.0
        return [(float(x["inicio"]) * k, float(x["fim"]) * k, x.get("nome") or "")
                for x in data.get("segmentos", [])
                if float(x["fim"]) - float(x["inicio"]) > 1.5]
    except (OSError, ValueError, KeyError, TypeError):
        return []


_library = None


def library():
    """Jogos gravados: [{"nome", "celular": (arquivo, início), "pc": (...)}].

    Junta as duas fontes:
      * modo automático (gravar_auto.cjs): gameplay/auto.json com um clipe
        por jogo (cortar_auto.py) ou, sem ele, gameplay/celular.* + pc.* —
        usado para o CELULAR (9:16 em resolução cheia, com as skins do kit
        sorteado);
      * gravações manuais (preparar_gravacoes.py, gameplay/jogos.json) —
        usadas para o PC quando existem, porque mostram o site de verdade
        no navegador, com a barra de endereço."""
    global _library
    if _library is not None:
        return _library
    manual = {}
    mf = os.path.join(GAMEPLAY_DIR, "jogos.json")
    if os.path.exists(mf):
        with open(mf) as fh:
            for j in json.load(fh):
                cel = os.path.join(GAMEPLAY_DIR, j["celular"])
                pc = os.path.join(GAMEPLAY_DIR, j["pc"])
                if os.path.exists(cel) and os.path.exists(pc):
                    manual[j["nome"].lower()] = dict(nome=j["nome"], celular=(cel, 0.0),
                                                     pc=(pc, 0.0))
    _library = []
    af = os.path.join(GAMEPLAY_DIR, "auto.json")  # clipes do cortar_auto.py
    if os.path.exists(af):
        with open(af) as fh:
            for j in json.load(fh):
                cel = os.path.join(GAMEPLAY_DIR, j["celular"])
                pc = os.path.join(GAMEPLAY_DIR, j["pc"])
                if not os.path.exists(cel):
                    continue
                m = manual.pop(j["nome"].lower(), None)
                _library.append(dict(nome=j["nome"], celular=(cel, 0.0),
                                     pc=m["pc"] if m else (pc if os.path.exists(pc)
                                                           else cel, 0.0)))
    elif find_clip("celular") and find_clip("pc"):
        sc, sp = segments("celular"), segments("pc")

        def st(segs, i):
            if not segs:
                return i * 6.0
            a, b, _ = segs[i % len(segs)]
            return a + min(1.5, (b - a) * 0.15)  # pula a transição
        for i in range(max(len(sc), len(sp), 1)):
            nome = (sc[i][2] if i < len(sc) else "") or f"Jogo {i + 1}"
            m = manual.pop(nome.lower(), None)
            _library.append(dict(nome=nome,
                                 celular=(find_clip("celular"), st(sc, i)),
                                 pc=m["pc"] if m else (find_clip("pc"), st(sp, i))))
    _library += list(manual.values())
    return _library


def total_jogos():
    """Quantos jogos anunciar: os gravados, se forem muitos; senão '+20'."""
    n = len(library())
    return str(n) if n >= 20 else TOTAL_JOGOS


_skins = None


def skins():
    """Skins do inventário exportadas pelo exportar_skins.cjs."""
    global _skins
    if _skins is None:
        _skins = []
        mf = os.path.join(GAMEPLAY_DIR, "skins.json")
        if os.path.exists(mf):
            with open(mf) as fh:
                for it in json.load(fh):
                    if os.path.exists(os.path.join(GAMEPLAY_DIR, it["arquivo"])):
                        _skins.append(it)
    return _skins


RAR_ORDEM = {"comum": 0, "raro": 1, "epico": 2, "lendario": 3}


def pick_skins(n, tipos=("roupa", "chapeu", "aura", "olhos"), min_rar="raro"):
    """Escolhe skins vistosas, variando o tipo, das mais raras para as menos."""
    lst = [x for x in skins() if x["tipo"] in tipos and
           RAR_ORDEM.get(x["raridade"], 0) >= RAR_ORDEM[min_rar]]
    lst.sort(key=lambda x: (-RAR_ORDEM.get(x["raridade"], 0), tipos.index(x["tipo"])))
    out, usados = [], set()
    for x in lst:  # primeiro um de cada tipo, depois o resto
        if x["tipo"] not in usados:
            out.append(x)
            usados.add(x["tipo"])
    out += [x for x in lst if x not in out]
    return out[:n]


@functools.lru_cache(maxsize=256)
def skin_image(arquivo, size):
    im = Image.open(os.path.join(GAMEPLAY_DIR, arquivo)).convert("RGBA")
    k = size / max(im.size)
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))),
                     Image.LANCZOS)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else WHITE



def game(i, name=None):
    lib = library()
    for g in lib:
        if name and g["nome"].lower() == name.lower():
            return g
    return lib[i % len(lib)]


def at(src, frac):
    """Mesma gravação, começando em `frac` (0–1) da duração dela."""
    path, start = src
    dur = clip_duration(path)
    return path, start + max(0.0, dur - start - 2.0) * frac


_open_clips = []
# barra com o nome do jogo no topo das gravações do preparar_gravacoes.py
HEADER_PX = 72


class Clip:
    """Lê um vídeo quadro a quadro (em loop, acelerado SPEED vezes), já
    cortado para w x h. `skip_top` tira a barra com o nome do jogo."""

    def __init__(self, path, w, h, start=0.0, skip_top=0):
        self.path, self.w, self.h = path, int(w), int(h)
        dur = clip_duration(path)
        self.start = start % max(0.1, dur - 1.0) if dur > 1.5 else 0.0
        self.skip_top = skip_top if path.endswith("_celular.mp4") else 0
        self.proc, self.idx = None, -1
        self.img = Image.new("RGB", (self.w, self.h), (0, 0, 0))

    def _open(self):
        crop = (f"crop=iw:ih-{self.skip_top}:0:{self.skip_top},"
                if self.skip_top else "")
        vf = (f"setpts=PTS/{SPEED},fps={FPS},{crop}"
              f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase:"
              f"flags=lanczos,crop={self.w}:{self.h}")
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-stream_loop", "-1",
             "-ss", f"{self.start:.2f}", "-i", self.path, "-vf", vf, "-an",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        _open_clips.append(self)

    def get(self, t):
        self.used = FRAME[0]
        if self.proc is None:
            self._open()
        want, n = int(t * FPS), self.w * self.h * 3
        while self.idx < want:
            buf = self.proc.stdout.read(n)
            if len(buf) < n:
                break
            self.img = Image.frombytes("RGB", (self.w, self.h), buf)
            self.idx += 1
        return self.img

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None


def close_clips():
    while _open_clips:
        _open_clips.pop().close()


FRAME = [0]  # quadro atual da renderização


def close_idle_clips():
    """Fecha as gravações cujas cenas já acabaram (economiza memória)."""
    for c in list(_open_clips):
        if getattr(c, "used", 0) < FRAME[0] - 1:
            c.close()
            _open_clips.remove(c)


def blurred_bg(frame, W, H, dark=0.45):
    """Fundo desfocado (barato: reduz, desfoca e amplia)."""
    small = frame.resize((max(8, W // 14), max(8, H // 14)), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(2.2))
    sw, sh = small.size
    k = max(W / sw, H / sh)
    big = small.resize((int(sw * k) + 2, int(sh * k) + 2), Image.BILINEAR)
    x0, y0 = (big.width - W) // 2, (big.height - H) // 2
    big = big.crop((x0, y0, x0 + W, y0 + H)).convert("RGBA")
    big.alpha_composite(Image.new("RGBA", (W, H), (6, 5, 16, int(255 * dark))))
    return big


# ---------------------------------------------------------------- contexto

class Ctx:
    """Medidas do quadro. `platform` (reels, tiktok, youtube) define as áreas
    seguras: no TikTok os botões cobrem a direita e o rodapé; no Reels e no
    TikTok o topo tem o cabeçalho do app."""

    def __init__(self, W, H, platform=None):
        self.W, self.H = W, H
        self.u = min(W, H) / 1080
        self.cx, self.cy = W / 2, H / 2
        self.vertical = H > W * 1.3
        self.platform = platform or ("reels" if self.vertical else "youtube")
        self.max_w = W * (0.86 if self.vertical else 0.8)
        self.text_cx = self.cx
        self.safe_bottom = 0.92
        self.top_off = 0
        if self.platform == "reels":
            self.safe_bottom, self.top_off = 0.8, 100 * self.u
        elif self.platform == "tiktok":
            self.safe_bottom, self.top_off = 0.74, 130 * self.u
            self.max_w = W * 0.78
            self.text_cx = self.cx - W * 0.04
        # jogo em pé (9:16): tela cheia no vertical, painel central nos outros
        self.panel_w = W if self.vertical else int(H * 9 / 16)
        self.panel_h = H

    def Y(self, frac):
        return self.H * frac

    @property
    def cap_size(self):
        return (96 if self.vertical else 76) * self.u


# ---------------------------------------------------------------- camadas

def game_panel(img, c, clip, t, zoom=1.0):
    fr = clip.get(t)
    if c.vertical:
        put(img, scaled(fr.convert("RGBA"), zoom), c.cx, c.cy)
        return
    img.alpha_composite(blurred_bg(fr, c.W, c.H, 0.55))
    im = scaled(fr.convert("RGBA"), zoom * 0.94)
    im.putalpha(rounded(im.size, int(36 * c.u), WHITE).getchannel("A"))
    put(img, shadow(im.size, int(36 * c.u), 30 * c.u, 160), c.cx, c.cy + 10 * c.u)
    put(img, im, c.cx, c.cy)


def window_card(frame, w, u, bar=False):
    """Gravação do PC como janela de navegador com cantos arredondados.
    `bar` desenha abas/endereço (para gravações sem a barra do navegador)."""
    h = int(w * 9 / 16)
    im = frame.convert("RGBA").resize((w, h), Image.BILINEAR)
    if bar:
        bh = max(18, int(h * 0.075))
        top = Image.new("RGBA", (w, bh), (32, 30, 44, 255))
        d = ImageDraw.Draw(top)
        for k, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
            r = bh * 0.14
            x = bh * 0.45 + k * bh * 0.42
            d.ellipse((x - r, bh / 2 - r, x + r, bh / 2 + r), fill=col)
        pw, ph = int(w * 0.42), int(bh * 0.62)
        px = (w - pw) // 2
        d.rounded_rectangle((px, (bh - ph) // 2, px + pw, (bh + ph) // 2), ph // 2,
                            fill=(52, 50, 66, 255))
        lbl = text_layer("🔒 " + URL, int(ph * 0.62), fill=(225, 225, 235), path=F_SEMI)
        top.alpha_composite(lbl, (px + (pw - lbl.width) // 2, (bh - lbl.height) // 2))
        im = im.resize((w, h - bh), Image.BILINEAR)
        full = Image.new("RGBA", (w, h))
        full.alpha_composite(top, (0, 0))
        full.alpha_composite(im, (0, bh))
        im = full
    im.putalpha(rounded((w, h), int(24 * u), WHITE).getchannel("A"))
    out = shadow((w, h), int(24 * u), 26 * u, 170)
    pad = (out.width - w) // 2
    out.alpha_composite(im, (pad, pad - int(6 * u)))
    return out


def phone_card(frame, h, u):
    """Jogo em pé como cartão com borda branca (sem desenhar aparelho)."""
    w = int(h * 9 / 16)
    im = frame.convert("RGBA").resize((w, h), Image.BILINEAR)
    im.putalpha(rounded((w, h), int(34 * u), WHITE).getchannel("A"))
    b = int(6 * u)
    ring = rounded((w + 2 * b, h + 2 * b), int(34 * u) + b, WHITE + (255,))
    ring.alpha_composite(im, (b, b))
    out = shadow(ring.size, int(38 * u), 26 * u, 170)
    pad = (out.width - ring.width) // 2
    out.alpha_composite(ring, (pad, pad - int(6 * u)))
    return out


def progress_bar(img, c, t, dur):
    y = (58 if c.vertical else 26) * c.u + c.top_off
    w, h = c.W * 0.92, max(4, int(6 * c.u))
    x0 = (c.W - w) / 2
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((x0, y, x0 + w, y + h), h // 2, fill=(255, 255, 255, 70))
    d.rounded_rectangle((x0, y, x0 + max(h, w * clamp01(t / dur)), y + h), h // 2,
                        fill=(255, 255, 255, 235))


@functools.lru_cache(maxsize=8)
def logo_image(size, radius_frac=0.0):
    """Logo KAVIX ARCADE (foto do perfil). radius_frac=0.5 vira círculo."""
    if os.path.exists(LOGO):
        im = Image.open(LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
    else:  # sem o arquivo: usa o mascote desenhado
        im = Image.new("RGBA", (size, size), (20, 16, 40, 255))
        ms = scaled(mascot(), size * 1.3 / 600)
        im.alpha_composite(ms, ((size - ms.width) // 2, int(size * 0.02)))
    if radius_frac:
        m = rounded((size, size), int(size * radius_frac), WHITE).getchannel("A")
        im.putalpha(m)
    return im


@functools.lru_cache(maxsize=8)
def handle_layer(u):
    """Perfil no topo, como num post: avatar do mascote + @ + 'Patrocinado'."""
    av = int(78 * u)
    b = int(4 * u)
    ring = hgradient(av + 2 * b, av + 2 * b, VIOLET, SKY)
    m = Image.new("L", ring.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, ring.width - 1, ring.height - 1), fill=255)
    ring.putalpha(m)
    inner = logo_image(av).copy()
    im2 = Image.new("L", (av, av), 0)
    ImageDraw.Draw(im2).ellipse((0, 0, av - 1, av - 1), fill=255)
    inner.putalpha(im2)
    ring.alpha_composite(inner, (b, b))
    name = text_layer(HANDLE, int(36 * u), path=F_BOLD, shadow_a=200)
    tag = text_layer("jogos grátis no celular e PC", int(27 * u), fill=(230, 230, 240),
                     path=F_SEMI, shadow_a=200)
    W = ring.width + int(14 * u) + max(name.width, tag.width)
    out = Image.new("RGBA", (W, ring.height + int(8 * u)), (0, 0, 0, 0))
    out.alpha_composite(ring, (0, 0))
    out.alpha_composite(name, (ring.width + int(8 * u), -int(4 * u)))
    out.alpha_composite(tag, (ring.width + int(8 * u), int(40 * u)))
    return out


def handle(img, c, alpha=1.0):
    composite(img, set_alpha(handle_layer(c.u), alpha), 34 * c.u,
              (90 if c.vertical else 52) * c.u + c.top_off)


@functools.lru_cache(maxsize=4)
def top_shade(W, H):
    g = np.linspace(1, 0, int(H * 0.16), dtype=np.float32) ** 1.6 * 150
    a = np.zeros((H, W), np.uint8)
    a[: len(g)] = g[:, None].astype(np.uint8)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.putalpha(Image.fromarray(a))
    return im


# ------------------------------------------------------------------- cenas
# Cada cena é f(img, t, dur, c). Textos: lista de
# (início, fim, tipo, texto, opções), com tempos relativos à cena.

def draw_texts(img, c, t, items):
    for it in items:
        t0, t1, kind, text = it[:4]
        opt = it[4] if len(it) > 4 else {}
        if not (t0 <= t < t1):
            continue
        lt, a = t - t0, 1 - prog(t, t1 - 0.12, t1)
        y = c.Y(opt.get("y", 0.6 if c.vertical else 0.74))
        y = min(y, c.Y(c.safe_bottom))
        y = max(y, c.Y(0.12) + c.top_off)
        if kind == "cap":
            caption(img, text, c.text_cx, y, opt.get("size", 1.0) * c.cap_size, lt,
                    c.max_w, opt.get("hl", ()), alpha=a)
        else:
            draw_sticker(img, text, c.text_cx, y, opt.get("size", 54) * c.u, lt,
                         opt.get("rot", -3), opt.get("bg", WHITE),
                         opt.get("fg", BLACK), a, max_w=c.max_w, path=F_DISPLAY)


def sc_game(src, texts=(), name=None, zoom_in=True):
    """Jogabilidade em tela cheia, com etiqueta do nome e legendas."""
    st = {}

    def f(img, t, dur, c):
        if "clip" not in st:
            st["clip"] = Clip(src[0], c.panel_w, c.panel_h, src[1], HEADER_PX)
        game_panel(img, c, st["clip"], t, 1.0 + (0.06 * t / dur if zoom_in else 0))
        img.alpha_composite(top_shade(c.W, c.H))
        handle(img, c)
        if name:
            draw_sticker(img, name, c.text_cx,
                         c.Y(0.2 if c.vertical else 0.24) + c.top_off * 0.6,
                         62 * c.u, t - 0.05, -3, path=F_DISPLAY)
        draw_texts(img, c, t, texts)
    return f


def sc_pc(src_pc, texts=()):
    """Gravação do PC numa janela de navegador sobre o próprio jogo desfocado."""
    st = {}

    def f(img, t, dur, c):
        if "pc" not in st:
            st["pc"] = Clip(src_pc[0], 1280, 720, src_pc[1])
        fr = st["pc"].get(t)
        img.alpha_composite(blurred_bg(fr, c.W, c.H, 0.5))
        k = spring(t / 0.5)
        card = window_card(fr, int(c.W * (0.94 if c.vertical else 0.72)), c.u,
                           bar=not src_pc[0].endswith("_pc.mp4"))
        card = scaled(card, lerp(0.7, 1.0, k) * (1 + 0.04 * t / dur))
        card = card.rotate(lerp(-8, -2, k), expand=True, resample=Image.BICUBIC)
        put(img, set_alpha(card, clamp01(t / 0.1)), c.cx, c.Y(0.48 if c.vertical else 0.5))
        img.alpha_composite(top_shade(c.W, c.H))
        handle(img, c)
        draw_texts(img, c, t, texts)
    return f


def sc_collage(src_cel, src_pc, texts=()):
    """Celular e PC juntos, em cartões inclinados."""
    st = {}

    def f(img, t, dur, c):
        if not st:
            st["pc"] = Clip(src_pc[0], 1280, 720, src_pc[1])
            st["cel"] = Clip(src_cel[0], 540, 960, src_cel[1], HEADER_PX)
        fp, fc = st["pc"].get(t), st["cel"].get(t)
        img.alpha_composite(blurred_bg(fc, c.W, c.H, 0.5))
        if c.vertical:
            ww, ph = int(c.W * 0.86), int(c.H * 0.4)
            pcpos, celpos = (c.cx + 40 * c.u, c.Y(0.32)), (c.cx - 150 * c.u, c.Y(0.6))
        else:
            ww, ph = int(c.W * 0.5), int(c.H * 0.7)
            pcpos, celpos = (c.cx + c.W * 0.1, c.Y(0.44)), (c.cx - c.W * 0.2, c.Y(0.52))
        k1, k2 = spring(t / 0.5), spring((t - 0.15) / 0.5)
        pc = window_card(fp, ww, c.u, bar=not src_pc[0].endswith("_pc.mp4")).rotate(
            lerp(10, 3, k1), expand=True,
                                              resample=Image.BICUBIC)
        put(img, set_alpha(scaled(pc, lerp(0.6, 1, k1)), clamp01(t / 0.1)), *pcpos)
        if t > 0.15:
            ce = phone_card(fc, ph, c.u).rotate(lerp(-12, -5, k2), expand=True,
                                                 resample=Image.BICUBIC)
            put(img, set_alpha(scaled(ce, lerp(0.6, 1, k2)),
                               clamp01((t - 0.15) / 0.1)), *celpos)
        img.alpha_composite(top_shade(c.W, c.H))
        handle(img, c)
        draw_texts(img, c, t, texts)
    return f


def sc_items(src_bg, texts=()):
    """'Itens exclusivos': mascotes em cartões de vidro sobre o jogo."""
    st = {}

    def f(img, t, dur, c):
        if "bg" not in st:
            st["bg"] = Clip(src_bg[0], 540, 960, src_bg[1], HEADER_PX)
        img.alpha_composite(blurred_bg(st["bg"].get(t), c.W, c.H, 0.55))
        cw = int((c.W * 0.78 if c.vertical else c.H * 0.56) / 2)
        ch = int(cw * 1.2)
        gx, gy = c.cx, c.Y(0.52 if c.vertical else 0.55)
        reais = pick_skins(4)
        for i, (c1, c2) in enumerate(MASCOT_SKINS):
            lt = t - 0.5 - i * 0.18
            if lt < 0:
                continue
            r, q = divmod(i, 2)
            x = gx + (q - 0.5) * (cw + 26 * c.u)
            y = gy + (r - 0.5) * (ch + 26 * c.u)
            k = spring(lt / 0.5)
            card = rounded((cw, ch), int(34 * c.u), (255, 255, 255, 38),
                           outline=(255, 255, 255, 90), width=max(2, int(3 * c.u)))
            if i < len(reais):  # skin de verdade do inventário
                it = reais[i]
                m = skin_image(it["arquivo"], int(cw * 0.68))
                card.alpha_composite(m, ((cw - m.width) // 2,
                                         int(ch * 0.38 - m.height / 2 +
                                             math.sin(t * 4 + i) * 8 * c.u)))
                nm = text_layer(it["nome"], int(34 * c.u), path=F_BOLD, shadow_a=150)
                card.alpha_composite(nm, ((cw - nm.width) // 2, int(ch * 0.66)))
                chip = sticker(it["raridade_nome"].upper(), int(26 * c.u),
                               hexrgb(it["cor"]), INK)
            else:
                m = scaled(mascot(600, c1, c2), cw * 0.95 / 600)
                card.alpha_composite(m, ((cw - m.width) // 2,
                                         int(ch * 0.42 - m.height / 2 +
                                             math.sin(t * 4 + i) * 8 * c.u)))
                chip = sticker("EXCLUSIVO", int(30 * c.u), "brand", INK)
            card.alpha_composite(chip, ((cw - chip.width) // 2,
                                        int(ch * 0.85 - chip.height / 2)))
            card = card.rotate((-1) ** i * 3 * (1 - k), expand=True,
                               resample=Image.BICUBIC)
            put(img, set_alpha(scaled(card, lerp(0.4, 1, k)), clamp01(lt / 0.1)), x, y)
            if lt < 0.6:
                put(img, set_alpha(emoji_layer("✨", int(70 * c.u)), 1 - lt / 0.6),
                    x + cw * 0.38, y - ch * 0.42)
        img.alpha_composite(top_shade(c.W, c.H))
        handle(img, c)
        draw_texts(img, c, t, texts)
    return f


def sc_skin_reveal(src_bg, items, texts=()):
    """Uma skin por vez, grande, com brilho na cor da raridade."""
    st = {}

    def f(img, t, dur, c):
        if "bg" not in st:
            st["bg"] = Clip(src_bg[0], 540, 960, src_bg[1], HEADER_PX)
        img.alpha_composite(blurred_bg(st["bg"].get(t), c.W, c.H, 0.62))
        if not items:
            return
        per = dur / len(items)
        i = min(len(items) - 1, int(t / per))
        it, lt = items[i], t - i * per
        col = hexrgb(it["cor"])
        k = spring(lt / 0.45)
        size = int(min(c.W, c.H) * (0.62 if c.vertical else 0.5))
        cy = c.Y(0.5)
        glow = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((size * 0.4, size * 0.4, size * 1.6, size * 1.6),
                                     fill=col + (150,))
        glow = glow.filter(ImageFilter.GaussianBlur(size * 0.18))
        put(img, set_alpha(scaled(glow, lerp(0.5, 1, k)), clamp01(lt / 0.15)), c.cx, cy)
        sk = skin_image(it["arquivo"], size)
        sk = sk.rotate(lerp(-25, 0, k), expand=True, resample=Image.BICUBIC)
        put(img, set_alpha(scaled(sk, lerp(0.2, 1, k) * (1 + 0.03 * math.sin(t * 6))),
                           clamp01(lt / 0.08)), c.cx, cy + math.sin(t * 4) * 10 * c.u)
        draw_sticker(img, it["raridade_nome"].upper(), c.cx,
                     cy - size * 0.62, 44 * c.u, lt - 0.1, -4, col, INK)
        caption(img, it["nome"], c.cx, cy + size * 0.66, c.cap_size * 0.9, lt - 0.15,
                c.max_w, highlight=(0,) if it["raridade"] == "lendario" else ())
        img.alpha_composite(top_shade(c.W, c.H))
        handle(img, c)
        draw_texts(img, c, t, texts)
    return f


@functools.lru_cache(maxsize=8)
def cta_button(w, h, text):
    btn = hgradient(w, h, VIOLET, SKY)
    btn.putalpha(rounded((w, h), int(h * 0.3), WHITE).getchannel("A"))
    lbl = text_layer(text, int(h * 0.4), fill=INK, path=F_BLACK)
    btn.alpha_composite(lbl, ((w - lbl.width) // 2, (h - lbl.height) // 2))
    return btn


def sc_cta(src_bg, title="Cria sua conta agora", button="Criar minha conta"):
    """Final: cartão de vidro sobre o jogo desfocado, com botão e endereço."""
    st = {}

    def f(img, t, dur, c):
        if "bg" not in st:
            st["bg"] = Clip(src_bg[0], 540, 960, src_bg[1], HEADER_PX)
        img.alpha_composite(blurred_bg(st["bg"].get(t), c.W, c.H, 0.62))
        k = min(1.0, c.H * 0.9 / (1080 * c.u)) * c.u
        cw, ch = int(880 * k), int(860 * k)
        e = spring(t / 0.55)
        cy = c.cy + 20 * c.u + lerp(300, 0, e) * k
        card = rounded((cw, ch), int(56 * k), (255, 255, 255, 34),
                       outline=(255, 255, 255, 80), width=max(2, int(3 * k)))
        put(img, set_alpha(shadow((cw, ch), int(56 * k), 40 * k, 120),
                           clamp01(t / 0.2)), c.cx, cy + 14 * k)
        put(img, set_alpha(card, clamp01(t / 0.15)), c.cx, cy)
        top = cy - ch / 2

        def Y(o):
            return top + o * k

        if t > 0.2:  # logo do perfil no topo do cartão
            lg = logo_image(int(230 * k), 0.24)
            put(img, shadow(lg.size, int(55 * k), 20 * k, 140), c.cx, top - 10 * k)
            put(img, scaled(lg, spring((t - 0.2) / 0.5)),
                c.cx, top - 18 * k + math.sin(t * 5) * 6 * k)
        draw_sticker(img, "🎁 itens exclusivos no cadastro", c.cx, Y(170), 38 * k,
                     t - 0.3, -2, LIME, BLACK)
        caption(img, title, c.cx, Y(300), 86 * k, t - 0.4, cw * 0.86,
                highlight=(len(title.split()) - 1,), per_word=0.06)
        if t > 0.75:
            lt = t - 0.75
            bw, bh = int(700 * k), int(128 * k)
            b = cta_button(bw, bh, button).copy()
            sx = ((lt * 0.9) % 1.5 - 0.25) * bw
            sh = Image.new("RGBA", b.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).polygon([(sx, 0), (sx + bh * 0.5, 0),
                                        (sx + bh * 0.1, bh), (sx - bh * 0.4, bh)],
                                       fill=(255, 255, 255, 120))
            sh.putalpha(Image.fromarray(np.minimum(np.asarray(sh.getchannel("A")),
                                                   np.asarray(b.getchannel("A")))))
            b.alpha_composite(sh)
            by = Y(500)
            put(img, scaled(b, spring(lt / 0.45) * (1 + 0.04 * math.sin(lt * 7))),
                c.cx, by)
            press = abs(math.sin((lt % 1.4) / 1.4 * math.pi * 2))
            put(img, emoji_layer("👆", int(110 * k)),
                c.cx + bw * 0.44, by + bh * 0.45 + press * 30 * k)
        draw_sticker(img, URL, c.cx, Y(675), 46 * k, t - 0.95, 0)
        if t > 1.15:
            lay = text_layer("📱 celular  •  💻 PC  •  sem baixar nada", int(36 * k),
                             path=F_BOLD, shadow_a=180)
            put(img, set_alpha(lay, clamp01((t - 1.15) / 0.2)), c.cx, Y(785))
    return f


# ------------------------------------------------------------------- áudio

def _env(n, decay):
    return np.exp(-np.arange(n) / SR / decay)


def _smooth(x, k):
    return x if k <= 1 else np.convolve(x, np.ones(k) / k, mode="same")


def _add(out, sig, t):
    i = int(t * SR)
    if 0 <= i < len(out):
        j = min(len(out), i + len(sig))
        out[i:j] += sig[: j - i]


def sfx(kind, rng):
    def n(s):
        return int(s * SR)
    if kind == "kick":
        tt = np.arange(n(0.35)) / SR
        f = 48 + 120 * np.exp(-tt / 0.03)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n(0.35), 0.12) * 0.9
    if kind == "clap":
        x = rng.uniform(-1, 1, n(0.22))
        x = x - _smooth(x, 6)
        env = _env(n(0.22), 0.07)
        for d in (0.012, 0.024):
            env = env + np.roll(_env(n(0.22), 0.01), int(d * SR)) * 0.6
        return x * env * 0.32
    if kind == "hat":
        x = rng.uniform(-1, 1, n(0.05))
        return (x - _smooth(x, 3)) * _env(n(0.05), 0.012) * 0.2
    if kind == "whoosh":
        x = rng.uniform(-1, 1, n(0.35))
        w = np.sin(np.linspace(0, np.pi, n(0.35))) ** 2
        return (x - _smooth(x, 30)) * w * 0.28
    if kind == "pop":
        tt = np.arange(n(0.09)) / SR
        f = 900 - 500 * tt / 0.09
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n(0.09), 0.03) * 0.35
    if kind == "ding":
        out = np.zeros(n(0.9))
        for k, f in enumerate([1318.5, 1760.0]):
            m = n(0.7)
            s = np.sin(2 * np.pi * f * np.arange(m) / SR) * _env(m, 0.2) * 0.18
            i = n(k * 0.09)
            out[i:i + m] += s[: len(out) - i]
        return out
    if kind == "boom":
        tt = np.arange(n(1.2)) / SR
        f = 32 + 70 * np.exp(-tt / 0.07)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n(1.2), 0.45) * 0.9
    raise ValueError(kind)


ROOT = {"A": 55.0, "F": 43.65, "C": 65.41, "G": 49.0, "D": 73.42, "E": 41.2}


def music(duration, bpm, prog_, events, seed, gap=None):
    """Batida trap/phonk: 808 com glide, chimbal com rolos, palma no 3 e
    sininho. `gap` = (início, fim) de uma pausa antes do final."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(duration * SR))
    step = 60 / bpm / 4  # semicolcheia
    for i in range(int(duration / step)):
        t = i * step
        if gap and gap[0] <= t < gap[1]:
            continue
        s, b = i % 16, i // 16
        root = ROOT[prog_[b % len(prog_)]]
        if s in (0, 10) or (b % 2 and s == 7):
            _add(out, sfx("kick", rng), t)
        if s in (0, 10):
            m = int(step * (6 if s == 0 else 5) * SR)
            tt = np.arange(m) / SR
            f = root * (1 + 0.5 * np.exp(-tt / 0.05))  # glide do 808
            bass = np.tanh(2.2 * np.sin(2 * np.pi * np.cumsum(f) / SR))
            _add(out, bass * np.minimum(1, tt / 0.005) * _env(m, 0.5) * 0.45, t)
        if s == 8:
            _add(out, sfx("clap", rng), t)
        if s % 2 == 0:
            _add(out, sfx("hat", rng), t)
        if b % 2 == 1 and s >= 12:  # rolo de chimbal
            for k in range(1, 3):
                _add(out, sfx("hat", rng) * 0.7, t + k * step / 3)
        if s in (0, 3, 6, 10, 12):  # sininho
            semi = {0: 12, 3: 15, 6: 19, 10: 15, 12: 10}[s]
            f = root * 4 * 2 ** (semi / 12)
            m = int(0.22 * SR)
            tt = np.arange(m) / SR
            bell = np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.76 * tt)
            _add(out, bell * _env(m, 0.07) * 0.06, t)
    for kind, t in events:
        _add(out, sfx(kind, rng), t)
    fade = int(0.5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = np.tanh(out * 1.3)
    return out / max(1e-6, np.abs(out).max()) * 0.9


def write_wav(path, mono):
    data = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.repeat(data[:, None], 2, axis=1).tobytes())


# ------------------------------------------------------------------ roteiros

def build(scenes, bpm=140, prog_="AFCG", seed=1, extra=()):
    """[(duração, cena)] -> roteiro com tempos, efeitos e pausa antes do CTA."""
    t, out, events = 0.0, [], []
    for i, (d, fn) in enumerate(scenes):
        out.append((t, t + d, fn))
        if i:
            events.append(("whoosh", t - 0.12))
        t += d
    cta = out[-1][0]
    events += [("boom", cta), ("ding", cta + 0.8)] + list(extra)
    return dict(dur=t, scenes=out, events=events, bpm=bpm, prog=prog_,
                seed=seed, gap=(cta - 0.3, cta))


HOOKS = ["duvido você passar de 30 pontos 😤",
         "esse jogo é viciante demais 😭",
         "aposto que tu não dura 1 minuto 💀",
         "testa teus reflexos aqui ⚡",
         "só os brabos passam do nível 3 🔥"]


def spec_arcade(W, H):
    """Gancho 'POV' e cortes rápidos por todos os jogos gravados."""
    lib = library()
    sc = [(2.4, sc_game(at(lib[0]["celular"], 0.3), texts=[
        (0.0, 2.4, "label", "POV:", {"y": 0.3, "size": 58, "rot": -4}),
        (0.15, 2.4, "cap", f"você achou {total_jogos()} jogos num site só 🎮",
         {"y": 0.42, "hl": (2, 3)}),
    ]))]
    for i, g in enumerate(lib[1:], 1):
        texts = []
        if i == 4:
            texts.append((0, 1.5, "cap", "qual é o teu favorito? 👇", {"hl": (3,)}))
        if i == 8:
            texts.append((0, 1.5, "cap", "e dá pra jogar no celular E no PC 🤯",
                          {"hl": (5, 6, 7)}))
        sc.append((1.5, sc_game(at(g["celular"], 0.35), texts, name=g["nome"])))
    sc.append((2.8, sc_collage(at(game(9, "Cobrinha")["celular"], 0.1),
                               at(game(2, "Quebra Blocos")["pc"], 0.6), texts=[
        (0.2, 2.8, "cap", "celular ou PC? tu escolhe 😎",
         {"y": 0.84 if H > W else 0.86, "hl": (0, 2)})])))
    sc.append((5.0, sc_cta(at(lib[0]["celular"], 0.6))))
    pops = [("pop", 2.4 + 1.5 * k + 0.05) for k in range(len(lib) - 1)]
    return build(sc, 140, "AFCG", 6, extra=pops)


def spec_destaque(nome, W, H):
    """Um jogo só: gancho, jogo em tela cheia, PC e CTA."""
    g = game(0, nome)
    i = [x["nome"] for x in library()].index(g["nome"])
    hook = HOOKS[i % len(HOOKS)]
    sc = [
        (5.5, sc_game(at(g["celular"], 0.05), name=g["nome"], texts=[
            (0.1, 2.6, "cap", hook, {"y": 0.36, "hl": (len(hook.split()) - 2,)}),
            (2.8, 5.5, "cap", "joga direto do celular 📱", {"y": 0.36, "hl": (3,)}),
        ])),
        (3.0, sc_pc(at(g["pc"], 0.6), texts=[
            (0.1, 3.0, "label", "💻 e no PC também",
             {"y": 0.2 if H > W else 0.14, "size": 58}),
            (0.3, 3.0, "cap", "sem baixar nada", {"y": 0.78, "hl": (2,)}),
        ])),
        (5.0, sc_cta(at(g["celular"], 0.5))),
    ]
    return build(sc, 136 + i % 3 * 4, ["AFCG", "FCGA", "ADFE"][i % 3], 20 + i,
                 extra=[("pop", 0.1)])


def spec_plataformas(W, H):
    """Celular, PC e os dois juntos + montagem curta."""
    lib = library()
    sc = [
        (3.0, sc_game(at(game(0, "Espinhos")["celular"], 0.3), name="Espinhos",
                      texts=[(0.1, 3.0, "cap", "joga no celular 📱",
                              {"y": 0.36, "hl": (2,)})])),
        (3.0, sc_pc(at(game(2, "Quebra Blocos")["pc"], 0.4), texts=[
            (0.1, 3.0, "cap", "ou no PC 💻", {"y": 0.2 if H > W else 0.14,
                                              "hl": (2,)}),
            (0.6, 3.0, "label", "direto no navegador ⚡", {"y": 0.8, "size": 52})])),
        (3.0, sc_collage(at(game(9, "Cobrinha")["celular"], 0.2),
                         at(game(8, "Empilha")["pc"], 0.3), texts=[
            (0.2, 3.0, "cap", "sem baixar nada 🙌", {"y": 0.86, "hl": (2,)})])),
    ]
    for k, g in enumerate(lib[3:7]):
        texts = [(0, 1.1, "cap", f"{total_jogos()} jogos te esperando 🎮",
                  {"hl": (0, 1)})] if k == 0 else []
        sc.append((1.1, sc_game(at(g["celular"], 0.4), texts, name=g["nome"])))
    sc.append((5.0, sc_cta(at(game(10, "Memória")["celular"], 0.5))))
    return build(sc, 144, "FCGA", 5)


def spec_desafio(W, H):
    sc = [
        (1.8, sc_game(at(game(6, "Reflexo")["celular"], 0.3), texts=[
            (0.0, 1.8, "cap", "teus amigos já tão jogando...",
             {"y": 0.4, "hl": (3,)})])),
        (1.6, sc_game(at(game(4, "Pega Tudo")["celular"], 0.3), texts=[
            (0.0, 1.6, "cap", "e tu aí parado 💀", {"y": 0.4, "hl": (3,)})])),
    ]
    for k, g in enumerate([game(2, "Quebra Blocos"), game(7, "Troca Cor"),
                           game(9, "Cobrinha")]):
        texts = [(0, 1.2, "label", "bora? 👀", {"y": 0.36, "size": 76})] if k == 0 else []
        sc.append((1.2, sc_game(at(g["celular"], 0.5), texts, name=g["nome"])))
    sc.append((4.8, sc_cta(at(game(0, "Espinhos")["celular"], 0.7))))
    return build(sc, 148, "ADFE", 4)


def spec_itens(W, H):
    sc = [
        (4.6, sc_items(at(game(5, "Órbita")["celular"], 0.3), texts=[
            (0.0, 4.6, "cap", "cadastro novo = itens exclusivos 🎁",
             {"y": 0.19 if H > W else 0.14, "hl": (3, 4)}),
            (2.4, 4.6, "label", "só pra quem cria conta agora",
             {"y": 0.86 if H > W else 0.9, "size": 46})])),
        (2.6, sc_game(at(game(1, "Passagem")["celular"], 0.2), name="Passagem",
                      texts=[(0.1, 2.6, "cap", f"e ainda {total_jogos()} jogos pra jogar 🎮",
                              {"y": 0.4, "hl": (2, 3)})])),
        (5.0, sc_cta(at(game(3, "Três Pistas")["celular"], 0.5))),
    ]
    return build(sc, 140, "AFCG", 3,
                 extra=[("pop", 0.5 + k * 0.18) for k in range(4)])


def spec_todos(W, H):
    """Todos os jogos gravados em cortes de menos de 1 segundo."""
    lib = library()
    n = total_jogos()
    sc = [(2.0, sc_game(at(lib[0]["celular"], 0.3), texts=[
        (0.0, 2.0, "cap", f"{n} jogos em {n} segundos 😳", {"y": 0.4, "hl": (0, 3)})]))]
    for i, g in enumerate(lib[1:], 2):
        sc.append((0.75, sc_game(at(g["celular"], 0.45), name=g["nome"], texts=[
            (0, 0.75, "label", f"#{i}", {"y": 0.84 if H > W else 0.86, "size": 44,
                                         "rot": 4, "bg": LIME})])))
    sc.append((4.8, sc_cta(at(lib[0]["celular"], 0.7))))
    return build(sc, 150, "AFCG", 9)


def spec_skins(W, H):
    """Skins reais do inventário + jogo com as skins + CTA."""
    lib = library()
    todas = skins()
    n = f"+{len(todas) // 10 * 10}" if len(todas) >= 20 else "várias"
    reveal = sorted(pick_skins(6), key=lambda x: RAR_ORDEM.get(x["raridade"], 0))
    sc = [
        (2.4, sc_game(at(game(0)["celular"], 0.5), texts=[
            (0.1, 2.4, "cap", "tua bolinha pode ficar assim 👀", {"y": 0.38, "hl": (4,)})])),
        (5.4, sc_skin_reveal(at(game(3)["celular"], 0.3), reveal, texts=[
            (0.0, 5.4, "cap", f"{n} skins pra liberar 🔥", {"y": 0.16 if H > W else 0.12,
                                                            "hl": (0,), "size": 0.8})])),
        (3.6, sc_items(at(game(5)["celular"], 0.3), texts=[
            (0.0, 3.6, "cap", "cadastro novo = itens exclusivos 🎁",
             {"y": 0.19 if H > W else 0.14, "hl": (3, 4)})])),
        (5.0, sc_cta(at(lib[0]["celular"], 0.6))),
    ]
    return build(sc, 140, "FCGA", 11,
                 extra=[("pop", 2.4 + k * 0.9) for k in range(6)])


TOP5 = [("Empilha", "esse aqui é tenso 😤"),
        ("Cobrinha", "clássico que não envelhece 🐍"),
        ("Espinhos", "um toque errado e já era 💀"),
        ("Quebra Blocos", "não consigo parar 😭"),
        ("Reflexo", "o mais viciante de todos 👑")]


def spec_top5(W, H):
    """Contagem regressiva do 5 ao 1 com reações e chamada pra comentar."""
    lib = library()
    sc = [(2.2, sc_game(at(game(4)["celular"], 0.5), texts=[
        (0.0, 2.2, "label", "TOP 5", {"y": 0.28, "size": 70, "rot": -4, "bg": LIME}),
        (0.2, 2.2, "cap", "jogos mais viciantes do KAVIX 🔥", {"y": 0.4, "hl": (2,)})]))]
    for k, (nome, fala) in enumerate(TOP5):
        g = game(k * 5 + 1, nome)
        rank = 5 - k
        sc.append((2.8, sc_game(at(g["celular"], 0.4), texts=[
            (0.0, 2.8, "label", f"#{rank}", {"y": 0.2, "size": 66, "rot": -5,
                                             "bg": LIME if rank > 1 else (255, 206, 64)}),
            (0.1, 2.8, "label", g["nome"], {"y": 0.27, "size": 62, "rot": 3}),
            (0.6, 2.8, "cap", fala, {"y": 0.62, "hl": (len(fala.split()) - 2,)})])))
    sc.append((2.0, sc_collage(at(game(9, "Cobrinha")["celular"], 0.2),
                               at(game(2, "Quebra Blocos")["pc"], 0.5), texts=[
        (0.1, 2.0, "cap", "concorda? comenta o teu 👇", {"y": 0.86, "hl": (2, 3)})])))
    sc.append((5.0, sc_cta(at(lib[0]["celular"], 0.6))))
    return build(sc, 138, "ADFE", 12,
                 extra=[("pop", 2.2 + 2.8 * k + 0.02) for k in range(5)])


VIDEOS = {}
for _nome, _fn in (("todos", spec_todos), ("top5", spec_top5), ("skins", spec_skins)):
    VIDEOS[f"{_nome}_reels"] = (_fn, 1080, 1920, "reels")
    VIDEOS[f"{_nome}_tiktok"] = (_fn, 1080, 1920, "tiktok")
    VIDEOS[f"{_nome}_youtube"] = (_fn, 1920, 1080, "youtube")
VIDEOS.update({
    "arcade": (spec_arcade, 1080, 1920),
    "arcade_feed": (spec_arcade, 1080, 1350),
    "arcade_youtube": (spec_arcade, 1920, 1080),
    "plataformas": (spec_plataformas, 1080, 1920),
    "plataformas_youtube": (spec_plataformas, 1920, 1080),
    "desafio": (spec_desafio, 1080, 1920),
    "itens": (spec_itens, 1080, 1920),
})


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in s)


# um vídeo curto de destaque para cada jogo gravado
for _g in library():
    VIDEOS[f"destaque_{_slug(_g['nome'])}"] = (
        functools.partial(spec_destaque, _g["nome"]), 1080, 1920)


# --------------------------------------------------------------- renderizar

def render_frame(s, c, t):
    W, H = c.W, c.H
    img = Image.new("RGBA", (W, H), (6, 5, 16, 255))
    for a, b, fn in s["scenes"]:
        if a <= t < b:
            fn(img, t - a, b - a, c)
    if t < s["scenes"][-1][0]:
        progress_bar(img, c, t, s["dur"])
    frame = img.convert("RGB")
    for ct in [a for a, _, _ in s["scenes"][1:]]:
        dt = t - ct
        if 0 <= dt < 0.2:  # corte com "zoom punch" e clarão rápido
            z = 1 + 0.12 * (1 - dt / 0.2) ** 2
            big = frame.resize((int(W * z), int(H * z)), Image.BILINEAR)
            x0, y0 = (big.width - W) // 2, (big.height - H) // 2
            frame = big.crop((x0, y0, x0 + W, y0 + H))
            if dt < 0.07:
                frame = Image.blend(frame, Image.new("RGB", (W, H), WHITE),
                                    0.28 * (1 - dt / 0.07))
    return frame


def render(name):
    spec_fn, W, H, *plat = VIDEOS[name]
    return render_spec(spec_fn(W, H), W, H, plat[0] if plat else None,
                       os.path.join(OUT_DIR, f"kavix_{name}_{W}x{H}.mp4"))


def render_spec(s, W, H, platform, out):
    """Renderiza um roteiro (dict do build) em `out`."""
    c = Ctx(W, H, platform)
    ACCENT[0] = s.get("accent", LIME)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wav = out + ".wav"
    name = os.path.basename(out)
    write_wav(wav, music(s["dur"], s["bpm"], s["prog"], s["events"], s["seed"],
                         s["gap"]))
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-maxrate", "6M", "-bufsize", "12M",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(int(s["dur"] * FPS)):
        FRAME[0] = fi
        proc.stdin.write(render_frame(s, c, fi / FPS).tobytes())
        close_idle_clips()
    proc.stdin.close()
    proc.wait()
    close_clips()
    os.remove(wav)
    if proc.returncode:
        raise RuntimeError(f"ffmpeg falhou em {name}")
    return out


def main():
    if not library():
        sys.exit(f"sem gravações em {GAMEPLAY_DIR}: rode o preparar_gravacoes.py "
                 "ou o gravar_auto.cjs antes (veja o README)")
    names = sys.argv[1:] or list(VIDEOS)
    for n in names:
        if n not in VIDEOS:
            sys.exit(f"vídeo desconhecido: {n} (opções: {', '.join(VIDEOS)})")
    with Pool(min(len(names), os.cpu_count() or 1)) as pool:
        for path in pool.imap_unordered(render, names):
            print("ok:", path)


if __name__ == "__main__":
    main()
