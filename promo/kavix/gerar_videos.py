#!/usr/bin/env python3
"""Gera os vídeos promocionais do KAVIX (kavixbrasil.com.br).

Tudo é desenhado por código (Pillow + numpy) e a trilha sonora é sintetizada,
então não há direitos autorais de terceiros envolvidos.

Uso:
    python3 promo/kavix/gerar_videos.py            # gera todos
    python3 promo/kavix/gerar_videos.py hype desafio  # gera só alguns

Requer: python3, pillow, numpy e ffmpeg no PATH.
"""
import math
import os
import random
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FPS = 30
SR = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos")

URL = "kavixbrasil.com.br"

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


def text_layer(text, size, fill=WHITE, stroke=0, stroke_fill=(0, 0, 0),
               gradient=None, glow=None, glow_radius=0, path=FONT_BLACK):
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
        layer.paste(vgradient(w, h, gradient[0], gradient[1]), (0, 0), mask)
    else:
        layer.paste(fill + (255,), (0, 0, w, h), mask)
    if glow:
        a = np.asarray(outer.filter(ImageFilter.GaussianBlur(glow_radius)),
                       np.float32) * 1.8
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
    draw_text(img, text, cx - d, cy, size, alpha * 0.8, fill=(255, 40, 80))
    draw_text(img, text, cx + d, cy, size, alpha * 0.8, fill=CYAN)
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
                        outline=GOLD1, width=int(w * 0.03))
    m = int(w * 0.07)
    screen = vgradient(w - 2 * m, h - 2 * m, (90, 30, 200), (20, 160, 255))
    smask = Image.new("L", screen.size, 0)
    ImageDraw.Draw(smask).rounded_rectangle(
        (0, 0, screen.width - 1, screen.height - 1), int(r * 0.6), fill=255)
    im.paste(screen, (m, m), smask)
    d.rounded_rectangle((w * 0.35, m + h * 0.012, w * 0.65, m + h * 0.035),
                        20, fill=(30, 30, 45))
    logo = text_layer("KAVIX", w * 0.2, gradient=(GOLD1, GOLD2))
    composite_center(im, logo, w / 2, h * 0.42)
    btn = rounded_box((int(w * 0.6), int(h * 0.07)), int(h * 0.035), GOLD2)
    composite_center(im, btn, w / 2, h * 0.62)
    lbl = text_layer("JOGAR", w * 0.07, fill=DARK)
    composite_center(im, lbl, w / 2, h * 0.62)
    return im.resize((w // 2, h // 2), Image.LANCZOS)


def icon_monitor(w=1400):
    h = int(w * 0.78)
    im, d = _canvas(w, h)
    sh = int(h * 0.75)
    d.rounded_rectangle((0, 0, w - 1, sh), int(w * 0.03), fill=(30, 30, 45),
                        outline=GOLD1, width=int(w * 0.012))
    m = int(w * 0.035)
    screen = vgradient(w - 2 * m, sh - 2 * m, (20, 160, 255), (90, 30, 200))
    im.paste(screen, (m, m))
    logo = text_layer("KAVIX", w * 0.11, gradient=(GOLD1, GOLD2))
    composite_center(im, logo, w / 2, sh * 0.42)
    btn = rounded_box((int(w * 0.28), int(sh * 0.12)), int(sh * 0.06), GOLD2)
    composite_center(im, btn, w / 2, sh * 0.7)
    lbl = text_layer("JOGAR", w * 0.035, fill=DARK)
    composite_center(im, lbl, w / 2, sh * 0.7)
    d.polygon([(w * 0.43, sh), (w * 0.57, sh), (w * 0.6, h * 0.95),
               (w * 0.4, h * 0.95)], fill=(50, 50, 70))
    d.rounded_rectangle((w * 0.3, h * 0.93, w * 0.7, h - 1), 12,
                        fill=(60, 60, 85), outline=GOLD1, width=6)
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


ICONS = {}


def icons():
    if not ICONS:
        ICONS.update(phone=icon_phone(), monitor=icon_monitor(),
                     gem=icon_gem(), crown=icon_crown(), star=icon_star(),
                     trophy=icon_trophy(), chest=icon_chest_parts())
    return ICONS


# ------------------------------------------------------------------- fundo

class Background:
    def __init__(self, W, H, seed, c_top=(10, 4, 30), c_mid=(60, 14, 120),
                 grid_color=MAGENTA):
        self.W, self.H = W, H
        self.rng = random.Random(seed)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W / 2, H * 0.45
        r = np.sqrt(((xx - cx) / W) ** 2 + ((yy - cy) / H) ** 2) * 1.6
        r = np.clip(r, 0, 1)[..., None]
        top, mid = np.array(c_top, np.float32), np.array(c_mid, np.float32)
        rgb = mid * (1 - r) + top * r
        arr = np.dstack([rgb, np.full((H, W, 1), 255, np.float32)])
        self.base = Image.fromarray(arr.astype(np.uint8), "RGBA")

        # vinheta
        v = np.clip((np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
                     - 0.35) * 2.2, 0, 1) * 200
        self.vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.vignette.putalpha(Image.fromarray(v.astype(np.uint8)))

        # raios de luz (meia resolução)
        D = int(math.hypot(W, H) / 2) + 4
        rays, d = _canvas(D, D)
        n = 18
        for i in range(n):
            a0 = 2 * math.pi * i / n
            a1 = a0 + math.pi / n * 0.55
            R = D
            d.polygon([(D / 2, D / 2),
                       (D / 2 + R * math.cos(a0), D / 2 + R * math.sin(a0)),
                       (D / 2 + R * math.cos(a1), D / 2 + R * math.sin(a1))],
                      fill=(255, 210, 120, 60))
        fade = np.clip(1 - np.sqrt(((np.mgrid[0:D, 0:D][1] - D / 2) / (D / 2)) ** 2
                                   + ((np.mgrid[0:D, 0:D][0] - D / 2) / (D / 2)) ** 2),
                       0, 1)
        a = np.asarray(rays.getchannel("A"), np.float32) * fade
        rays.putalpha(Image.fromarray(a.astype(np.uint8)))
        self.rays = rays.filter(ImageFilter.GaussianBlur(3))

        # partículas
        self.particles = [
            (self.rng.random() * W, self.rng.random() * H,
             self.rng.uniform(1.5, 5) * W / 1080, self.rng.uniform(40, 180),
             self.rng.random() * 6.28,
             self.rng.choice([CYAN, GOLD1, MAGENTA, WHITE]))
            for _ in range(int(140 * (W * H) / (1080 * 1920)) + 60)
        ]

        # grade estilo synthwave
        self.horizon = int(H * (0.66 if H > W else 0.7))
        gh = H - self.horizon
        g = np.linspace(0, 1, gh, dtype=np.float32) ** 0.8 * 255
        self.grid_fade = Image.fromarray(
            np.repeat(g[:, None], W, axis=1).astype(np.uint8))
        self.grid_color = grid_color

    def render(self, t, rays=0.0, ray_center=None):
        W, H = self.W, self.H
        img = self.base.copy()

        # grade
        gh = H - self.horizon
        grid = Image.new("RGBA", (W, gh), (0, 0, 0, 0))
        d = ImageDraw.Draw(grid)
        col = self.grid_color
        phase = (t * 0.9) % 1
        N = 14
        for i in range(N):
            p = ((i + phase) / N) ** 2.3
            y = p * gh
            d.line((0, y, W, y), fill=col + (90,), width=max(1, int(3 * p + 1)))
        for j in range(-16, 17):
            x0 = W / 2 + j * W * 0.035
            x1 = W / 2 + j * W * 0.3
            d.line((x0, 0, x1, gh), fill=col + (80,), width=2)
        a = np.asarray(grid.getchannel("A"), np.float32) * \
            np.asarray(self.grid_fade, np.float32) / 255
        grid.putalpha(Image.fromarray(a.astype(np.uint8)))
        composite(img, grid, 0, self.horizon)
        # brilho do horizonte
        hl = Image.new("RGBA", (W, int(H * 0.05)), col + (0,))
        ha = np.abs(np.linspace(-1, 1, hl.height, dtype=np.float32))
        ha = np.repeat(((1 - ha) ** 2 * 120)[:, None], W, axis=1)
        hl.putalpha(Image.fromarray(ha.astype(np.uint8)))
        composite(img, hl, 0, self.horizon - hl.height / 2)

        # raios
        if rays > 0.01:
            r = self.rays.rotate(t * 12, resample=Image.BILINEAR)
            r = r.resize((r.width * 2, r.height * 2), Image.BILINEAR)
            r = set_alpha(r, rays)
            cx, cy = ray_center or (W / 2, H * 0.45)
            composite_center(img, r, cx, cy)

        # partículas
        pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(pl)
        for x, y, s, sp, ph, c in self.particles:
            yy = (y - t * sp) % H
            xx = x + math.sin(t * 1.3 + ph) * 12
            a = int(120 + 120 * math.sin(t * 4 + ph))
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


GOLD_STYLE = dict(gradient=(GOLD1, GOLD2), stroke=6, stroke_fill=(60, 20, 0),
                  glow=(255, 150, 0), glow_radius=18)
WHITE_STYLE = dict(fill=WHITE, stroke=4, stroke_fill=(20, 0, 50),
                   glow=PURPLE, glow_radius=16)
CYAN_STYLE = dict(fill=CYAN, stroke=4, stroke_fill=(0, 20, 50),
                  glow=(0, 120, 255), glow_radius=16)
PINK_STYLE = dict(fill=WHITE, stroke=4, stroke_fill=(60, 0, 30),
                  glow=MAGENTA, glow_radius=18)


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
                                     outline=CYAN + (int(220 * (1 - lt / step)),),
                                     width=int(14 * c.u))
        img.alpha_composite(ring)
        draw_text(img, nums[i], c.cx, c.cy, size, a, **GOLD_STYLE)
    return f


def scene_logo(tagline="JÁ DISPONÍVEL", tag_style=None):
    def f(img, t, dur, c):
        ea = exit_alpha(t, dur)
        k = ease_out_back(t / 0.4, 2.5)
        s = lerp(3.0, 1.0, k)
        breathe = 1 + 0.02 * math.sin(t * 6)
        size = 330 * c.u * s * breathe
        draw_text(img, "KAVIX", c.cx, c.y(-40), size, clamp01(t / 0.1) * ea,
                  max_w=c.max_w * s, **GOLD_STYLE)
        if tagline:
            lt = t - 0.45
            if lt > 0:
                x = lerp(c.W * 1.2, c.cx, ease_out_cubic(lt / 0.3))
                draw_text(img, tagline, x, c.y(170), 80 * c.u, ea,
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


_btn_cache = {}


def cta_button(c, text):
    key = (c.W, c.H, text)
    if key not in _btn_cache:
        bw, bh = int(860 * c.u), int(170 * c.u)
        mask = rounded_box((bw, bh), bh // 2, (255, 255, 255, 255)).getchannel("A")
        btn = vgradient(bw, bh, (255, 220, 80), (255, 110, 0))
        btn.putalpha(mask)
        size = fit_size(text, 82 * c.u, bw * 0.86)
        lbl = text_layer(text, size, fill=(40, 10, 0))
        composite_center(btn, lbl, bw / 2, bh / 2)
        _btn_cache[key] = (btn, mask)
    return _btn_cache[key]


def scene_cta(headline=("CADASTRE-SE", "AGORA"),
              sub="E GANHE ITENS EXCLUSIVOS", button="CADASTRE-SE GRÁTIS",
              platforms=True):
    def f(img, t, dur, c):
        # título
        for i, line in enumerate(headline):
            lt = t - i * 0.15
            if lt < 0:
                continue
            k = ease_out_back(lt / 0.35)
            draw_text(img, line, c.cx, c.y(-400 + i * 140),
                      150 * c.u * lerp(2, 1, k), clamp01(lt / 0.1),
                      max_w=c.max_w * lerp(2, 1, k),
                      **(GOLD_STYLE if i == len(headline) - 1 else WHITE_STYLE))
        if sub and t > 0.4:
            lt = t - 0.4
            x = lerp(-c.W * 0.5, c.cx, ease_out_cubic(lt / 0.3))
            draw_text(img, sub, x, c.y(-110), 66 * c.u, 1.0, max_w=c.max_w,
                      **PINK_STYLE)
        # botão pulsando + brilho passando
        if t > 0.6:
            lt = t - 0.6
            btn, mask = cta_button(c, button)
            b = btn.copy()
            sx = ((lt * 0.8) % 1.4 - 0.2) * b.width
            shine = Image.new("RGBA", b.size, (0, 0, 0, 0))
            ImageDraw.Draw(shine).polygon(
                [(sx, 0), (sx + b.height * 0.5, 0),
                 (sx + b.height * 0.1, b.height), (sx - b.height * 0.4, b.height)],
                fill=(255, 255, 255, 140))
            sa = np.minimum(np.asarray(shine.getchannel("A")),
                            np.asarray(mask))
            shine.putalpha(Image.fromarray(sa))
            b.alpha_composite(shine)
            pulse = 1 + 0.045 * math.sin(lt * 7)
            k = ease_out_back(lt / 0.35)
            by = c.y(90)
            # ondas de toque
            rip = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
            rd = ImageDraw.Draw(rip)
            for j in range(2):
                p = ((lt * 0.9) + j * 0.5) % 1
                rw = b.width / 2 * (1 + p * 0.35)
                rh = b.height / 2 * (1 + p * 1.0)
                rd.rounded_rectangle((c.cx - rw, by - rh, c.cx + rw, by + rh),
                                     rh, outline=GOLD1 + (int(200 * (1 - p)),),
                                     width=max(2, int(6 * c.u)))
            img.alpha_composite(rip)
            composite_center(img, scaled(b, k * pulse), c.cx, by)
            # mãozinha tocando
            hand_p = (lt % 1.6) / 1.6
            press = 1 - abs(math.sin(hand_p * math.pi * 2)) * 0.12
            hx = c.cx + b.width * 0.32
            hy = by + b.height * 0.55 + (1 - press) * 120 * c.u
            hr = 34 * c.u * press
            hand = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0))
            ImageDraw.Draw(hand).ellipse((hx - hr, hy - hr, hx + hr, hy + hr),
                                         fill=(255, 255, 255, 200),
                                         outline=(40, 10, 60, 255),
                                         width=max(2, int(5 * c.u)))
            img.alpha_composite(hand)
        # URL
        if t > 0.9:
            lt = t - 0.9
            k = ease_out_back(lt / 0.3)
            draw_text(img, URL, c.cx, c.y(260), 74 * c.u * lerp(1.5, 1, k),
                      clamp01(lt / 0.1), max_w=c.max_w, **CYAN_STYLE)
        if platforms and t > 1.2:
            a = clamp01((t - 1.2) / 0.25)
            draw_text(img, "DISPONÍVEL NO CELULAR E NO PC", c.cx, c.y(370),
                      52 * c.u, a, max_w=c.max_w, path=FONT_BOLD,
                      fill=WHITE, stroke=3, stroke_fill=(20, 0, 50))
            if not c.vertical:
                return
            ic = icons()
            ph = scaled(ic["phone"], 0.2 * c.u)
            mo = scaled(ic["monitor"], 0.16 * c.u)
            composite_center(img, set_alpha(ph, a), c.cx - 70 * c.u, c.y(470))
            composite_center(img, set_alpha(mo, a), c.cx + 70 * c.u, c.y(470))
    return f


def footer(img, t, c, alpha):
    if alpha <= 0:
        return
    draw_text(img, URL, c.cx, c.H - (126 if c.vertical else 34) * c.u,
              (44 if c.vertical else 34) * c.u, alpha * 0.9, path=FONT_BOLD, fill=WHITE, stroke=3,
              stroke_fill=(20, 0, 50))


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
        (5.0, 8.0, scene_platforms("JOGUE ONDE QUISER", "NO CELULAR OU NO PC")),
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
        (1.5, 4.5, scene_platforms("CELULAR OU COMPUTADOR?", "VOCÊ ESCOLHE!")),
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


VIDEOS = {
    # nome: (spec, largura, altura)
    "hype": (spec_hype, 1080, 1920),
    "plataformas": (spec_plataformas, 1080, 1920),
    "itens": (spec_itens, 1080, 1920),
    "desafio": (spec_desafio, 1080, 1920),
    "hype_feed": (spec_hype, 1080, 1080),
    "hype_youtube": (spec_hype, 1920, 1080),
}


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
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, a)))
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
    os.remove(wav)
    if proc.returncode:
        raise RuntimeError(f"ffmpeg falhou em {name}")
    return out


def main():
    names = sys.argv[1:] or list(VIDEOS)
    for n in names:
        if n not in VIDEOS:
            sys.exit(f"vídeo desconhecido: {n} (opções: {', '.join(VIDEOS)})")
    with Pool(min(len(names), os.cpu_count() or 1)) as pool:
        for path in pool.imap_unordered(render, names):
            print("ok:", path)


if __name__ == "__main__":
    main()
