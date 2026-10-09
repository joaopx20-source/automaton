#!/usr/bin/env python3
"""Gera os vídeos promocionais do KAVIX (kavixbrasil.com.br).

Tudo é desenhado por código (Pillow + numpy) e a trilha sonora é sintetizada,
então não há direitos autorais de terceiros envolvidos.

Uso:
    python3 promo/kavix/gerar_videos.py            # gera todos
    python3 promo/kavix/gerar_videos.py hype desafio  # gera só alguns

Requer: python3, pillow, numpy e ffmpeg no PATH.
"""
import functools
import json
import math
import os
import random
import subprocess
import sys
import unicodedata
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FPS = 30
SR = 44100
OUT_DIR = os.environ.get("KAVIX_OUT_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "videos")

URL = "kavixbrasil.com.br"
TOTAL_JOGOS = "+20 JOGOS"  # quantidade de jogos do site (não só os gravados)

# Gravações reais do jogo: coloque aqui arquivos chamados celular.* e pc.*
# (mp4, webm, mov...). Veja o README.
GAMEPLAY_DIR = os.environ.get("KAVIX_GAMEPLAY_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gameplay")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi")
# Velocidade da jogabilidade nos vídeos (2 = modo 2x).
SPEED = float(os.environ.get("KAVIX_SPEED", "2"))

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_BLACK = next(p for p in FONT_CANDIDATES if os.path.exists(p))
FONT_BOLD = next(p for p in FONT_BOLD_CANDIDATES if os.path.exists(p))

# Paleta
WHITE = (255, 255, 255)
GOLD1 = (255, 230, 120)
GOLD2 = (255, 140, 0)
CYAN = (41, 230, 255)
MAGENTA = (255, 46, 136)
PURPLE = (140, 60, 255)
DARK = (14, 6, 34)

# Tema do site KAVIX ARCADE (cores tiradas das telas do próprio site)
BG = (7, 6, 18)          # fundo da página
BG2 = (13, 10, 32)
CARD = (17, 14, 36)      # cartões/modais ("Fim de jogo")
BORDER = (52, 46, 86)
VIOLET = (124, 92, 255)  # botão "Jogar de novo": degradê roxo -> ciano
SKY = (56, 210, 255)
MUTED = (170, 167, 195)
INK = (16, 14, 40)       # texto escuro dos botões
CHIP = (40, 38, 58)      # etiqueta "FIM DE JOGO"
XP_BG, XP_FG = (60, 46, 12), (255, 206, 64)  # etiqueta "+XP no passe"


# ---------------------------------------------------------------- utilidades

def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def prog(t, a, b):
    return clamp01((t - a) / (b - a)) if b > a else float(t >= a)


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_cubic(x):
    x = clamp01(x)
    return x ** 3


def ease_out_back(x, s=1.9):
    x = clamp01(x)
    c3 = s + 1
    return 1 + c3 * (x - 1) ** 3 + s * (x - 1) ** 2


def lerp(a, b, x):
    return a + (b - a) * x


_font_cache = {}


def font(size, path=FONT_BLACK):
    size = max(6, int(size))
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def composite(base, layer, x, y):
    """alpha_composite que aceita posições negativas / fora da tela."""
    x, y = int(round(x)), int(round(y))
    lw, lh = layer.size
    bw, bh = base.size
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(lw, bw - x), min(lh, bh - y)
    if ex <= sx or ey <= sy:
        return
    base.alpha_composite(layer.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def composite_center(base, layer, cx, cy):
    composite(base, layer, cx - layer.width / 2, cy - layer.height / 2)


def set_alpha(layer, alpha):
    if alpha >= 0.999:
        return layer
    a = np.asarray(layer.getchannel("A"), dtype=np.float32) * max(0.0, alpha)
    layer = layer.copy()
    layer.putalpha(Image.fromarray(a.astype(np.uint8)))
    return layer


def vgradient(w, h, c1, c2):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    arr = np.zeros((h, w, 4), np.uint8)
    for i in range(3):
        arr[..., i] = (c1[i] + (c2[i] - c1[i]) * t).astype(np.uint8)
    arr[..., 3] = 255
    return Image.fromarray(arr, "RGBA")


def fit_size(text, size, max_w, path=FONT_BLACK):
    w = font(size, path).getlength(text)
    return size * max_w / w if w > max_w else size


def hgradient(w, h, c1, c2):
    return vgradient(h, w, c1, c2).transpose(Image.TRANSPOSE)


def text_layer(text, size, fill=WHITE, stroke=0, stroke_fill=(0, 0, 0),
               gradient=None, glow=None, glow_radius=0, path=FONT_BLACK,
               hgrad=False, glow_strength=1.8):
    f = font(size, path)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    pad = int(glow_radius * 3) + 6
    w, h = r - l + 2 * pad, b - t + 2 * pad
    pos = (pad - l, pad - t)

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text(pos, text, font=f, fill=255)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    outer = mask
    if stroke:
        smask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(smask).text(pos, text, font=f, fill=255,
                                   stroke_width=stroke, stroke_fill=255)
        layer.paste(stroke_fill + (255,), (0, 0, w, h), smask)
        outer = smask
    if gradient:
        gfn = hgradient if hgrad else vgradient
        layer.paste(gfn(w, h, gradient[0], gradient[1]), (0, 0), mask)
    else:
        layer.paste(fill + (255,), (0, 0, w, h), mask)
    if glow:
        a = np.asarray(outer.filter(ImageFilter.GaussianBlur(glow_radius)),
                       np.float32) * glow_strength
        g = Image.new("RGBA", (w, h), glow + (0,))
        g.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
        g.alpha_composite(layer)
        layer = g
    return layer


def draw_text(img, text, cx, cy, size, alpha=1.0, rotate=0.0, max_w=None,
              **kw):
    if alpha <= 0.01 or size < 4:
        return
    if max_w:
        size = fit_size(text, size, max_w, kw.get("path", FONT_BLACK))
    layer = text_layer(text, size, **kw)
    if rotate:
        layer = layer.rotate(rotate, expand=True, resample=Image.BICUBIC)
    composite_center(img, set_alpha(layer, alpha), cx, cy)


def draw_glitch_text(img, text, cx, cy, size, t, alpha=1.0, max_w=None):
    if max_w:
        size = fit_size(text, size, max_w)
    jitter = (math.sin(t * 53) * 0.5 + math.sin(t * 31) * 0.5)
    d = size * 0.035 * (1 + 2 * (abs(jitter) > 0.8))
    draw_text(img, text, cx - d, cy, size, alpha * 0.8, fill=VIOLET)
    draw_text(img, text, cx + d, cy, size, alpha * 0.8, fill=SKY)
    draw_text(img, text, cx, cy, size, alpha, fill=WHITE)


def rounded_box(size, radius, fill, outline=None, width=0, ss=2):
    w, h = size
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle(
        (0, 0, w * ss - 1, h * ss - 1), radius * ss, fill=fill,
        outline=outline, width=width * ss)
    return im.resize((w, h), Image.LANCZOS)


def scaled(layer, s):
    if abs(s - 1) < 0.004:
        return layer
    w, h = max(1, int(layer.width * s)), max(1, int(layer.height * s))
    return layer.resize((w, h), Image.BICUBIC)


# ------------------------------------------------------------------- ícones
# Desenhados em 2x e reduzidos para ter antialias.

def _canvas(w, h):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def icon_phone(h=900):
    w = int(h * 0.5)
    im, d = _canvas(w, h)
    r = int(w * 0.14)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=(30, 30, 45),
                        outline=BORDER, width=int(w * 0.03))
    m = int(w * 0.07)
    screen = vgradient(w - 2 * m, h - 2 * m, (60, 40, 170), (40, 130, 220))
    smask = Image.new("L", screen.size, 0)
    ImageDraw.Draw(smask).rounded_rectangle(
        (0, 0, screen.width - 1, screen.height - 1), int(r * 0.6), fill=255)
    im.paste(screen, (m, m), smask)
    d.rounded_rectangle((w * 0.35, m + h * 0.012, w * 0.65, m + h * 0.035),
                        20, fill=(30, 30, 45))
    logo = text_layer("KAVIX", w * 0.2, gradient=(VIOLET, SKY), hgrad=True)
    composite_center(im, logo, w / 2, h * 0.42)
    btn = rounded_box((int(w * 0.6), int(h * 0.07)), int(h * 0.02), SKY)
    composite_center(im, btn, w / 2, h * 0.62)
    lbl = text_layer("JOGAR", w * 0.07, fill=DARK)
    composite_center(im, lbl, w / 2, h * 0.62)
    return im.resize((w // 2, h // 2), Image.LANCZOS)


def icon_monitor(w=1400):
    h = int(w * 0.78)
    im, d = _canvas(w, h)
    sh = int(h * 0.75)
    d.rounded_rectangle((0, 0, w - 1, sh), int(w * 0.03), fill=(30, 30, 45),
                        outline=BORDER, width=int(w * 0.012))
    m = int(w * 0.035)
    screen = vgradient(w - 2 * m, sh - 2 * m, (40, 130, 220), (60, 40, 170))
    im.paste(screen, (m, m))
    logo = text_layer("KAVIX", w * 0.11, gradient=(VIOLET, SKY), hgrad=True)
    composite_center(im, logo, w / 2, sh * 0.42)
    btn = rounded_box((int(w * 0.28), int(sh * 0.12)), int(sh * 0.03), SKY)
    composite_center(im, btn, w / 2, sh * 0.7)
    lbl = text_layer("JOGAR", w * 0.035, fill=DARK)
    composite_center(im, lbl, w / 2, sh * 0.7)
    d.polygon([(w * 0.43, sh), (w * 0.57, sh), (w * 0.6, h * 0.95),
               (w * 0.4, h * 0.95)], fill=(50, 50, 70))
    d.rounded_rectangle((w * 0.3, h * 0.93, w * 0.7, h - 1), 12,
                        fill=(40, 38, 60), outline=BORDER, width=6)
    return im.resize((w // 2, h // 2), Image.LANCZOS)


def icon_gem(s=800):
    im, d = _canvas(s, s)
    top, mid, bot = s * 0.18, s * 0.38, s * 0.92
    l, r = s * 0.06, s * 0.94
    pts_top = [(s * 0.28, top), (s * 0.72, top), (r, mid), (l, mid)]
    d.polygon(pts_top, fill=(120, 240, 255))
    d.polygon([(l, mid), (r, mid), (s / 2, bot)], fill=(30, 150, 255))
    d.polygon([(s * 0.28, top), (s * 0.5, mid), (l, mid)], fill=(170, 250, 255))
    d.polygon([(s * 0.72, top), (r, mid), (s * 0.5, mid)], fill=(80, 200, 255))
    d.polygon([(l, mid), (s * 0.5, mid), (s / 2, bot)], fill=(60, 190, 255))
    d.polygon([(s * 0.3, mid), (s * 0.5, mid), (s / 2, bot)],
              fill=(150, 235, 255))
    d.polygon(pts_top + [pts_top[0]], outline=WHITE, width=8)
    return im.resize((s // 2, s // 2), Image.LANCZOS)


def icon_crown(s=800):
    im, d = _canvas(s, s)
    base_y, top_y = s * 0.78, s * 0.22
    pts = [(s * 0.08, base_y), (s * 0.08, s * 0.38), (s * 0.3, s * 0.56),
           (s * 0.5, top_y), (s * 0.7, s * 0.56), (s * 0.92, s * 0.38),
           (s * 0.92, base_y)]
    d.polygon(pts, fill=(255, 190, 30), outline=(255, 240, 160), width=10)
    d.rectangle((s * 0.08, base_y, s * 0.92, s * 0.9), fill=(230, 140, 0))
    for x, y, c in [(0.08, 0.36, MAGENTA), (0.5, 0.2, CYAN),
                    (0.92, 0.36, MAGENTA)]:
        d.ellipse((s * x - s * 0.06, s * y - s * 0.06, s * x + s * 0.06,
                   s * y + s * 0.06), fill=c, outline=WHITE, width=6)
    for x, c in [(0.3, (60, 220, 120)), (0.5, MAGENTA), (0.7, (60, 220, 120))]:
        d.ellipse((s * x - s * 0.045, s * 0.84 - s * 0.045, s * x + s * 0.045,
                   s * 0.84 + s * 0.045), fill=c)
    return im.resize((s // 2, s // 2), Image.LANCZOS)


def icon_star(s=800, color=(255, 210, 40)):
    im, d = _canvas(s, s)
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = s * (0.46 if i % 2 == 0 else 0.2)
        pts.append((s / 2 + rr * math.cos(a), s / 2 + rr * math.sin(a)))
    d.polygon(pts, fill=color, outline=(255, 250, 200), width=12)
    return im.resize((s // 2, s // 2), Image.LANCZOS)


def icon_trophy(s=800):
    im, d = _canvas(s, s)
    g = (255, 190, 30)
    d.ellipse((s * 0.08, s * 0.16, s * 0.36, s * 0.46), outline=g,
              width=int(s * 0.05))
    d.ellipse((s * 0.64, s * 0.16, s * 0.92, s * 0.46), outline=g,
              width=int(s * 0.05))
    d.chord((s * 0.22, -s * 0.2, s * 0.78, s * 0.62), 0, 180, fill=g)
    d.rectangle((s * 0.22, s * 0.1, s * 0.78, s * 0.21), fill=g)
    d.rectangle((s * 0.45, s * 0.6, s * 0.55, s * 0.76), fill=(230, 140, 0))
    d.rounded_rectangle((s * 0.28, s * 0.76, s * 0.72, s * 0.9), 16,
                        fill=(230, 140, 0))
    d.polygon([(s * 0.36, s * 0.2), (s * 0.42, s * 0.2), (s * 0.4, s * 0.46)],
              fill=(255, 245, 190))
    return im.resize((s // 2, s // 2), Image.LANCZOS)


def icon_chest_parts(w=1000):
    """Retorna (base, tampa) do baú."""
    h = int(w * 0.5)
    brown, dark, gold = (140, 70, 25), (90, 40, 10), (255, 190, 40)
    base, d = _canvas(w, h)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 30, fill=brown, outline=dark,
                        width=14)
    for i in range(1, 4):
        d.line((10, h * i / 4, w - 10, h * i / 4), fill=dark, width=6)
    for x in (0.12, 0.88):
        d.rectangle((w * x - w * 0.04, 0, w * x + w * 0.04, h - 1), fill=gold)
    d.rounded_rectangle((w * 0.43, -10, w * 0.57, h * 0.38), 14, fill=gold,
                        outline=(200, 120, 0), width=6)
    d.ellipse((w * 0.48, h * 0.12, w * 0.52, h * 0.2), fill=dark)

    lh = int(w * 0.32)
    lid, d = _canvas(w, lh)
    d.rounded_rectangle((0, 0, w - 1, lh * 2), int(w * 0.18), fill=brown,
                        outline=dark, width=14)
    for x in (0.12, 0.88):
        d.rectangle((w * x - w * 0.04, 0, w * x + w * 0.04, lh), fill=gold)
    d.rectangle((0, lh - 26, w, lh), fill=gold)
    return (base.resize((w // 2, h // 2), Image.LANCZOS),
            lid.resize((w // 2, lh // 2), Image.LANCZOS))


def icon_mascot(s=800, c1=(255, 222, 110), c2=(236, 84, 24)):
    """Mascote do KAVIX: bolinha com coroa e olhos de pixel."""
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    R, cx, cy = s * 0.33, s / 2, s * 0.58
    glow, d = _canvas(s, s)
    d.ellipse((cx - R * 1.3, cy - R * 1.3, cx + R * 1.3, cy + R * 1.3),
              fill=c2 + (120,))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s * 0.05)))
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    dist = np.sqrt((xx - cx + R * 0.3) ** 2 + (yy - cy + R * 0.35) ** 2) / (R * 1.7)
    dist = np.clip(dist, 0, 1)[..., None]
    rgb = np.array(c1, np.float32) * (1 - dist) + np.array(c2, np.float32) * dist
    body = Image.fromarray(np.dstack([rgb, np.full((s, s, 1), 255,
                                                   np.float32)]).astype(np.uint8))
    mask = Image.new("L", (s, s), 0)
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
    pts = [(cx - R * 0.42, top), (cx - R * 0.48, top - R * 0.36),
           (cx - R * 0.2, top - R * 0.16), (cx, top - R * 0.46),
           (cx + R * 0.2, top - R * 0.16), (cx + R * 0.48, top - R * 0.36),
           (cx + R * 0.42, top)]
    d.polygon(pts, fill=(255, 196, 40), outline=(255, 238, 150), width=6)
    return im.resize((s // 2, s // 2), Image.LANCZOS)


ICONS = {}


def icons():
    if not ICONS:
        ICONS.update(phone=icon_phone(), monitor=icon_monitor(),
                     gem=icon_gem(), crown=icon_crown(), star=icon_star(),
                     trophy=icon_trophy(), chest=icon_chest_parts(),
                     mascot=icon_mascot(),
                     mascot_green=icon_mascot(c1=(150, 255, 170), c2=(20, 160, 80)))
    return ICONS


# ------------------------------------------------------------------- fundo

class Background:
    """Fundo escuro do site com luzes roxa/ciano se movendo devagar."""

    def __init__(self, W, H, seed):
        self.W, self.H = W, H
        self.rng = random.Random(seed)
        self.base = vgradient(W, H, BG, BG2)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        v = np.clip((np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
                     - 0.4) * 2.0, 0, 1) * 170
        self.vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.vignette.putalpha(Image.fromarray(v.astype(np.uint8)))

        def blob(size, color, strength):
            g = np.mgrid[0:size, 0:size].astype(np.float32)
            r = np.sqrt((g[0] - size / 2) ** 2 + (g[1] - size / 2) ** 2) / (size / 2)
            a = np.clip(1 - r, 0, 1) ** 2.2 * strength
            im = Image.new("RGBA", (size, size), color + (0,))
            im.putalpha(Image.fromarray(a.astype(np.uint8)))
            return im
        S = int(max(W, H) * 0.95)
        self.blob_v = blob(S, VIOLET, 95)
        self.blob_s = blob(int(S * 0.85), SKY, 60)
        self.glow = blob(int(min(W, H) * 1.3), (110, 110, 255), 150)
        self.particles = [
            (self.rng.random() * W, self.rng.random() * H,
             self.rng.uniform(1.2, 3.2) * W / 1080, self.rng.uniform(15, 60),
             self.rng.random() * 6.28,
             self.rng.choice([WHITE, VIOLET, SKY]))
            for _ in range(int(50 * (W * H) / (1080 * 1920)) + 25)
        ]

    def render(self, t, rays=0.0, ray_center=None):
        W, H = self.W, self.H
        img = self.base.copy()
        composite_center(img, self.blob_v,
                         W * (0.15 + 0.1 * math.sin(t * 0.45)),
                         H * (0.2 + 0.06 * math.cos(t * 0.35)))
        composite_center(img, self.blob_s,
                         W * (0.88 + 0.08 * math.cos(t * 0.4)),
                         H * (0.82 + 0.06 * math.sin(t * 0.5)))
        if rays > 0.01:
            pulse = 0.85 + 0.15 * math.sin(t * 3)
            cx, cy = ray_center or (W / 2, H * 0.45)
            composite_center(img, set_alpha(self.glow, rays * pulse), cx, cy)
        pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(pl)
        for x, y, s, sp, ph, c in self.particles:
            yy = (y - t * sp) % H
            xx = x + math.sin(t * 0.8 + ph) * 10
            a = int(60 + 50 * math.sin(t * 2 + ph))
            d.ellipse((xx - s, yy - s, xx + s, yy + s), fill=c + (max(0, a),))
        img.alpha_composite(pl)
        return img


# ---------------------------------------------------------------- contexto

class Ctx:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.u = min(W, H) / 1080
        self.cx, self.cy = W / 2, H / 2
        self.vertical = H > W * 1.3
        self.sp = 1.45 if self.vertical else 1.0  # espaçamento vertical
        self.max_w = W * 0.9

    def y(self, off):
        return self.cy + off * self.u * self.sp


# ------------------------------------------------------------------- cenas
# Cada cena é f(img, t, dur, ctx) com t = tempo local.

def exit_alpha(t, dur, out=0.18):
    return 1 - prog(t, dur - out, dur)


def scene_lines(lines, glitch=False, stagger=0.18):
    """lines: lista de (texto, tamanho, offset_y, estilo)."""
    def f(img, t, dur, c):
        ea = exit_alpha(t, dur)
        for i, (txt, size, off, style) in enumerate(lines):
            lt = t - i * stagger
            if lt < 0:
                continue
            k = ease_out_back(lt / 0.35)
            s = lerp(2.2, 1.0, k) if lt < 0.35 else 1.0
            a = clamp01(lt / 0.12) * ea
            sz = size * c.u * s
            y = c.y(off)
            if glitch:
                draw_glitch_text(img, txt, c.cx, y, sz, t, a, max_w=c.max_w * s)
            else:
                draw_text(img, txt, c.cx, y, sz, a, max_w=c.max_w * s, **style)
    return f


# destaque = degradê do botão do site; demais = texto branco limpo
GOLD_STYLE = dict(gradient=(VIOLET, SKY), hgrad=True, glow=(70, 50, 200),
                  glow_radius=22, glow_strength=1.0)
WHITE_STYLE = dict(fill=WHITE, glow=(0, 0, 0), glow_radius=14,
                   glow_strength=1.3)
CYAN_STYLE = dict(fill=(150, 228, 255), glow=(0, 0, 0), glow_radius=12,
                  glow_strength=1.3)
PINK_STYLE = dict(fill=(206, 196, 255), glow=(0, 0, 0), glow_radius=12,
                  glow_strength=1.3)


def chip_layer(text, size, kind="dark"):
    """Etiqueta em pílula, como "FIM DE JOGO" e "+23 XP no passe" do site."""
    fg = {"dark": (228, 226, 240), "gold": XP_FG, "accent": INK,
          "outline": WHITE}[kind]
    tl = text_layer(text, size, fill=fg, path=FONT_BOLD)
    w, h = int(tl.width + size * 1.1), int(tl.height + size * 0.35)
    if kind == "accent":
        box = hgradient(w, h, VIOLET, SKY)
        box.putalpha(rounded_box((w, h), int(h * 0.3), WHITE).getchannel("A"))
    elif kind == "outline":
        box = rounded_box((w, h), int(h * 0.3), CARD + (255,),
                          outline=BORDER + (255,), width=max(2, int(size * 0.08)))
    else:
        bg = XP_BG if kind == "gold" else CHIP
        box = rounded_box((w, h), h // 2, bg + (240,))
    composite_center(box, tl, w / 2, h / 2)
    return box


def draw_chip(img, text, cx, cy, size, alpha=1.0, kind="dark", scale=1.0):
    if alpha <= 0.01:
        return
    composite_center(img, set_alpha(scaled(chip_layer(text, size, kind), scale),
                                    alpha), cx, cy)


def scene_countdown(nums=("3", "2", "1")):
    def f(img, t, dur, c):
        step = dur / len(nums)
        i = min(len(nums) - 1, int(t / step))
        lt = t - i * step
        k = ease_out_cubic(lt / (step * 0.6))
        size = lerp(900, 520, k) * c.u
        a = 1 - prog(lt, step * 0.7, step)
        # anel
        ring = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
        R = lerp(100, 700, ease_out_cubic(lt / step)) * c.u
        ImageDraw.Draw(ring).ellipse((c.cx - R, c.cy - R, c.cx + R, c.cy + R),
                                     outline=VIOLET + (int(220 * (1 - lt / step)),),
                                     width=int(14 * c.u))
        img.alpha_composite(ring)
        draw_text(img, nums[i], c.cx, c.cy, size, a, **GOLD_STYLE)
    return f


def scene_logo(tagline="JÁ DISPONÍVEL", tag_style=None):
    def f(img, t, dur, c):
        ea = exit_alpha(t, dur)
        # mascote quicando
        km = ease_out_back(t / 0.45, 2.2)
        bob = math.sin(t * 5) * 10 * c.u
        m = scaled(icons()["mascot"], 0.75 * c.u * km)
        composite_center(img, set_alpha(m, ea), c.cx, c.y(-250) + bob)
        k = ease_out_back(prog(t, 0.1, 0.5), 2.5)
        s = lerp(2.4, 1.0, k)
        size = 300 * c.u * s * (1 + 0.015 * math.sin(t * 6))
        draw_text(img, "KAVIX", c.cx, c.y(-20), size, clamp01((t - 0.1) / 0.1) * ea,
                  max_w=c.max_w * s, **GOLD_STYLE)
        if t > 0.35:
            draw_chip(img, "A R C A D E", c.cx, c.y(115), 46 * c.u,
                      clamp01((t - 0.35) / 0.15) * ea, "dark")
        if tagline:
            lt = t - 0.55
            if lt > 0:
                x = lerp(c.W * 1.2, c.cx, ease_out_cubic(lt / 0.3))
                draw_text(img, tagline, x, c.y(225), 70 * c.u, ea,
                          max_w=c.max_w, **(tag_style or CYAN_STYLE))
    return f


def scene_platforms(headline="JOGUE ONDE QUISER", sub=None):
    def f(img, t, dur, c):
        ic = icons()
        ea = exit_alpha(t, dur)
        draw_text(img, headline, c.cx, c.y(-330), 100 * c.u,
                  clamp01(t / 0.15) * ea, max_w=c.max_w, **WHITE_STYLE)
        float_ = math.sin(t * 3) * 12 * c.u
        # celular entra pela esquerda, monitor pela direita
        kp = ease_out_back(prog(t, 0.1, 0.55))
        km = ease_out_back(prog(t, 0.35, 0.8))
        px = lerp(-c.W * 0.3, c.cx - 270 * c.u, kp)
        mx = lerp(c.W * 1.3, c.cx + 170 * c.u, km)
        ph = scaled(ic["phone"], 0.95 * c.u)
        mo = scaled(ic["monitor"], 0.75 * c.u)
        iy = c.y(20)
        composite_center(img, set_alpha(mo, ea), mx, iy + float_)
        composite_center(img, set_alpha(ph, ea), px, iy + 40 * c.u - float_)
        if t > 0.8:
            a = clamp01((t - 0.8) / 0.2) * ea
            draw_text(img, "CELULAR", px, c.y(290), 60 * c.u, a, **CYAN_STYLE)
            draw_text(img, "COMPUTADOR", mx + 30 * c.u, c.y(290), 60 * c.u, a,
                      **CYAN_STYLE)
        if sub and t > 1.1:
            k = ease_out_back((t - 1.1) / 0.3)
            draw_text(img, sub, c.cx, c.y(400), 70 * c.u * lerp(1.6, 1, k),
                      clamp01((t - 1.1) / 0.1) * ea, max_w=c.max_w,
                      **GOLD_STYLE)
    return f


ITEM_KEYS = ("gem", "crown", "star", "trophy")


def scene_chest(headline="ITENS EXCLUSIVOS", open_at=0.9, top_text=None):
    def f(img, t, dur, c):
        ic = icons()
        ea = exit_alpha(t, dur)
        base, lid = ic["chest"]
        s = 1.1 * c.u
        base, lid = scaled(base, s), scaled(lid, s)
        cy = c.y(130)
        shake = 0
        if t < open_at:
            shake = math.sin(t * 60) * 10 * c.u * prog(t, 0.2, open_at)
        op = ease_out_back(prog(t, open_at, open_at + 0.35))
        # brilho interno
        if t > open_at:
            gl = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
            R = (380 + 30 * math.sin(t * 8)) * c.u * op
            ImageDraw.Draw(gl).ellipse(
                (c.cx - R, cy - R * 1.1, c.cx + R, cy + R * 0.5),
                fill=(255, 210, 90, 150))
            gl = gl.filter(ImageFilter.GaussianBlur(60 * c.u))
            img.alpha_composite(set_alpha(gl, ea))
        # itens saindo
        if t > open_at:
            for i, key in enumerate(ITEM_KEYS):
                lt = t - open_at - i * 0.08
                if lt <= 0:
                    continue
                k = ease_out_cubic(lt / 0.6)
                ang = math.radians(-150 + i * 40)
                dist = 420 * c.u * k * (1 if c.vertical else 0.85)
                x = c.cx + math.cos(ang) * dist * (1 if c.vertical else 1.3)
                y = cy - 60 * c.u + math.sin(ang) * dist * \
                    (0.9 if c.vertical else 0.45) + \
                    math.sin(t * 3 + i) * 10 * c.u
                it = scaled(ic[key], 0.55 * c.u * lerp(0.3, 1, k))
                composite_center(img, set_alpha(it, ea), x, y)
        composite_center(img, set_alpha(base, ea), c.cx + shake,
                         cy + base.height / 2)
        lid_y = cy - lid.height / 2 - op * 140 * c.u
        lid_r = op * 18
        l2 = lid.rotate(lid_r, expand=True, resample=Image.BICUBIC)
        composite_center(img, set_alpha(l2, ea), c.cx + shake - op * 40 * c.u,
                         lid_y)
        if top_text:
            draw_text(img, top_text, c.cx, c.y(-430), 70 * c.u,
                      clamp01(t / 0.15) * ea, max_w=c.max_w, **WHITE_STYLE)
        if t > open_at:
            lt = t - open_at
            k = ease_out_back(lt / 0.35)
            draw_text(img, headline, c.cx, c.y(-300),
                      115 * c.u * lerp(2, 1, k), clamp01(lt / 0.1) * ea,
                      max_w=c.max_w * lerp(2, 1, k), **GOLD_STYLE)
    return f


def scene_item_cards(labels=("EXCLUSIVO",) * 4, headline=None):
    """Mostra os itens um a um em cartas giratórias."""
    def f(img, t, dur, c):
        ic = icons()
        ea = exit_alpha(t, dur)
        n = len(ITEM_KEYS)
        step = dur / n
        i = min(n - 1, int(t / step))
        lt = t - i * step
        cw, ch = int(560 * c.u), int(760 * c.u)
        colors = [(30, 150, 255), (255, 150, 0), (255, 46, 136), (140, 60, 255)]
        col = colors[i]
        card = rounded_box((cw, ch), int(50 * c.u), (20, 10, 45, 235),
                           outline=col + (255,), width=max(2, int(10 * c.u)))
        glow = Image.new("RGBA", (cw + int(160 * c.u), ch + int(160 * c.u)),
                         (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle(
            (60 * c.u, 60 * c.u, glow.width - 60 * c.u, glow.height - 60 * c.u),
            int(60 * c.u), fill=col + (200,))
        glow = glow.filter(ImageFilter.GaussianBlur(35 * c.u))
        # flip de entrada: escala horizontal
        k = ease_out_back(lt / 0.35)
        sx = max(0.02, k)
        out = prog(lt, step - 0.12, step)
        cy = c.y(40)
        for layer in (glow, card):
            L = layer.resize((max(1, int(layer.width * sx)), layer.height),
                             Image.BICUBIC)
            composite_center(img, set_alpha(L, ea * (1 - out)), c.cx, cy)
        if sx > 0.6:
            it = scaled(ic[ITEM_KEYS[i]], 0.85 * c.u)
            bob = math.sin(t * 4) * 12 * c.u
            composite_center(img, set_alpha(it, ea * (1 - out)), c.cx,
                             cy - 70 * c.u + bob)
            draw_text(img, labels[i], c.cx, cy + 270 * c.u, 64 * c.u,
                      ea * (1 - out), max_w=cw * 0.85, fill=WHITE,
                      glow=col, glow_radius=14)
        if headline:
            draw_text(img, headline, c.cx, c.y(-430), 92 * c.u, ea,
                      max_w=c.max_w, **GOLD_STYLE)
    return f


# ----------------------------------------------------------- gameplay real

def find_clip(kind):
    """Procura gameplay/<kind>.<ext> (kind = 'celular' ou 'pc')."""
    if not os.path.isdir(GAMEPLAY_DIR):
        return None
    for f in sorted(os.listdir(GAMEPLAY_DIR)):
        base, ext = os.path.splitext(f)
        if base.lower() == kind and ext.lower() in VIDEO_EXT:
            return os.path.join(GAMEPLAY_DIR, f)
    return None


def segments(kind):
    """Trechos de cada modo de jogo, do .json gerado pelo gravar_auto.cjs."""
    clip = find_clip(kind)
    if not clip:
        return []
    try:
        with open(os.path.splitext(clip)[0] + ".json") as fh:
            data = json.load(fh)
        # o vídeo gravado sai esticado em relação ao relógio real
        real, dur = float(data.get("duracao_real", 0)), clip_duration(clip)
        k = dur / real if real > 0 and dur > 0 else 1.0
        return [(float(x["inicio"]) * k, float(x["fim"]) * k)
                for x in data.get("segmentos", [])
                if float(x["fim"]) - float(x["inicio"]) > 1.5]
    except (OSError, ValueError, KeyError, TypeError):
        return []


_library = None


def library():
    """Jogos gravados: [{"nome", "celular": (arquivo, início), "pc": (...)}].

    Usa gameplay/jogos.json (preparar_gravacoes.py) ou, na falta dele,
    gameplay/celular.* + pc.* (com os modos do gravar_auto.cjs, se houver)."""
    global _library
    if _library is not None:
        return _library
    _library = []
    mf = os.path.join(GAMEPLAY_DIR, "jogos.json")
    if os.path.exists(mf):
        with open(mf) as fh:
            for j in json.load(fh):
                cel = os.path.join(GAMEPLAY_DIR, j["celular"])
                pc = os.path.join(GAMEPLAY_DIR, j["pc"])
                if os.path.exists(cel) and os.path.exists(pc):
                    _library.append(dict(nome=j["nome"], celular=(cel, 0.0),
                                         pc=(pc, 0.0)))
    if not _library and find_clip("celular") and find_clip("pc"):
        sc, sp = segments("celular"), segments("pc")

        def st(segs, i):
            if not segs:
                return i * 6.0
            a, b = segs[i % len(segs)]
            return a + min(1.0, (b - a) * 0.2)
        for i in range(max(len(sc), len(sp), 1)):
            _library.append(dict(nome=f"MODO {i + 1}",
                                 celular=(find_clip("celular"), st(sc, i)),
                                 pc=(find_clip("pc"), st(sp, i))))
    return _library


def has_gameplay():
    return bool(library())


def at(src, frac):
    """Mesma gravação, começando em `frac` (0–1) da duração dela."""
    path, start = src
    dur = clip_duration(path)
    return path, start + max(0.0, dur - start - 2.0) * frac


def game(i, name=None):
    """Um jogo da biblioteca, pelo nome (se existir) ou pela posição."""
    lib = library()
    for g in lib:
        if name and g["nome"].lower() == name.lower():
            return g
    return lib[i % len(lib)]


def clip_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


_open_clips = []


class Clip:
    """Lê um vídeo quadro a quadro, já cortado para w x h, em loop e
    acelerado em SPEED vezes."""

    def __init__(self, path, w, h, start=0.0, fit="cover"):
        self.path, self.w, self.h, self.fit = path, int(w), int(h), fit
        dur = clip_duration(path)
        self.start = start % max(0.1, dur - 1.0) if dur > 1.5 else 0.0
        self.proc = None
        self.idx = -1
        self.img = Image.new("RGB", (self.w, self.h), (0, 0, 0))

    def _open(self):
        if self.fit == "width":
            # jogo em pé: ocupa toda a largura; sobra vira fundo escuro
            size = (f"scale={self.w}:-2,pad={self.w}:'max({self.h},ih)':0:"
                    f"'(oh-ih)*0.4':color=0x0a0617,crop={self.w}:{self.h}")
        else:
            size = (f"scale={self.w}:{self.h}:force_original_aspect_ratio="
                    f"increase,crop={self.w}:{self.h}")
        vf = f"setpts=PTS/{SPEED},fps={FPS},{size}"
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-stream_loop", "-1",
             "-ss", f"{self.start:.2f}", "-i", self.path, "-vf", vf, "-an",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE)
        _open_clips.append(self)

    def get(self, t):
        if self.proc is None:
            self._open()
        want = int(t * FPS)
        n = self.w * self.h * 3
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


_frame_cache = {}


def device_frame(kind, sw, sh):
    """Moldura de celular/monitor para uma tela sw x sh.

    Retorna (corpo, sobreposição, (x, y) da tela, máscara da tela)."""
    key = (kind, sw, sh)
    if key in _frame_cache:
        return _frame_cache[key]
    ss = 2
    if kind == "celular":
        b = int(sw * 0.045)
        W, H = sw + 2 * b, sh + 2 * b
        r = int(W * 0.13)
        body, d = _canvas(W * ss, H * ss)
        d.rounded_rectangle((0, 0, W * ss - 1, H * ss - 1), r * ss,
                            fill=(20, 20, 30), outline=(84, 76, 128),
                            width=max(2, int(W * 0.012)) * ss)
        over, d = _canvas(W * ss, H * ss)
        d.rounded_rectangle((W * 0.36 * ss, (b + sh * 0.012) * ss,
                             W * 0.64 * ss, (b + sh * 0.035) * ss),
                            sh * 0.012 * ss, fill=(10, 10, 15))
        sr = int(r * 0.75)
        pos = (b, b)
    else:
        b = int(sw * 0.025)
        stand = int(sh * 0.32)
        W, H = sw + 2 * b, sh + 2 * b + stand
        body, d = _canvas(W * ss, H * ss)
        d.polygon([(W * 0.42 * ss, (sh + 2 * b) * ss),
                   (W * 0.58 * ss, (sh + 2 * b) * ss),
                   (W * 0.61 * ss, (H - stand * 0.18) * ss),
                   (W * 0.39 * ss, (H - stand * 0.18) * ss)],
                  fill=(45, 45, 65))
        d.rounded_rectangle((W * 0.28 * ss, (H - stand * 0.22) * ss,
                             W * 0.72 * ss, H * ss - 1), 10 * ss,
                            fill=(60, 60, 85), outline=(84, 76, 128), width=3 * ss)
        d.rounded_rectangle((0, 0, W * ss - 1, (sh + 2 * b) * ss),
                            int(sw * 0.015) * ss, fill=(20, 20, 30),
                            outline=(84, 76, 128), width=max(2, int(W * 0.005)) * ss)
        over, _ = _canvas(W * ss, H * ss)
        sr = int(sw * 0.006)
        pos = (b, b)
    body = body.resize((W, H), Image.LANCZOS)
    over = over.resize((W, H), Image.LANCZOS)
    mask = rounded_box((sw, sh), max(1, sr), (255, 255, 255, 255)) \
        .getchannel("A")
    _frame_cache[key] = (body, over, pos, mask)
    return _frame_cache[key]


def device_with_clip(kind, clip, t, sw, sh):
    body, over, (x, y), mask = device_frame(kind, sw, sh)
    im = body.copy()
    scr = clip.get(t).convert("RGBA")
    scr.putalpha(mask)
    im.alpha_composite(scr, (x, y))
    im.alpha_composite(over)
    return im


def device_glow(im, color, radius):
    g = Image.new("RGBA", (im.width + 4 * radius, im.height + 4 * radius),
                  color + (0,))
    a = Image.new("L", g.size, 0)
    a.paste(im.getchannel("A"), (2 * radius, 2 * radius))
    a = a.filter(ImageFilter.GaussianBlur(radius))
    g.putalpha(a.point(lambda v: min(255, int(v * 1.4))))
    return g


def real_tag(img, c, alpha):
    """Etiqueta 'GAMEPLAY REAL 2X' no estilo das etiquetas do site."""
    if alpha <= 0:
        return
    label = "GAMEPLAY REAL" + (f" {SPEED:g}X" if SPEED != 1 else "")
    box = chip_layer("  " + label, 30 * c.u, "dark")
    if int(time_blink(img) * 2) % 2 == 0:
        dot = rounded_box((int(14 * c.u), int(14 * c.u)), int(7 * c.u),
                          SKY + (255,))
        composite_center(box, dot, 20 * c.u, box.height / 2)
    x, y = c.W - 40 * c.u, (150 if c.vertical else 40) * c.u
    composite(img, set_alpha(box, alpha), x - box.width, y)


def time_blink(img):
    return getattr(img, "_kavix_t", 0.0)


def scene_gameplay(kind, headline, sub=None, src=None):
    """Um aparelho grande mostrando a gravação real do jogo."""
    clips = {}

    def f(img, t, dur, c):
        if kind == "celular":
            sh = int(c.H * (0.54 if c.vertical else 0.56))
            sw = int(sh * 0.462)
        else:
            sw = int(min(c.W * 0.88, c.H * (0.5 if c.vertical else 0.4) * 16 / 9))
            sh = int(sw * 9 / 16)
        if "c" not in clips:
            path, start = src or game(0)[kind]
            clips["c"] = Clip(path, sw, sh, start,
                              "width" if kind == "celular" else "cover")
        ea = exit_alpha(t, dur)
        dev = device_with_clip(kind, clips["c"], t, sw, sh)
        k = ease_out_back(prog(t, 0.0, 0.45))
        s = lerp(0.4, 1.0, k) * (1 + 0.012 * math.sin(t * 2.5))
        cy = c.cy + (40 if kind == "celular" else 10) * c.u * c.sp
        glow = device_glow(dev, VIOLET if kind == "celular" else SKY,
                           int(28 * c.u))
        composite_center(img, set_alpha(scaled(glow, s), 0.8 * ea), c.cx, cy)
        composite_center(img, set_alpha(scaled(dev, s), ea), c.cx, cy)
        draw_text(img, headline, c.cx,
                  cy - dev.height * s / 2 - 85 * c.u * (1 if c.vertical else 0.6),
                  (110 if c.vertical else 80) * c.u * lerp(1.6, 1, k),
                  clamp01(t / 0.12) * ea, max_w=c.max_w, **GOLD_STYLE)
        if sub and t > 0.5:
            lt = t - 0.5
            draw_chip(img, sub, c.cx,
                      cy + dev.height * s / 2 + 70 * c.u * (1 if c.vertical else 0.55),
                      (44 if c.vertical else 34) * c.u,
                      clamp01(lt / 0.15) * ea, "dark")
        real_tag(img, c, clamp01(t / 0.2) * ea)
    return f


def scene_gameplay_both(headline="JOGUE ONDE QUISER", sub=None, srcs=None):
    """Celular e monitor lado a lado, cada um com sua gravação."""
    clips = {}

    def f(img, t, dur, c):
        if c.vertical:
            msw = int(c.W * 0.7)
        else:
            msw = int(min(c.W * 0.5, c.H * 0.4 * 16 / 9))
        msh = int(msw * 9 / 16)
        psh = int(msh * (1.25 if c.vertical else 1.15))
        psw = int(psh * 0.462)
        if not clips:
            cel, pc = srcs or (game(0)["celular"], game(2)["pc"])
            clips["pc"] = Clip(pc[0], msw, msh, pc[1])
            clips["celular"] = Clip(cel[0], psw, psh, cel[1], "width")
        ea = exit_alpha(t, dur)
        mon = device_with_clip("pc", clips["pc"], t, msw, msh)
        ph = device_with_clip("celular", clips["celular"], t, psw, psh)
        float_ = math.sin(t * 3) * 10 * c.u
        km = ease_out_back(prog(t, 0.1, 0.55))
        kp = ease_out_back(prog(t, 0.3, 0.75))
        iy = c.y(20 if c.vertical else -10)
        if c.vertical:
            mx = lerp(c.W * 1.4, c.cx + c.W * 0.1, km)
            px = lerp(-c.W * 0.4, c.cx - c.W * 0.3, kp)
            py = iy + mon.height * 0.25
        else:
            mx = lerp(c.W * 1.4, c.cx + mon.width * 0.18, km)
            px = lerp(-c.W * 0.4, c.cx - mon.width * 0.55, kp)
            py = iy + 20 * c.u
        composite_center(img, set_alpha(mon, ea), mx, iy + float_)
        composite_center(img, set_alpha(ph, ea), px, py - float_)
        top = min(iy - mon.height / 2, py - ph.height / 2)
        bottom = max(iy + mon.height / 2, py + ph.height / 2)
        draw_text(img, headline, c.cx, top - 80 * c.u,
                  (100 if c.vertical else 76) * c.u,
                  clamp01(t / 0.15) * ea, max_w=c.max_w, **WHITE_STYLE)
        if sub and t > 0.9:
            k = ease_out_back((t - 0.9) / 0.3)
            draw_chip(img, sub, c.cx, bottom + 70 * c.u,
                      (46 if c.vertical else 36) * c.u,
                      clamp01((t - 0.9) / 0.1) * ea, "accent", k)
        real_tag(img, c, clamp01(t / 0.2) * ea)
    return f


def scene_platforms_auto(headline, sub=None):
    """Usa gameplay real quando existir; senão, a arte desenhada."""
    if has_gameplay():
        return scene_gameplay_both(headline, sub)
    return scene_platforms(headline, sub)


_btn_cache = {}


def cta_button(c, text, k=1.0):
    """Botão principal do site: degradê roxo -> ciano, texto escuro."""
    key = (c.W, c.H, text, k)
    if key not in _btn_cache:
        bw, bh = int(720 * c.u * k), int(130 * c.u * k)
        mask = rounded_box((bw, bh), int(bh * 0.24), WHITE + (255,)).getchannel("A")
        btn = hgradient(bw, bh, VIOLET, SKY)
        btn.putalpha(mask)
        size = fit_size(text, 58 * c.u * k, bw * 0.8, FONT_BOLD)
        lbl = text_layer(text, size, fill=INK, path=FONT_BOLD)
        composite_center(btn, lbl, bw / 2, bh / 2)
        _btn_cache[key] = (btn, mask)
    return _btn_cache[key]


def scene_cta(headline=("CADASTRE-SE", "AGORA"),
              sub="E GANHE ITENS EXCLUSIVOS", button="Criar minha conta",
              platforms=True):
    """Tela final no formato do cartão "Fim de jogo" do site."""
    title = " ".join(headline).capitalize()
    sub = sub.lower() if sub else None

    def f(img, t, dur, c):
        k = min(1.0, c.H * 0.9 / (1080 * c.u))
        U = c.u * k
        cw, ch = int(860 * U), int(820 * U)
        cy = c.cy + (40 * c.u if c.vertical else 30 * U)
        # cartão surgindo como o modal do site
        kp = ease_out_back(t / 0.4, 1.6)
        card = rounded_box((cw, ch), int(44 * U), CARD + (245,),
                           outline=BORDER + (255,), width=max(2, int(3 * U)))
        sh = Image.new("RGBA", (cw + int(160 * U), ch + int(160 * U)), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            (80 * U, 100 * U, sh.width - 80 * U, sh.height - 60 * U), int(50 * U),
            fill=(0, 0, 0, 170))
        sh = sh.filter(ImageFilter.GaussianBlur(30 * U))
        composite_center(img, set_alpha(scaled(sh, kp), clamp01(t / 0.2)), c.cx, cy)
        composite_center(img, set_alpha(scaled(card, kp), clamp01(t / 0.15)),
                         c.cx, cy)
        top = cy - ch / 2

        def y(off):
            return top + off * U

        if t > 0.25:
            km = ease_out_back((t - 0.25) / 0.4, 2.2)
            m = scaled(icons()["mascot"], 0.5 * U * km)
            composite_center(img, m, c.cx, top - 10 * U + math.sin(t * 5) * 6 * U)
        a1 = clamp01((t - 0.3) / 0.15)
        draw_chip(img, "CADASTRO NOVO", c.cx, y(150), 32 * U, a1, "dark")
        if t > 0.35:
            kk = ease_out_back((t - 0.35) / 0.35)
            draw_text(img, title, c.cx, y(250), 92 * U * lerp(1.4, 1, kk),
                      clamp01((t - 0.35) / 0.1), max_w=cw * 0.88,
                      path=FONT_BLACK, fill=WHITE)
        if sub:
            draw_text(img, sub, c.cx, y(340), 48 * U, clamp01((t - 0.5) / 0.15),
                      max_w=cw * 0.85, path=FONT_BOLD, fill=MUTED)
        if t > 0.6:
            kk = ease_out_back((t - 0.6) / 0.35, 2.5)
            draw_chip(img, "ITENS EXCLUSIVOS NO CADASTRO", c.cx, y(430),
                      34 * U, clamp01((t - 0.6) / 0.1), "gold", kk)
        if t > 0.75:
            lt = t - 0.75
            btn, mask = cta_button(c, button, k)
            b = btn.copy()
            sx = ((lt * 0.8) % 1.4 - 0.2) * b.width
            shine = Image.new("RGBA", b.size, (0, 0, 0, 0))
            ImageDraw.Draw(shine).polygon(
                [(sx, 0), (sx + b.height * 0.5, 0),
                 (sx + b.height * 0.1, b.height), (sx - b.height * 0.4, b.height)],
                fill=(255, 255, 255, 110))
            shine.putalpha(Image.fromarray(np.minimum(
                np.asarray(shine.getchannel("A")), np.asarray(mask))))
            b.alpha_composite(shine)
            pulse = 1 + 0.035 * math.sin(lt * 7)
            kk = ease_out_back(lt / 0.35)
            by = y(560)
            rip = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
            rd = ImageDraw.Draw(rip)
            for j in range(2):
                p = ((lt * 0.9) + j * 0.5) % 1
                rw = b.width / 2 * (1 + p * 0.12)
                rh = b.height / 2 * (1 + p * 0.6)
                rd.rounded_rectangle((c.cx - rw, by - rh, c.cx + rw, by + rh),
                                     int(rh * 0.5),
                                     outline=SKY + (int(170 * (1 - p)),),
                                     width=max(2, int(4 * U)))
            img.alpha_composite(rip)
            composite_center(img, scaled(b, kk * pulse), c.cx, by)
            # toque do dedo
            hp = (lt % 1.6) / 1.6
            press = 1 - abs(math.sin(hp * math.pi * 2)) * 0.15
            hx = c.cx + b.width * 0.43
            hy = by + b.height * 0.62 + (1 - press) * 90 * U
            hr = 30 * U * press
            hand = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
            ImageDraw.Draw(hand).ellipse((hx - hr, hy - hr, hx + hr, hy + hr),
                                         fill=(255, 255, 255, 210),
                                         outline=INK + (255,),
                                         width=max(2, int(4 * U)))
            img.alpha_composite(hand)
        if t > 0.9:
            draw_chip(img, URL, c.cx, y(700), 40 * U, clamp01((t - 0.9) / 0.15),
                      "outline")
        if platforms and t > 1.1:
            draw_text(img, "Disponível no celular e no PC", c.cx,
                      cy + ch / 2 + 70 * U, 42 * U, clamp01((t - 1.1) / 0.2),
                      max_w=c.max_w, path=FONT_BOLD, fill=MUTED)
    return f


def footer(img, t, c, alpha):
    if alpha <= 0:
        return
    draw_text(img, URL, c.cx, c.H - (126 if c.vertical else 34) * c.u,
              (42 if c.vertical else 32) * c.u, alpha * 0.9, path=FONT_BOLD,
              fill=MUTED)


# ------------------------------------------------------------------- áudio

def _env(n, decay):
    return np.exp(-np.arange(n) / SR / decay)


def _noise(n, rng):
    return rng.uniform(-1, 1, n)


def _smooth(x, k):
    if k <= 1:
        return x
    return np.convolve(x, np.ones(k) / k, mode="same")


def _add(out, sig, t):
    i = int(t * SR)
    if i >= len(out):
        return
    j = min(len(out), i + len(sig))
    out[i:j] += sig[: j - i]


def sfx(kind, rng):
    if kind == "kick":
        n = int(0.4 * SR)
        tt = np.arange(n) / SR
        f = 45 + 110 * np.exp(-tt / 0.04)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.18) * 0.9
    if kind == "snare":
        n = int(0.25 * SR)
        x = _noise(n, rng)
        x = x - _smooth(x, 8)
        tone = np.sin(2 * np.pi * 190 * np.arange(n) / SR) * 0.4
        return (x * 0.6 + tone) * _env(n, 0.09) * 0.55
    if kind == "hat":
        n = int(0.06 * SR)
        x = _noise(n, rng)
        return (x - _smooth(x, 3)) * _env(n, 0.018) * 0.25
    if kind == "impact":
        n = int(1.6 * SR)
        tt = np.arange(n) / SR
        f = 30 + 90 * np.exp(-tt / 0.08)
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.5)
        nz = _smooth(_noise(n, rng), 20) * _env(n, 0.3) * 2
        return (boom + nz) * 0.9
    if kind == "whoosh":
        n = int(0.45 * SR)
        x = _noise(n, rng)
        w = np.sin(np.linspace(0, np.pi, n)) ** 2
        lo = _smooth(x, 12)
        return (x - lo) * w * 0.35 + lo * w * 0.6
    if kind == "blip":
        n = int(0.18 * SR)
        tt = np.arange(n) / SR
        return np.sign(np.sin(2 * np.pi * 880 * tt)) * _env(n, 0.05) * 0.18
    if kind == "coin":
        n1, n2 = int(0.08 * SR), int(0.35 * SR)
        a = np.sign(np.sin(2 * np.pi * 988 * np.arange(n1) / SR)) * 0.15
        b = np.sign(np.sin(2 * np.pi * 1319 * np.arange(n2) / SR)) * \
            _env(n2, 0.12) * 0.15
        return np.concatenate([a, b])
    if kind == "sparkle":
        n = int(0.8 * SR)
        out = np.zeros(n)
        for k, f in enumerate([1568, 2093, 2637, 3136, 2637, 3136]):
            m = int(0.3 * SR)
            s = np.sin(2 * np.pi * f * np.arange(m) / SR) * _env(m, 0.08) * 0.12
            i = int(k * 0.07 * SR)
            out[i:i + m] += s[: n - i]
        return out
    raise ValueError(kind)


NOTE = {"A": 55.0, "F": 43.65, "C": 65.41, "G": 49.0, "D": 73.42, "E": 41.2}
CHORDS = {"A": (0, 3, 7), "D": (0, 3, 7), "E": (0, 4, 7),
          "F": (0, 4, 7), "C": (0, 4, 7), "G": (0, 4, 7)}


def music(duration, bpm, drop, progression, events, seed):
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    bar = beat * 4

    # pad
    tt = np.arange(n) / SR
    pad = np.zeros(n)
    for b in range(int(duration / bar) + 1):
        root = progression[b % len(progression)]
        i0, i1 = int(b * bar * SR), min(n, int((b + 1) * bar * SR))
        if i0 >= n:
            break
        seg = tt[i0:i1]
        for semi in CHORDS[root]:
            f = NOTE[root] * 4 * 2 ** (semi / 12)
            pad[i0:i1] += (np.sin(2 * np.pi * f * seg) +
                           0.5 * np.sin(2 * np.pi * f * 2.003 * seg)) * 0.04
    out += pad

    # riser até o drop
    if drop > 0.3:
        m = int(drop * SR)
        r = _noise(m, rng)
        r = r - _smooth(r, 4)
        env = np.linspace(0, 1, m) ** 2.5
        sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(200, 1400, m)) / SR)
        out[:m] += (r * 0.25 + sweep * 0.08) * env

    # batida a partir do drop
    t = drop
    k = 0
    while t < duration - 0.3:
        _add(out, sfx("kick", rng), t)
        if k % 2 == 1:
            _add(out, sfx("snare", rng), t)
        _add(out, sfx("hat", rng), t + beat / 2)
        # baixo pulsando em colcheias com "sidechain"
        b = int((t - drop) / bar)
        root = progression[b % len(progression)]
        for h in (0, 0.5):
            m = int(beat / 2 * SR)
            ttt = np.arange(m) / SR
            f = NOTE[root] * 2
            saw = 2 * ((ttt * f) % 1) - 1
            saw = _smooth(saw, 6)
            env = np.minimum(1, ttt / 0.04) * _env(m, 0.2)
            _add(out, saw * env * 0.22, t + h * beat)
        # arpejo
        for q in range(4):
            semi = CHORDS[root][q % 3] + (12 if q == 3 else 0)
            f = NOTE[root] * 8 * 2 ** (semi / 12)
            m = int(beat / 4 * SR)
            ttt = np.arange(m) / SR
            sq = np.sign(np.sin(2 * np.pi * f * ttt)) * _env(m, 0.06) * 0.05
            _add(out, sq, t + q * beat / 4)
        t += beat
        k += 1

    for kind, at in events:
        _add(out, sfx(kind, rng), at)

    fade = int(0.6 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    out = np.tanh(out * 1.2)
    out /= max(1e-6, np.abs(out).max()) / 0.89
    return out


def write_wav(path, mono):
    data = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
    stereo = np.repeat(data[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


# ------------------------------------------------------------------ vídeos

def spec_hype(W, H):
    """Vídeo principal: contagem, logo, plataformas, baú, CTA."""
    bpm = 120
    scenes = [
        (0.0, 1.0, scene_lines([("PREPARADO?", 150, 0, {})], glitch=True)),
        (1.0, 2.5, scene_countdown()),
        (2.5, 5.0, scene_logo("O JOGO QUE TODO MUNDO TÁ JOGANDO")),
        (5.0, 8.0, scene_platforms_auto("JOGUE ONDE QUISER", "NO CELULAR OU NO PC")),
        (8.0, 11.0, scene_chest("ITENS EXCLUSIVOS", top_text="SÓ PRA QUEM SE CADASTRA")),
        (11.0, 16.0, scene_cta()),
    ]
    events = [("blip", 1.0), ("blip", 1.5), ("blip", 2.0), ("impact", 2.5),
              ("whoosh", 4.85), ("whoosh", 7.85), ("coin", 8.9),
              ("sparkle", 8.95), ("impact", 11.0), ("whoosh", 11.35)]
    flashes = [2.5, 8.9, 11.0]
    rays = [(2.5, 5.0), (8.9, 11.0), (11.0, 16.0)]
    return dict(dur=16.0, bpm=bpm, drop=2.5, prog="AFCG", scenes=scenes,
                events=events, flashes=flashes, rays=rays, seed=1,
                footer_from=2.5, footer_to=11.0)


def spec_plataformas(W, H):
    scenes = [
        (0.0, 1.5, scene_lines([("UM JOGO.", 150, -60, WHITE_STYLE),
                                ("DUAS TELAS.", 150, 110, GOLD_STYLE)])),
        (1.5, 4.5, scene_platforms_auto("CELULAR OU COMPUTADOR?", "VOCÊ ESCOLHE!")),
        (4.5, 6.5, scene_logo("ENTRA E JOGA")),
        (6.5, 9.0, scene_lines([("CADASTRO NOVO", 110, -80, WHITE_STYLE),
                                ("= ITENS EXCLUSIVOS", 110, 80, GOLD_STYLE)])),
        (9.0, 15.0, scene_cta(("CRIE SUA CONTA", "AGORA"))),
    ]
    events = [("whoosh", 0.0), ("whoosh", 0.18), ("impact", 1.5),
              ("whoosh", 1.6), ("whoosh", 1.85), ("impact", 4.5),
              ("coin", 6.5), ("sparkle", 6.7), ("impact", 9.0)]
    return dict(dur=15.0, bpm=124, drop=1.5, prog="FCGA", scenes=scenes,
                events=events, flashes=[1.5, 4.5, 9.0],
                rays=[(4.5, 6.5), (9.0, 15.0)], seed=2,
                footer_from=1.5, footer_to=9.0)


def spec_itens(W, H):
    scenes = [
        (0.0, 1.5, scene_lines([("ATENÇÃO,", 130, -80, WHITE_STYLE),
                                ("JOGADOR!", 170, 90, GOLD_STYLE)])),
        (1.5, 4.5, scene_chest("PRESENTE PRA VOCÊ!", open_at=1.0,
                               top_text="ABRA O BAÚ...")),
        (4.5, 8.5, scene_item_cards(("EXCLUSIVO", "EXCLUSIVO", "EXCLUSIVO",
                                     "EXCLUSIVO"),
                                    headline="ITENS EXCLUSIVOS")),
        (8.5, 10.5, scene_lines([("SÓ PRA QUEM", 120, -80, WHITE_STYLE),
                                 ("SE CADASTRAR!", 130, 80, PINK_STYLE)])),
        (10.5, 16.0, scene_cta(("GARANTA OS SEUS", "AGORA"))),
    ]
    events = [("impact", 0.0), ("whoosh", 1.5), ("coin", 2.5),
              ("sparkle", 2.55), ("whoosh", 4.5), ("coin", 4.6),
              ("whoosh", 5.5), ("coin", 5.6), ("whoosh", 6.5), ("coin", 6.6),
              ("whoosh", 7.5), ("coin", 7.6), ("impact", 8.5),
              ("impact", 10.5)]
    return dict(dur=16.0, bpm=118, drop=1.5, prog="ADFE", scenes=scenes,
                events=events, flashes=[0.0, 2.5, 8.5, 10.5],
                rays=[(2.5, 8.5), (10.5, 16.0)], seed=3,
                footer_from=1.5, footer_to=10.5)


def spec_desafio(W, H):
    """Curtinho e direto, ótimo para Stories/Reels."""
    scenes = [
        (0.0, 1.4, scene_lines([("SEUS AMIGOS", 130, -80, WHITE_STYLE),
                                ("JÁ TÃO JOGANDO...", 110, 80, CYAN_STYLE)])),
        (1.4, 2.6, scene_lines([("E VOCÊ?", 220, 0, {})], glitch=True)),
        (2.6, 4.4, scene_logo("BORA JOGAR!", PINK_STYLE)),
        (4.4, 10.0, scene_cta()),
    ]
    events = [("whoosh", 0.0), ("whoosh", 0.18), ("impact", 1.4),
              ("impact", 2.6), ("whoosh", 4.3), ("impact", 4.4),
              ("coin", 5.0)]
    return dict(dur=10.0, bpm=128, drop=1.4, prog="AFCG", scenes=scenes,
                events=events, flashes=[1.4, 2.6, 4.4],
                rays=[(2.6, 4.4), (4.4, 10.0)], seed=4,
                footer_from=0.0, footer_to=4.4)


def spec_gameplay(W, H):
    """Mostra o jogo de verdade: celular, PC, os dois, prêmios e CTA."""
    cel, pc = game(0, "Espinhos"), game(2, "Quebra Blocos")
    b1, b2 = game(9, "Cobrinha"), game(8, "Empilha")
    scenes = [
        (0.0, 1.6, scene_lines([("VEJA O KAVIX", 130, -80, WHITE_STYLE),
                                ("EM AÇÃO!", 170, 90, GOLD_STYLE)])),
        (1.6, 6.6, scene_gameplay("celular", "NO CELULAR",
                                  "JOGUE EM QUALQUER LUGAR",
                                  at(cel["celular"], 0.3))),
        (6.6, 11.6, scene_gameplay("pc", "NO COMPUTADOR", "NA TELA GRANDE",
                                   at(pc["pc"], 0.4))),
        (11.6, 14.6, scene_gameplay_both("VOCÊ ESCOLHE ONDE JOGAR",
                                         "CELULAR OU PC",
                                         (at(b1["celular"], 0.2),
                                          at(b2["pc"], 0.3)))),
        (14.6, 17.0, scene_chest("ITENS EXCLUSIVOS", open_at=0.7,
                                 top_text="CADASTRE-SE E GANHE")),
        (17.0, 22.0, scene_cta()),
    ]
    events = [("whoosh", 0.0), ("whoosh", 0.18), ("impact", 1.6),
              ("whoosh", 6.5), ("impact", 6.6), ("whoosh", 11.5),
              ("whoosh", 11.8), ("coin", 15.3), ("sparkle", 15.35),
              ("impact", 17.0), ("whoosh", 17.35)]
    return dict(dur=22.0, bpm=122, drop=1.6, prog="AFCG", scenes=scenes,
                events=events, flashes=[1.6, 6.6, 11.6, 15.3, 17.0],
                rays=[(14.6, 17.0), (17.0, 22.0)], seed=5,
                footer_from=1.6, footer_to=17.0)


def spec_arcade(W, H):
    """Montagem passando por todos os jogos, alternando celular e PC."""
    lib = library()
    per = 2.4
    scenes = [(0.0, 1.8, scene_lines([
        (TOTAL_JOGOS, 170, -80, GOLD_STYLE),
        ("NUM SÓ LUGAR!", 120, 90, WHITE_STYLE)]))]
    events = [("whoosh", 0.0), ("whoosh", 0.18)]
    flashes = []
    t = 1.8
    for i, g in enumerate(lib):
        kind = "pc" if i % 3 == 2 else "celular"
        sub = "NO PC" if kind == "pc" else "NO CELULAR"
        scenes.append((t, t + per, scene_gameplay(kind, g["nome"].upper(), sub,
                                                  at(g[kind], 0.35))))
        events += [("impact" if i == 0 else "whoosh", t), ("blip", t + 0.05)]
        flashes.append(t)
        t += per
    scenes.append((t, t + 3.0, scene_gameplay_both(
        "ESCOLHA SEU FAVORITO", "CELULAR OU PC",
        (at(game(9, "Cobrinha")["celular"], 0.1),
         at(game(2, "Quebra Blocos")["pc"], 0.7)))))
    events.append(("whoosh", t))
    flashes.append(t)
    t += 3.0
    scenes.append((t, t + 2.4, scene_chest("ITENS EXCLUSIVOS", open_at=0.7,
                                           top_text="CADASTRE-SE E GANHE")))
    events += [("coin", t + 0.7), ("sparkle", t + 0.75)]
    flashes.append(t + 0.7)
    chest = t
    t += 2.4
    scenes.append((t, t + 5.0, scene_cta()))
    events += [("impact", t), ("whoosh", t + 0.35)]
    flashes.append(t)
    return dict(dur=t + 5.0, bpm=128, drop=1.8, prog="AFCG", scenes=scenes,
                events=events, flashes=flashes,
                rays=[(chest, t), (t, t + 5.0)], seed=6,
                footer_from=1.8, footer_to=t)


def spec_destaque(nome, W, H):
    """Vídeo curto de um jogo só: celular, PC e CTA."""
    g = game(0, nome)
    seed = sum(map(ord, nome))
    scenes = [
        (0.0, 1.5, scene_lines([(nome.upper(), 170, -70, GOLD_STYLE),
                                ("JÁ JOGOU?", 120, 100, WHITE_STYLE)])),
        (1.5, 7.0, scene_gameplay("celular", nome.upper(),
                                  "QUANTOS PONTOS VOCÊ FAZ?",
                                  at(g["celular"], 0.05))),
        (7.0, 10.0, scene_gameplay("pc", "TAMBÉM NO PC", "DIRETO NO NAVEGADOR",
                                   at(g["pc"], 0.65))),
        (10.0, 15.0, scene_cta()),
    ]
    events = [("whoosh", 0.0), ("whoosh", 0.18), ("impact", 1.5),
              ("whoosh", 6.9), ("impact", 7.0), ("impact", 10.0),
              ("coin", 10.6)]
    return dict(dur=15.0, bpm=118 + seed % 12, drop=1.5,
                prog=["AFCG", "FCGA", "ADFE"][seed % 3], scenes=scenes,
                events=events, flashes=[1.5, 7.0, 10.0], rays=[(10.0, 15.0)],
                seed=seed, footer_from=1.5, footer_to=10.0)


# Vídeos que só fazem sentido com gravações reais do jogo.
NEEDS_GAMEPLAY = {"gameplay", "gameplay_feed", "gameplay_youtube",
                  "arcade", "arcade_feed", "arcade_youtube"}

VIDEOS = {
    "arcade": (spec_arcade, 1080, 1920),
    "arcade_feed": (spec_arcade, 1080, 1080),
    "arcade_youtube": (spec_arcade, 1920, 1080),
    "gameplay": (spec_gameplay, 1080, 1920),
    "gameplay_feed": (spec_gameplay, 1080, 1080),
    "gameplay_youtube": (spec_gameplay, 1920, 1080),
    # nome: (spec, largura, altura)
    "hype": (spec_hype, 1080, 1920),
    "plataformas": (spec_plataformas, 1080, 1920),
    "itens": (spec_itens, 1080, 1920),
    "desafio": (spec_desafio, 1080, 1920),
    "hype_feed": (spec_hype, 1080, 1080),
    "hype_youtube": (spec_hype, 1920, 1080),
}


# um vídeo curto de destaque para cada jogo gravado
for _g in library():
    _slug = "".join(ch if ch.isalnum() else "_" for ch in
                    unicodedata.normalize("NFKD", _g["nome"]).encode(
                        "ascii", "ignore").decode().lower())
    VIDEOS[f"destaque_{_slug}"] = (functools.partial(spec_destaque, _g["nome"]),
                                   1080, 1920)


def render(name):
    spec_fn, W, H = VIDEOS[name]
    s = spec_fn(W, H)
    c = Ctx(W, H)
    bg = Background(W, H, s["seed"])
    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, f".{name}.wav")
    out = os.path.join(OUT_DIR, f"kavix_{name}_{W}x{H}.mp4")
    write_wav(wav, music(s["dur"], s["bpm"], s["drop"], s["prog"],
                         s["events"], s["seed"]))

    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
           "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(s["dur"] * FPS)
    for fi in range(nframes):
        t = fi / FPS
        ray_a = max([clamp01((t - a) / 0.3) * (1 - prog(t, b - 0.2, b))
                     for a, b in s["rays"] if a <= t < b] or [0])
        img = bg.render(t, rays=ray_a * 0.9)
        img._kavix_t = t
        for a, b, fn in s["scenes"]:
            if a <= t < b:
                fn(img, t - a, b - a, c)
        fa = clamp01((t - s["footer_from"]) / 0.3) * \
            (1 - prog(t, s["footer_to"] - 0.2, s["footer_to"]))
        footer(img, t, c, fa)
        img.alpha_composite(bg.vignette)
        # flash + tremida nos cortes
        dx = dy = 0
        for ft in s["flashes"]:
            dt = t - ft
            if 0 <= dt < 0.25:
                a = int(255 * (1 - dt / 0.25) ** 2 * 0.85)
                img.alpha_composite(Image.new("RGBA", (W, H),
                                              (225, 220, 255, int(a * 0.55))))
            if 0 <= dt < 0.3:
                amp = 22 * c.u * (1 - dt / 0.3)
                dx = int(math.sin(dt * 90) * amp)
                dy = int(math.cos(dt * 70) * amp)
        frame = img.convert("RGB")
        if dx or dy:
            frame = frame.transform((W, H), Image.AFFINE,
                                    (1.04, 0, dx - W * 0.02, 0, 1.04,
                                     dy - H * 0.02), resample=Image.BILINEAR)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    close_clips()
    os.remove(wav)
    if proc.returncode:
        raise RuntimeError(f"ffmpeg falhou em {name}")
    return out


def main():
    names = sys.argv[1:] or list(VIDEOS)
    for n in names:
        if n not in VIDEOS:
            sys.exit(f"vídeo desconhecido: {n} (opções: {', '.join(VIDEOS)})")
    if not has_gameplay():
        skip = [n for n in names if n in NEEDS_GAMEPLAY]
        if skip:
            print(f"aviso: sem gravações em {GAMEPLAY_DIR} (celular.* e pc.*);"
                  f" pulando {', '.join(skip)}")
        names = [n for n in names if n not in NEEDS_GAMEPLAY]
    else:
        print("usando gameplay real:",
              ", ".join(g["nome"] for g in library()))
    if not names:
        return
    with Pool(min(len(names), os.cpu_count() or 1)) as pool:
        for path in pool.imap_unordered(render, names):
            print("ok:", path)


if __name__ == "__main__":
    main()
