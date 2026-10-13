#!/usr/bin/env python3
"""Vídeo-convite para grupos do Facebook: mostra tudo do KAVIX ARCADE em ~45s
(30 jogos, batalha online, ranking e competitivo com patentes, passe de batalha,
recompensas diárias, skins, celular e PC) e termina chamando para jogar.

Uso:  python3 promo/kavix/video_grupo.py
Saída: grupo_facebook/kavix_convite_grupo.mp4 + legenda.txt
"""
import math
import os

import carrossel as C
import gerar_videos as g
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "grupo_facebook")
W, H = 1080, 1920
cap = lambda t0, t1, s, y=0.38, hl=(), size=1.0: (t0, t1, "cap", s, {"y": y, "hl": hl, "size": size})  # noqa
label = lambda t0, t1, s, y=0.3, size=58, rot=-3, bg=g.WHITE: (t0, t1, "label", s, {"y": y, "size": size, "rot": rot, "bg": bg})  # noqa


def cel(nome, frac=0.4):
    return g.at(g.game(0, nome)["celular"], frac)


def pc(nome, frac=0.5):
    return g.at(g.game(0, nome)["pc"], frac)


# --------------------------------------------------------------- artes

def arte_diarias():
    """Recompensas diárias: faixa de 7 dias (sem inventar itens específicos)."""
    im = C.fundo(200, (255, 206, 64), C.VIOLET)
    C.sticker(im, "RECOMPENSA DIÁRIA", W / 2, 230, 56, -3, (255, 206, 64), C.INK)
    C.titulo(im, "volta todo dia e ganha mais 🎁", 400, 80, hl=(3, 4))
    for k in range(7):
        r, q = divmod(k, 4)
        n_col = 4 if r == 0 else 3
        x = W / 2 + (q - (n_col - 1) / 2) * 240
        y = 680 + r * 330
        big = k == 6
        cw, ch = (220, 290)
        col = (255, 206, 64) if big else ((198, 255, 61) if k < 3 else (255, 255, 255))
        card = g.rounded((cw, ch), 34, (255, 255, 255, 40 if big else 26),
                         outline=col + (220,), width=5 if big else 3)
        e = g.emoji_layer("🎁" if k < 6 else "👑", 120 if big else 96)
        card.alpha_composite(e, ((cw - e.width) // 2, 70 if big else 80))
        d = g.text_layer(f"DIA {k + 1}", 34, fill=C.WHITE, path=g.F_DISPLAY)
        card.alpha_composite(d, ((cw - d.width) // 2, 16))
        if k < 3:
            ok = g.emoji_layer("✅", 46)
            card.alpha_composite(ok, ((cw - ok.width) // 2, ch - 70))
        C.put(im, card, x, y)
    C.texto(im, "quanto mais dias seguidos, melhor o prêmio 🔥", W / 2, 1210, 36,
            C.WHITE, g.F_BOLD, True)
    return im


def arte_batalha():
    """Card 'batalha online' com duas bolinhas frente a frente."""
    im = C.fundo(201, (255, 90, 110), C.SKY)
    C.sticker(im, "⚔️ BATALHA ONLINE", W / 2, 260, 60, -3, (255, 90, 110), C.WHITE)
    C.titulo(im, "desafia teus amigos ao vivo", 430, 80, hl=(2, 3, 4))
    a = g.mascot(420, (255, 222, 110), (236, 84, 24))
    b = g.mascot(420, (150, 230, 255), (40, 90, 230)).transpose(Image.FLIP_LEFT_RIGHT)
    C.put(im, a, 290, 830)
    C.put(im, b, 790, 830)
    C.put(im, g.sticker("VS", 80, "brand", C.INK, g.F_DISPLAY), W / 2, 830)
    C.sticker(im, "VOCÊ", 290, 1080, 44, -4, C.LIME, C.INK)
    C.sticker(im, "TEU AMIGO", 790, 1080, 44, 4, C.WHITE, C.INK)
    return im


def arte(slide):
    """Abre um slide pronto dos carrosséis."""
    im = Image.open(os.path.join(C.OUT, slide)).convert("RGBA")
    return im.crop((0, 140, im.width, im.height - 120))  # sem cabeçalho/contador do carrossel


# --------------------------------------------------------------- cenas

def sc_image(img, texts=(), zoom=0.06):
    """Imagem (arte 4:5) dentro do vídeo 9:16, com zoom lento e fundo desfocado."""
    src = img.convert("RGBA")

    def f(im, t, dur, c):
        bg = src.resize((c.W // 12, c.H // 12)).filter(ImageFilter.GaussianBlur(2))
        im.alpha_composite(bg.resize((c.W, c.H)))
        im.alpha_composite(Image.new("RGBA", (c.W, c.H), (6, 5, 16, 140)))
        k = g.spring(t / 0.5)
        w = int(c.W * 0.92 * (1 + zoom * t / dur))
        card = src.resize((w, int(w * src.height / src.width)), Image.BILINEAR)
        card.putalpha(g.rounded(card.size, 40, g.WHITE).getchannel("A"))
        g.put(im, g.shadow(card.size, 40, 30, 160), c.cx, c.Y(0.5) + 14)
        g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.85, 1, k)), g.clamp01(t / 0.15)),
              c.cx, c.Y(0.5))
        im.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(im, c)
        g.draw_texts(im, c, t, texts)
    return f


def sc_duelo(a, b, texts=()):
    """Tela dividida VOCÊ x TEU AMIGO com jogabilidade real."""
    st = {}

    def f(im, t, dur, c):
        h2 = c.H // 2
        if not st:
            st["a"] = g.Clip(a[0], c.W, h2, a[1], g.HEADER_PX)
            st["b"] = g.Clip(b[0], c.W, h2, b[1], g.HEADER_PX)
        im.alpha_composite(st["a"].get(t).convert("RGBA"), (0, 0))
        im.alpha_composite(st["b"].get(t).convert("RGBA"), (0, h2))
        ImageDraw.Draw(im).rectangle((0, h2 - 5, c.W, h2 + 5), fill=(255, 255, 255, 255))
        im.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(im, c)
        g.draw_sticker(im, "VOCÊ", c.text_cx, h2 * 0.42 + c.top_off * 0.4, 60, t, -4,
                       g.LIME, g.INK, path=g.F_DISPLAY)
        g.draw_sticker(im, "TEU AMIGO", c.text_cx, h2 + h2 * 0.18, 60, t - 0.2, 4,
                       g.WHITE, g.INK, path=g.F_DISPLAY)
        if t > 0.3:
            g.put(im, g.scaled(g.sticker("VS", 70, "brand", g.INK, g.F_DISPLAY),
                               g.spring((t - 0.3) / 0.4)), c.cx, h2)
        g.draw_texts(im, c, t, texts)
    return f


# --------------------------------------------------------------- roteiro

def roteiro():
    jogos = [x["nome"] for x in g.library()]
    sc = [
        (3.2, g.sc_game(cel("Espinhos", 0.3), texts=[
            cap(0.1, 3.2, "procurando jogo pra jogar no celular ou no PC? 👀", 0.4, (4, 7))])),
        (2.4, g.sc_game(cel("Empilha", 0.4), texts=[
            label(0.0, 2.4, "30 JOGOS", 0.32, 80, -5, g.LIME),
            cap(0.2, 2.4, "num site só 🎮", 0.46, (2,))])),
    ]
    for k, nome in enumerate(["Cobrinha", "Bolhas", "Quebra Blocos", "Hélice", "Boliche",
                              "Gravidade", "Trampolim", "Pulso"]):
        sc.append((0.8, g.sc_game(cel(nome, 0.5), name=nome, texts=[
            label(0, 0.8, f"#{k + 2}", 0.7, 44, 4, g.LIME)])))
    sc += [
        (3.6, sc_duelo(cel("Reflexo", 0.3), g.at(g.game(0, "Reflexo")["celular"], 0.7), texts=[
            cap(0.3, 3.6, "⚔️ batalha online contra teus amigos", 0.75, (1, 2), 0.85)])),
        (2.8, sc_image(arte_batalha())),
        (3.6, sc_image(arte("modelo_6_ranking_competitivo/slide_02.jpg"), texts=[
            cap(0.2, 3.6, "modo competitivo com patentes 💎", 0.86, (3, 4), 0.8)])),
        (3.6, sc_image(arte("modelo_7_desafio_do_recorde/slide_03.jpg"), texts=[
            cap(0.2, 3.6, "ranking geral e de cada jogo 🏆", 0.86, (1,), 0.8)])),
        (3.6, sc_image(arte("modelo_5_passe_de_batalha/slide_02.jpg"), texts=[
            cap(0.2, 3.6, "passe de batalha com itens raros 🎫", 0.86, (4, 5), 0.8)])),
        (3.4, sc_image(arte_diarias(), texts=[
            cap(0.2, 3.4, "recompensas todo dia 🎁", 0.86, (1, 2), 0.85)])),
        (3.2, g.sc_skin_reveal(cel("Órbita", 0.3), [C.skin("Mago"), C.skin("Coroa Suprema"),
                                                    C.skin("Aura Cosmos")], texts=[
            cap(0.0, 3.2, "+90 skins pra tua bolinha ✨", 0.19, (0,), 0.8)])),
        (3.2, g.sc_collage(cel("Cobrinha", 0.2), pc("Quebra Blocos", 0.4), texts=[
            cap(0.2, 3.2, "celular ou PC, sem baixar nada 🙌", 0.72, (3, 4), 0.85)])),
        (3.0, g.sc_game(cel("Memória", 0.5), texts=[
            cap(0.1, 3.0, "comenta teu nick que a gente se desafia 👇", 0.4, (1, 2))])),
        (5.5, g.sc_cta(cel("Espinhos", 0.6), "Vem jogar com a gente", "Jogar agora")),
    ]
    extra = [("pop", 5.6 + 0.8 * k) for k in range(8)]
    s = g.build(sc, bpm=140, prog_="AFCG", seed=777, extra=extra)
    s["accent"] = g.LIME
    return s


LEGENDA = """🎮 Galera, bora jogar junto? Conheçam o KAVIX ARCADE!

São 30 jogos rápidos pra jogar no celular ou no PC, direto no navegador, sem baixar nada:

⚔️ Batalha online contra os amigos
🏆 Ranking geral e de cada jogo
💎 Modo competitivo com patentes (Diamante, Rubi, Esmeralda, Safira e Ouro)
🎫 Passe de batalha com itens raros
🎁 Recompensas todo dia
✨ +90 skins pra montar tua bolinha

Quem criar conta agora ganha itens exclusivos 🎁

👉 kavixbrasil.com.br

Comenta aqui teu nick no jogo que a gente se desafia 👇 Quem chegar primeiro no Diamante? 💎

#kavix #kavixarcade #jogosonline #jogosgratis #gamerbrasil"""


def main():
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, "kavix_convite_grupo.mp4")
    g.render_spec(roteiro(), W, H, "reels", out)
    with open(os.path.join(OUT, "legenda.txt"), "w") as fh:
        fh.write(LEGENDA + "\n")
    print("ok:", out)


if __name__ == "__main__":
    main()
