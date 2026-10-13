#!/usr/bin/env python3
"""Thumbnail (capa) do vídeo-convite do grupo do Facebook, 1920x1080.

Uso:  python3 promo/kavix/thumb_grupo.py
Saída: grupo_facebook/thumbnail.jpg (+ thumbnail_1280x720.jpg)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

import carrossel as C
import gerar_videos as g

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "grupo_facebook")
W, H = 1920, 1080
PINK = (255, 70, 140)
GOLD = (255, 206, 64)


def raios(cx, cy):
    """Fundo com raios de explosão (estilo capa de vídeo de jogo)."""
    im = Image.new("RGBA", (W, H), (20, 8, 48, 255))
    d = ImageDraw.Draw(im)
    R = 2600
    n = 28
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 0.5) / n
        cor = (88, 40, 190, 255) if k % 2 else (46, 22, 120, 255)
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                   (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=cor)
    # brilho central e vinheta
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - 520, cy - 520, cx + 520, cy + 520), fill=g.SKY + (150,))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(170)))
    vin = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vin).ellipse((-W * .25, -H * .35, W * 1.25, H * 1.35), fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGBA", (W, H), (6, 4, 18, 255))
    dark.putalpha(Image.eval(vin, lambda v: 255 - v))
    im.alpha_composite(dark)
    return im


def celular(nome, h, rot):
    shot = Image.open(os.path.join(C.OUT, "prints", nome + ".jpg")).convert("RGBA")
    shot = shot.crop((0, 72, shot.width, shot.height))  # tira a barra do nome
    w = int(h * 9 / 16)
    shot = shot.resize((w, int(w * shot.height / shot.width)), Image.LANCZOS).crop((0, 0, w, h))
    b, r = 12, 46
    shot.putalpha(g.rounded((w, h), r, g.WHITE).getchannel("A"))
    ring = g.rounded((w + 2 * b, h + 2 * b), r + b, g.WHITE + (255,))
    ring.alpha_composite(shot, (b, b))
    out = g.shadow(ring.size, r, 34, 200)
    p = (out.width - ring.width) // 2
    out.alpha_composite(ring, (p, p - 10))
    return out.rotate(rot, expand=True, resample=Image.BICUBIC)


def texto_grande(s, size, cor, rot=0, stroke=None):
    lay = g.text_layer(s, size, fill=cor, path=g.F_DISPLAY, stroke=stroke or int(size * .09),
                       stroke_fill=(12, 6, 30), shadow_a=220)
    return lay.rotate(rot, expand=True, resample=Image.BICUBIC)


def selo(s, size, bg, fg, rot):
    return g.sticker(s, size, bg, fg, g.F_DISPLAY).rotate(rot, expand=True,
                                                         resample=Image.BICUBIC)


def skin(nome, s):
    im = Image.open(os.path.join(HERE, "gameplay", "skins", nome + ".png")).convert("RGBA")
    return im.resize((s, int(s * im.height / im.width)), Image.LANCZOS)


def main():
    im = raios(1400, 540)

    # leque de jogos à direita
    for nome, x, y, h, rot in (("cobrinha", 1150, 600, 600, 15), ("trampolim", 1790, 610, 600, -15),
                               ("helice", 1290, 570, 700, 8), ("bolhas", 1640, 575, 700, -8),
                               ("empilha", 1465, 545, 800, 0)):
        g.put(im, celular(nome, h, rot), x, y)

    # gema de patente, troféu e skins flutuando
    gm = C.gema((150, 230, 255), (60, 120, 255), 230).rotate(-12, expand=True,
                                                            resample=Image.BICUBIC)
    g.put(im, gm, 1820, 170)
    g.put(im, g.emoji_layer("🏆", 170).rotate(10, expand=True, resample=Image.BICUBIC), 1030, 930)
    g.put(im, g.emoji_layer("🎁", 150).rotate(-10, expand=True, resample=Image.BICUBIC), 1830, 940)

    # selos de recursos sobre o leque
    g.put(im, selo("⚔️ BATALHA ONLINE", 46, PINK, g.WHITE, 6), 1260, 120)
    g.put(im, selo("💎 RANKED", 46, g.SKY, g.INK, -5), 1720, 330)
    g.put(im, selo("🎁 ITENS GRÁTIS", 46, GOLD, g.INK, 4), 1600, 905)

    # sombra à esquerda para o texto saltar
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((-500, -200, 1000, 1300), fill=(6, 3, 20, 190))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(120)))

    # logo
    lg = g.logo_image(200, 0.24)
    g.put(im, g.shadow(lg.size, 48, 26, 190), 170, 150 + 10)
    g.put(im, lg, 170, 150)
    g.put(im, g.text_layer("KAVIX ARCADE", 52, path=g.F_DISPLAY, shadow_a=200), 470, 150)

    # texto principal
    g.put(im, texto_grande("30 JOGOS", 128, g.LIME, 4), 470, 390)
    g.put(im, selo("GRÁTIS", 110, PINK, g.WHITE, -4), 440, 590)
    sub = g.text_layer("no celular e no PC", 64, fill=g.WHITE, path=g.F_DISPLAY,
                       stroke=6, stroke_fill=(12, 6, 30), shadow_a=200)
    g.put(im, sub, 440, 770)
    g.put(im, selo("👉 SEM BAIXAR NADA", 44, g.WHITE, g.INK, 3), 430, 905)

    os.makedirs(OUT, exist_ok=True)
    rgb = im.convert("RGB")
    rgb.save(os.path.join(OUT, "thumbnail.jpg"), quality=92)
    rgb.resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, "thumbnail_1280x720.jpg"),
                                                quality=92)
    print("ok")


def raios_duplo():
    """Fundo dividido na diagonal: lado rosa (você) x lado ciano (o desafio)."""
    a = raios(420, 560)
    b = raios(1500, 540)
    tint_a = Image.new("RGBA", (W, H), PINK + (90,))
    tint_b = Image.new("RGBA", (W, H), g.SKY + (60,))
    a.alpha_composite(tint_a)
    b.alpha_composite(tint_b)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([(760, 0), (W, 0), (W, H), (560, H)], fill=255)
    a.paste(b, (0, 0), m)
    d = ImageDraw.Draw(a)
    d.line([(760, 0), (560, H)], fill=(255, 255, 255, 255), width=10)
    return a


def main_v2():
    """Versão 2: desafio do recorde."""
    im = raios_duplo()

    # jogos do lado esquerdo
    for nome, x, y, h, rot in (("bolhas", 200, 600, 640, 10), ("helice", 560, 620, 640, -9),
                               ("empilha", 380, 560, 760, 0)):
        g.put(im, celular(nome, h, rot), x, y)
    g.put(im, g.emoji_layer("🔥", 150).rotate(12, expand=True, resample=Image.BICUBIC), 110, 170)

    # VS no corte
    g.put(im, selo("VS", 110, "brand", g.WHITE, -6), 680, 560)

    # texto do desafio
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((820, -150, 2300, 1250), fill=(6, 3, 20, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(120)))
    g.put(im, texto_grande("DUVIDO TU", 92, g.WHITE, 3), 1360, 150)
    g.put(im, texto_grande("BATER MEU", 92, g.WHITE, 3), 1360, 275)
    g.put(im, texto_grande("RECORDE", 150, GOLD, 3), 1350, 430)

    # cartão do recorde
    cw, ch = 820, 230
    card = g.rounded((cw, ch), 56, (14, 10, 36, 235), outline=GOLD + (255,), width=8)
    tr = g.emoji_layer("🏆", 150)
    card.alpha_composite(tr, (40, (ch - tr.height) // 2))
    n = g.text_layer("2.428", 130, fill=g.LIME, path=g.F_DISPLAY, shadow_a=180)
    card.alpha_composite(n, (220, (ch - n.height) // 2 - 6))
    pts = g.text_layer("pts", 44, fill=g.WHITE, path=g.F_DISPLAY)
    card.alpha_composite(pts, (min(cw - pts.width - 30, 220 + n.width - 20), ch - pts.height - 42))
    card = card.rotate(-3, expand=True, resample=Image.BICUBIC)
    sc = g.shadow(card.size, 56, 30, 200)
    p = (sc.width - card.width) // 2
    sc.alpha_composite(card, (p, p - 10))
    g.put(im, sc, 1320, 680)

    # gema e selo ranked
    gm = C.gema((150, 230, 255), (60, 120, 255), 200).rotate(14, expand=True,
                                                            resample=Image.BICUBIC)
    g.put(im, gm, 1790, 600)
    g.put(im, selo("💎 RANKED", 42, g.SKY, g.INK, 6), 1740, 800)

    # faixa inferior
    g.put(im, selo("🎮 30 JOGOS GRÁTIS • CELULAR E PC", 46, g.LIME, g.INK, -2), 1340, 930)

    # logo
    lg = g.logo_image(150, 0.24)
    g.put(im, g.shadow(lg.size, 36, 22, 190), 1820, 110)
    g.put(im, lg, 1820, 100)

    rgb = im.convert("RGB")
    rgb.save(os.path.join(OUT, "thumbnail_v2.jpg"), quality=92)
    rgb.resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, "thumbnail_v2_1280x720.jpg"),
                                                quality=92)
    print("ok v2")


if __name__ == "__main__":
    import sys
    main_v2() if "v2" in sys.argv[1:] else main()
