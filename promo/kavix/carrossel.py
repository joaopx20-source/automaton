#!/usr/bin/env python3
"""Carrosséis (posts de várias imagens) do KAVIX ARCADE para intercalar com os reels.

Formato 1080x1350 (4:5, ocupa mais espaço no feed do Instagram/Facebook), no mesmo
visual dos reels: fonte Unbounded, degradê roxo/ciano do site, destaque verde-limão,
prints reais dos jogos, skins reais do inventário e o logo do @kavixarcade.

Uso:
    python3 promo/kavix/carrossel.py            # gera os 4 modelos
Saída: carrossel/modelo_N_<nome>/slide_01.png ... + legenda.txt
"""
import math
import os
import random

import gerar_videos as g
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "carrossel")
PRINTS = os.path.join(OUT, "prints")
W, H = 1080, 1350
U = 1.0
LIME, VIOLET, SKY, WHITE, BLACK, INK = g.LIME, g.VIOLET, g.SKY, g.WHITE, g.BLACK, g.INK
BG = (8, 7, 20)


def slug(nome):
    return g._slug(nome).strip("_")


def shot(nome):
    return Image.open(os.path.join(PRINTS, slug(nome) + ".jpg")).convert("RGBA")


# ------------------------------------------------------------- base visual

def fundo(seed, cor1=VIOLET, cor2=SKY, foto=None):
    """Fundo escuro com luzes da marca (ou um print do jogo desfocado)."""
    rng = random.Random(seed)
    im = Image.new("RGBA", (W, H), BG + (255,))
    if foto is not None:
        f = foto.resize((W // 10, int(W // 10 * foto.height / foto.width)))
        f = f.filter(ImageFilter.GaussianBlur(3)).resize((W, int(W * foto.height / foto.width)))
        im.alpha_composite(f.crop((0, (f.height - H) // 2, W, (f.height - H) // 2 + H)))
        im.alpha_composite(Image.new("RGBA", (W, H), BG + (170,)))
    for cor, (cx, cy), r in ((cor1, (rng.uniform(0, .4), rng.uniform(0, .35)), .75),
                             (cor2, (rng.uniform(.6, 1), rng.uniform(.65, 1)), .7)):
        blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        R = int(W * r)
        ImageDraw.Draw(blob).ellipse((cx * W - R, cy * H - R, cx * W + R, cy * H + R),
                                     fill=cor + (70,))
        im.alpha_composite(blob.filter(ImageFilter.GaussianBlur(W * 0.18)))
    # grão sutil para tirar o "chapado"
    noise = Image.effect_noise((W // 2, H // 2), 40).resize((W, H)).convert("L")
    gr = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    gr.putalpha(noise.point(lambda v: int(max(0, v - 128) * 0.12)))
    im.alpha_composite(gr)
    return im


def moldura(im, n, total, swipe=True):
    """Logo + @ no topo, contador de páginas e 'arrasta' no rodapé."""
    lg = g.logo_image(76, 0.5)
    im.alpha_composite(lg, (48, 44))
    name = g.text_layer(g.HANDLE, 30, path=g.F_BOLD)
    im.alpha_composite(name, (136, 52))
    sub = g.text_layer("jogos grátis no celular e PC", 22, fill=(190, 190, 205), path=g.F_SEMI)
    im.alpha_composite(sub, (136, 88))
    pg = g.sticker(f"{n}/{total}", 26, (255, 255, 255), BLACK, g.F_DISPLAY)
    im.alpha_composite(pg, (W - pg.width - 30, 40))
    # pontinhos de progresso
    d = ImageDraw.Draw(im)
    x0 = W / 2 - (total * 22) / 2
    for k in range(total):
        col = (255, 255, 255, 235) if k == n - 1 else (255, 255, 255, 70)
        d.rounded_rectangle((x0 + k * 22, H - 46, x0 + k * 22 + (34 if k == n - 1 else 12), H - 36),
                            5, fill=col)
    if swipe:
        sw = g.text_layer("arrasta pro lado ➜", 30, fill=WHITE, path=g.F_BOLD, shadow_a=150)
        im.alpha_composite(sw, (W - sw.width - 50, H - 100))
    return im


def titulo(im, texto, y, size=86, hl=(), cor_hl=LIME, max_w=W - 120, cx=W / 2):
    """Título grande com palavras destacadas (sem animação)."""
    g.ACCENT[0] = cor_hl
    g.caption(im, texto, cx, y, size, 9, max_w, highlight=hl, per_word=0)


def texto(im, s, x, y, size=34, cor=(220, 220, 232), path=None, centro=False):
    lay = g.text_layer(s, size, fill=cor, path=path or g.F_SEMI)
    im.alpha_composite(lay, (int(x - lay.width / 2) if centro else int(x), int(y)))
    return lay


def card_jogo(nome, w, rot=0.0, borda=8, raio=36):
    """Print do jogo num cartão com borda branca e sombra."""
    sh = shot(nome)
    h = int(w * 16 / 9)
    sh = sh.resize((w, int(w * sh.height / sh.width)))
    sh = sh.crop((0, (sh.height - h) // 2, w, (sh.height - h) // 2 + h))
    sh.putalpha(g.rounded((w, h), raio, WHITE).getchannel("A"))
    ring = g.rounded((w + 2 * borda, h + 2 * borda), raio + borda, WHITE + (255,))
    ring.alpha_composite(sh, (borda, borda))
    out = g.shadow(ring.size, raio, 24, 160)
    pad = (out.width - ring.width) // 2
    out.alpha_composite(ring, (pad, pad - 6))
    return out.rotate(rot, expand=True, resample=Image.BICUBIC) if rot else out


def put(im, lay, cx, cy):
    g.put(im, lay, cx, cy)


def sticker(im, s, cx, cy, size, rot=-3, bg=WHITE, fg=BLACK, path=None):
    lay = g.sticker(s, int(size), bg, fg, path or g.F_DISPLAY)
    if rot:
        lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    put(im, lay, cx, cy)
    return lay


def botao(im, s, cy, w=760, h=124):
    b = g.cta_button(w, h, s)
    sh = g.shadow(b.size, int(h * 0.3), 22, 150)
    put(im, sh, W / 2, cy + 10)
    put(im, b, W / 2, cy)




TOTAL = 5  # o Instagram/Facebook do perfil aceita até 5 fotos por carrossel aqui


def skin(nome):
    for it in g.skins():
        if it["nome"] == nome:
            return it
    raise KeyError(nome)


def slide_cta(seed, chamada, foto=None):
    im = fundo(seed, foto=foto)
    lg = g.logo_image(280, 0.22)
    put(im, g.shadow(lg.size, 62, 30, 170), W / 2, 310)
    put(im, lg, W / 2, 300)
    titulo(im, chamada, 560, 72, hl=(len(chamada.split()) - 1,))
    sticker(im, "🎁 cadastro novo ganha itens exclusivos", W / 2, 715, 32, -2, LIME)
    sticker(im, "🏆 ranking competitivo  •  🎫 passe de batalha", W / 2, 790, 30, 2,
            (40, 38, 60), WHITE, g.F_BOLD)
    botao(im, "Jogar agora", 925)
    sticker(im, "🔗 kavixbrasil.com.br", W / 2, 1070, 44, 0)
    texto(im, "📱 celular  •  💻 PC  •  sem baixar nada  •  link na bio 👆", W / 2, 1150, 28,
          centro=True, path=g.F_BOLD)
    return moldura(im, TOTAL, TOTAL, swipe=False)


def grade_jogos(im, grupo, y0=470, cw=250, gap_y=480):
    for k, nome in enumerate(grupo):
        r, q = divmod(k, 3)
        x = W / 2 + (q - 1) * (cw + 70)
        y = y0 + r * gap_y
        put(im, card_jogo(nome, cw, (-3, 2, -2, 3, -1, 2, -2, 3, -1)[k], 6, 28), x, y)
        sticker(im, nome, x, y + cw * 0.89, 26, (-3, 3)[k % 2], WHITE)


def grade_skins(im, itens, y0, cols=3, cw=300, ch=340, gap=26):
    for k, it in enumerate(itens):
        r, q = divmod(k, cols)
        x = W / 2 + (q - (cols - 1) / 2) * (cw + gap)
        y = y0 + r * (ch + gap)
        col = g.hexrgb(it["cor"])
        card = g.rounded((cw, ch), 34, (255, 255, 255, 30), outline=col + (200,), width=4)
        glow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((cw * .15, ch * .05, cw * .85, ch * .65), fill=col + (90,))
        card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
        sk = g.skin_image(it["arquivo"], int(cw * 0.62))
        card.alpha_composite(sk, ((cw - sk.width) // 2, int(ch * 0.33 - sk.height / 2)))
        nm = g.text_layer(it["nome"].replace("Título: ", ""), 28, path=g.F_BOLD)
        if nm.width > cw - 20:
            nm = g.scaled(nm, (cw - 20) / nm.width)
        card.alpha_composite(nm, ((cw - nm.width) // 2, int(ch * 0.64)))
        chip = g.rounded((int(cw * 0.56), 36), 18, col + (255,))
        cl = g.text_layer(it["raridade_nome"].upper(), 19, fill=INK, path=g.F_BLACK)
        chip.alpha_composite(cl, ((chip.width - cl.width) // 2, (36 - cl.height) // 2))
        card.alpha_composite(chip, ((cw - chip.width) // 2, int(ch * 0.84)))
        put(im, card, x, y)


# ---------------------------------------------------- patentes / ranking

PATENTES = [("Diamante", (190, 240, 255), (90, 170, 230)),
            ("Rubi", (255, 120, 150), (200, 20, 70)),
            ("Esmeralda", (130, 240, 170), (20, 150, 90)),
            ("Safira", (130, 170, 255), (40, 70, 200)),
            ("Ouro", (255, 225, 120), (215, 145, 20))]


def gema(c1, c2, s=300):
    """Gema lapidada (ícone de patente)."""
    S = s * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top, mid, bot, l, r = S * .2, S * .4, S * .92, S * .06, S * .94

    def mix(t):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    d.polygon([(S * .28, top), (S * .72, top), (r, mid), (l, mid)], fill=mix(.1))
    d.polygon([(l, mid), (r, mid), (S / 2, bot)], fill=mix(.75))
    d.polygon([(S * .28, top), (S * .5, mid), (l, mid)], fill=mix(0))
    d.polygon([(S * .72, top), (r, mid), (S * .5, mid)], fill=mix(.4))
    d.polygon([(l, mid), (S * .5, mid), (S / 2, bot)], fill=mix(.55))
    d.polygon([(S * .3, mid), (S * .5, mid), (S / 2, bot)], fill=mix(.2))
    d.polygon([(S * .28, top), (S * .72, top), (r, mid), (S / 2, bot), (l, mid)],
              outline=(255, 255, 255), width=10)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((S * .1, S * .15, S * .9, S * .95), fill=c2 + (110,))
    out = glow.filter(ImageFilter.GaussianBlur(S * .08))
    out.alpha_composite(im)
    return out.resize((s, s), Image.LANCZOS)


def avatar(s, nome_ou_q, cor):
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, s - 1, s - 1), fill=cor + (255,))
    d.ellipse((6, 6, s - 7, s - 7), fill=(28, 26, 50, 255))
    t = g.text_layer(nome_ou_q, int(s * .42), fill=WHITE, path=g.F_DISPLAY)
    im.alpha_composite(t, ((s - t.width) // 2, (s - t.height) // 2))
    return im


# ---------------------------------------------------------------- modelos

def modelo_30_jogos():
    jogos = [x["nome"] for x in g.library()]
    slides = []
    im = fundo(1)
    for k, (nome, x, y, r) in enumerate([(jogos[3], 200, 860, -10), (jogos[9], 880, 860, 9),
                                         (jogos[0], 540, 930, 0)]):
        put(im, card_jogo(nome, 300 if k < 2 else 340, r), x, y)
    sticker(im, "POV:", 230, 250, 54, -5, LIME)
    titulo(im, "tem 30 jogos nesse site 😳", 400, 104, hl=(1, 2))
    sticker(im, "e é de graça", W / 2, 1180, 46, 3, WHITE)
    slides.append(moldura(im, 1, TOTAL))
    frases = ["os clássicos 🔥", "pra testar reflexo ⚡", "e muito mais 🫠"]
    for p in range(3):
        im = fundo(10 + p)
        titulo(im, frases[p], 205, 64, hl=(len(frases[p].split()) - 2,))
        grade_jogos(im, jogos[p * 6:p * 6 + 6] if p < 2 else jogos[18:24],
                    y0=480, cw=230, gap_y=470)
        slides.append(moldura(im, p + 2, TOTAL))
    slides.append(slide_cta(20, "qual tu vai jogar primeiro?"))
    leg = ("tem 30 jogos nesse site e tu ainda não conhecia 😳\n"
           "salva esse post e comenta qual tu vai jogar primeiro 👇\n\n"
           "tem ranking competitivo com patentes e passe de batalha com itens raros 🏆🎫\n"
           "joga grátis no celular ou no PC, sem baixar nada 👉 kavixbrasil.com.br (link na bio)")
    return "30_jogos", slides, leg


TOP = [("Empilha", "um bloco fora do lugar e acabou 😭"),
       ("Cobrinha", "o clássico que nunca envelhece 🐍"),
       ("Espinhos", "um toque errado e já era 💀"),
       ("Quebra Blocos", "não dá pra jogar só uma 🫠"),
       ("Reflexo", "o mais viciante de todos 👑")]


def slide_rank_duplo(seed, pares):
    im = fundo(seed)
    for k, (rank, nome, fala) in enumerate(pares):
        y = 400 + k * 470
        x_card = 290 if k == 0 else 790
        x_txt = 790 if k == 0 else 290
        put(im, card_jogo(nome, 230, (-4, 4)[k], 6, 28), x_card, y + 40)
        sticker(im, f"#{rank}", x_txt, y - 70, 92, (6, -6)[k], LIME)
        sticker(im, nome, x_txt, y + 60, 44, (-3, 3)[k], WHITE)
        ws = fala.split()
        meio = (len(ws) + 1) // 2
        for j, linha in enumerate((" ".join(ws[:meio]), " ".join(ws[meio:]))):
            texto(im, linha, x_txt, y + 120 + j * 48, 34, WHITE, g.F_BLACK, True)
    return im


def modelo_top5():
    slides = []
    im = fundo(30, foto=shot("Reflexo"))
    sticker(im, "TOP 5", W / 2, 330, 90, -5, LIME)
    titulo(im, "jogos mais viciantes do KAVIX 🔥", 560, 92, hl=(2,))
    texto(im, "o #1 vai te surpreender 👀", W / 2, 760, 40, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(["Empilha", "Cobrinha", "Espinhos"]):
        put(im, card_jogo(nome, 220, (-8, 0, 8)[k], 6, 26), W / 2 + (k - 1) * 270, 1040)
    slides.append(moldura(im, 1, TOTAL))
    slides.append(moldura(slide_rank_duplo(31, [(5,) + TOP[0], (4,) + TOP[1]]), 2, TOTAL))
    slides.append(moldura(slide_rank_duplo(32, [(3,) + TOP[2], (2,) + TOP[3]]), 3, TOTAL))
    nome, fala = TOP[4]
    im = fundo(33, foto=shot(nome))
    put(im, card_jogo(nome, 470, -4), 330, 760)
    sticker(im, "#1", 820, 380, 130, 6, (255, 206, 64))
    sticker(im, nome, 820, 570, 58, -3, WHITE)
    for j, linha in enumerate(("o mais viciante", "de todos 👑")):
        texto(im, linha, 820, 680 + j * 56, 42, WHITE, g.F_BLACK, True)
    sticker(im, "vale ponto no ranking 🏆", 820, 900, 30, 2, (40, 38, 60), WHITE, g.F_BOLD)
    slides.append(moldura(im, 4, TOTAL))
    slides.append(slide_cta(40, "concorda com o top? comenta o teu"))
    leg = ("TOP 5 jogos mais viciantes do KAVIX 🔥 o #1 é covardia 👑\n"
           "concorda? comenta o teu favorito 👇\n\n"
           "cada jogo tem ranking próprio e vale ponto no competitivo 🏆\n"
           "todos de graça no celular e no PC 👉 kavixbrasil.com.br (link na bio)")
    return "top5_viciantes", slides, leg


def modelo_skins():
    sk = g.skins()
    lend = [x for x in sk if x["raridade"] == "lendario"]
    epic = [x for x in sk if x["raridade"] == "epico" and x["tipo"] in ("roupa", "chapeu", "aura", "olhos")]
    slides = []
    im = fundo(50, (255, 206, 64), VIOLET)
    top = sorted(lend, key=lambda x: x["tipo"] != "roupa")[:3]
    for k, it in enumerate(top):
        put(im, g.skin_image(it["arquivo"], (300, 380, 300)[k]), W / 2 + (k - 1) * 330,
            (930, 880, 930)[k])
    titulo(im, "monta tua bolinha do teu jeito 👀", 360, 92, hl=(3,))
    sticker(im, f"+{len(sk) // 10 * 10} skins", W / 2, 1180, 56, -3, LIME)
    slides.append(moldura(im, 1, TOTAL))
    for p, (nomep, lst, cor) in enumerate((("LENDÁRIAS 👑", lend[:5], (255, 206, 64)),
                                          ("ÉPICAS 💜", epic[:6], (176, 107, 255)))):
        im = fundo(51 + p, cor, VIOLET)
        sticker(im, nomep, W / 2, 230, 64, -3, cor, INK)
        grade_skins(im, lst, 560)
        slides.append(moldura(im, p + 2, TOTAL))
    im = fundo(55)
    titulo(im, "qual tu ia usar primeiro?", 330, 84, hl=(4,))
    for k, it in enumerate(lend[:2]):
        x = W / 2 + (k - .5) * 420
        put(im, g.skin_image(it["arquivo"], 330), x, 720)
        sticker(im, "A" if k == 0 else "B", x, 520, 64, (-6, 6)[k], LIME)
        sticker(im, it["nome"], x, 930, 36, (-3, 3)[k], WHITE)
    texto(im, "comenta A ou B 👇", W / 2, 1060, 46, WHITE, g.F_BLACK, True)
    slides.append(moldura(im, 4, TOTAL))
    slides.append(slide_cta(56, "cria tua conta e escolhe a tua"))
    leg = (f"monta tua bolinha do teu jeito 👀 são +{len(sk) // 10 * 10} skins: lendárias, épicas, raras…\n"
           "qual tu ia usar primeiro? comenta 👇\n\n"
           "tem item que só sai no passe de batalha 🎫 e cadastro novo ganha itens exclusivos 🎁\n"
           "👉 kavixbrasil.com.br (link na bio)")
    return "skins", slides, leg


def modelo_conhece():
    slides = []
    im = fundo(60, foto=shot("Bolhas"))
    titulo(im, "tu ainda não conhece o KAVIX? 🤔", 330, 100, hl=(4,))
    texto(im, "salva esse post antes que suma 📌", W / 2, 560, 40, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(["Hélice", "Bolhas", "Canhão"]):
        put(im, card_jogo(nome, 260, (-7, 0, 7)[k], 6, 28), W / 2 + (k - 1) * 300, 930)
    slides.append(moldura(im, 1, TOTAL))
    # 3 passos num slide
    im = fundo(61)
    titulo(im, "como jogar em 3 passos 👇", 210, 70, hl=(3,))
    passos = [("1", "entra no site", "kavixbrasil.com.br no celular ou no PC", "Quebra Blocos"),
              ("2", "escolhe um dos 30 jogos", "reflexo, lógica, desafio…", "Trampolim"),
              ("3", "cria tua conta", "e ganha itens exclusivos 🎁", "Órbita")]
    for k, (num, tit, desc, nome) in enumerate(passos):
        y = 450 + k * 280
        card = g.rounded((960, 240), 44, (255, 255, 255, 26), outline=(255, 255, 255, 70), width=3)
        put(im, card, W / 2, y)
        put(im, card_jogo(nome, 110, 0, 4, 18), 160, y)
        sticker(im, num, 300, y, 64, -4, LIME)
        texto(im, tit, 370, y - 52, 44, WHITE, g.F_BLACK)
        texto(im, desc, 370, y + 12, 32, (215, 215, 230), g.F_SEMI)
    slides.append(moldura(im, 2, TOTAL))
    # benefícios
    im = fundo(65)
    titulo(im, "tudo isso sem baixar nada 🙌", 230, 80, hl=(3, 4))
    itens = [("📱", "roda no celular"), ("💻", "roda no PC"), ("🏆", "ranking competitivo"),
             ("🎫", "passe de batalha"), ("💎", "patentes pra subir"), ("🎁", "itens no cadastro")]
    for k, (e, s) in enumerate(itens):
        r, q = divmod(k, 2)
        x = W / 2 + (q - .5) * 470
        y = 500 + r * 210
        card = g.rounded((430, 170), 40, (255, 255, 255, 28), outline=(255, 255, 255, 80), width=3)
        card.alpha_composite(g.emoji_layer(e, 76), (34, 47))
        lay = g.text_layer(s, 36, fill=WHITE, path=g.F_BOLD)
        if lay.width > 270:
            lay = g.scaled(lay, 270 / lay.width)
        card.alpha_composite(lay, (130, (170 - lay.height) // 2))
        put(im, card, x, y)
    slides.append(moldura(im, 3, TOTAL))
    # vitrine dos jogos
    im = fundo(66)
    titulo(im, "30 jogos te esperando 🎮", 210, 74, hl=(0, 1))
    grade_jogos(im, ["Pula Corda", "Zigue-Zague", "Boliche", "Gravidade", "Pulso", "Encaixe"],
                y0=500, cw=250, gap_y=470)
    slides.append(moldura(im, 4, TOTAL))
    slides.append(slide_cta(67, "bora jogar agora?"))
    leg = ("tu ainda não conhece o KAVIX? 🤔 30 jogos no navegador, no celular e no PC, sem baixar nada\n"
           "tem ranking competitivo com patentes 💎 e passe de batalha com itens raros 🎫\n"
           "salva esse post 📌 e manda pra quem vive entediado 👀\n\n"
           "👉 kavixbrasil.com.br (link na bio) · cadastro novo ganha itens exclusivos 🎁")
    return "conhece_o_kavix", slides, leg


PASSE_PREMIUM = ["Coroa de Gelo", "Moldura Esmeralda", "Título: Campeão", "Aura Dourada",
                 "Cor Kavix", "Coroa Suprema"]
PASSE_GRATIS = ["Rastro Prata", "Título: Recordista", "Óculos Dourados", "Boina",
                "Floresta", "Aura Estelar"]


def barra_xp(im, y, frac, w=860, h=34):
    x0 = (W - w) / 2
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y, x0 + w, y + h), h // 2, fill=(255, 255, 255, 40))
    fill = g.hgradient(int(w * frac), h, VIOLET, SKY)
    fill.putalpha(g.rounded((int(w * frac), h), h // 2, WHITE).getchannel("A"))
    im.alpha_composite(fill, (int(x0), int(y)))


def modelo_passe():
    slides = []
    # capa
    im = fundo(70, (255, 206, 64), VIOLET)
    sticker(im, "PASSE DE BATALHA", W / 2, 260, 58, -4, (255, 206, 64), INK)
    titulo(im, "temporada 1 chegou 🎫", 410, 96, hl=(1,))
    for k, n in enumerate(["Aura Cosmos", "Coroa Suprema", "Aura Estelar"]):
        put(im, g.skin_image(skin(n)["arquivo"], (280, 360, 280)[k]), W / 2 + (k - 1) * 320,
            (880, 820, 880)[k])
    texto(im, "30 níveis de recompensas raras", W / 2, 1110, 40, WHITE, g.F_BLACK, True)
    slides.append(moldura(im, 1, TOTAL))
    # recompensas premium
    im = fundo(71, (255, 206, 64), VIOLET)
    sticker(im, "TRILHA PREMIUM ⭐", W / 2, 220, 56, -3, (255, 206, 64), INK)
    texto(im, "auras, molduras, títulos e as peças mais chamativas", W / 2, 300, 32,
          (225, 225, 235), g.F_SEMI, True)
    grade_skins(im, [skin(n) for n in PASSE_PREMIUM], 560, cw=290, ch=330)
    slides.append(moldura(im, 2, TOTAL))
    # trilha grátis
    im = fundo(72, SKY, VIOLET)
    sticker(im, "TRILHA GRÁTIS 🎁", W / 2, 220, 56, 3, LIME, INK)
    texto(im, "todo mundo ganha itens só de jogar", W / 2, 300, 34, (225, 225, 235), g.F_SEMI, True)
    grade_skins(im, [skin(n) for n in PASSE_GRATIS], 560, cw=290, ch=330)
    slides.append(moldura(im, 3, TOTAL))
    # sobe de nível
    im = fundo(73)
    titulo(im, "cada partida dá XP ⚡", 250, 86, hl=(3,))
    texto(im, "sobe de nível e libera recompensa nova", W / 2, 360, 36, WHITE, g.F_BOLD, True)
    for k, (nivel, frac, item) in enumerate(((1, .25, "Boina"), (12, .6, "Óculos Dourados"),
                                             (30, 1.0, "Aura Estelar"))):
        y = 520 + k * 250
        card = g.rounded((940, 210), 40, (255, 255, 255, 26), outline=(255, 255, 255, 70), width=3)
        put(im, card, W / 2, y)
        sticker(im, f"NÍVEL {nivel}", 250, y - 40, 40, -3, LIME if nivel < 30 else (255, 206, 64), INK)
        barra_xp(im, y + 20, frac, w=440, h=30)
        im2 = g.skin_image(skin(item)["arquivo"], 150)
        put(im, im2, 860, y)
        texto(im, item, 860 - 230, y - 58, 30, WHITE, g.F_BOLD)
    slides.append(moldura(im, 4, TOTAL))
    slides.append(slide_cta(74, "começa a temporada agora"))
    leg = ("o KAVIX tem PASSE DE BATALHA 🎫 temporada 1 com 30 níveis de recompensas\n"
           "auras, coroas, molduras e títulos raros… e tem trilha grátis pra todo mundo 🎁\n"
           "qual item tu quer primeiro? comenta 👇\n\n"
           "joga, ganha XP e sobe de nível 👉 kavixbrasil.com.br (link na bio)")
    return "passe_de_batalha", slides, leg


def modelo_ranking():
    slides = []
    # capa
    im = fundo(80, SKY, VIOLET)
    titulo(im, "tem RANKING e modo COMPETITIVO 🏆", 330, 96, hl=(1, 4))
    for k, (nome, c1, c2) in enumerate(PATENTES[:3]):
        put(im, gema(c1, c2, (260, 340, 260)[k]), W / 2 + (k - 1) * 300, (880, 820, 880)[k])
    texto(im, "sobe de patente e mostra quem manda 😤", W / 2, 1120, 38, WHITE, g.F_BLACK, True)
    slides.append(moldura(im, 1, TOTAL))
    # patentes
    im = fundo(81, SKY, VIOLET)
    sticker(im, "AS PATENTES 💎", W / 2, 220, 58, -3, LIME, INK)
    for k, (nome, c1, c2) in enumerate(PATENTES):
        y = 400 + k * 180
        card = g.rounded((900, 150), 40, (255, 255, 255, 26), outline=c2 + (200,), width=4)
        put(im, card, W / 2, y)
        put(im, gema(c1, c2, 150), 220, y)
        texto(im, f"{k + 1}º", 310, y - 30, 44, c1, g.F_DISPLAY)
        texto(im, nome, 410, y - 30, 48, WHITE, g.F_DISPLAY)
    slides.append(moldura(im, 2, TOTAL))
    # ranking organizado: pódio + lista
    im = fundo(82)
    sticker(im, "RANKING GERAL", W / 2, 200, 54, -3, WHITE, INK)
    texto(im, "soma o teu recorde em todos os jogos", W / 2, 270, 30, (215, 215, 230), g.F_SEMI, True)
    podio = [(2, "Rubi", 300, 600, 240), (1, "Diamante", 540, 540, 300), (3, "Esmeralda", 780, 640, 200)]
    for pos, pat, x, y, hbar in podio:
        c1, c2 = next((a, b) for n, a, b in PATENTES if n == pat)
        bar = g.rounded((200, hbar), 26, c2 + (210,))
        put(im, bar, x, y + 170 + hbar / 2 - 100)
        texto(im, f"{pos}º", x, y + 120, 60, WHITE, g.F_DISPLAY, True)
        put(im, gema(c1, c2, 110), x, y - 120)
        put(im, avatar(120, "?", c1), x, y)
        sticker(im, "teu nome aqui? 👀" if pos == 1 else pat, x, y + 74,
                28 if pos == 1 else 26, 0, LIME if pos == 1 else WHITE, INK)
    for k, pat in enumerate(PATENTES[3:]):
        y = 1010 + k * 110
        row = g.rounded((860, 92), 30, (255, 255, 255, 26), outline=pat[2] + (200,), width=3)
        put(im, row, W / 2, y)
        texto(im, f"{k + 4}º", 150, y - 26, 40, WHITE, g.F_DISPLAY)
        put(im, gema(pat[1], pat[2], 80), 270, y)
        texto(im, "pode ser tu", 330, y - 22, 34, WHITE, g.F_BOLD)
        sticker(im, pat[0], 850, y, 28, 0, pat[1], INK)
    slides.append(moldura(im, 3, TOTAL))
    # ranking por jogo + títulos
    im = fundo(83)
    titulo(im, "ranking em cada um dos 30 jogos 🎮", 230, 70, hl=(3, 4))
    chips = ["Espinhos", "Passagem", "Quebra Blocos", "Três Pistas", "Pega Tudo", "Órbita",
             "Reflexo", "Gravidade", "Troca Cor", "Empilha", "Cobrinha", "Memória"]
    x, y = 90, 420
    for nome in chips:
        lay = g.sticker(nome, 28, (40, 38, 60), WHITE, g.F_BOLD)
        if x + lay.width > W - 80:
            x, y = 90, y + 86
        im.alpha_composite(lay, (int(x), int(y)))
        x += lay.width - 6
    sticker(im, "TÍTULOS PRA CONQUISTAR", W / 2, 790, 44, -2, LIME, INK)
    tits = ["Título: Recordista", "Título: Lendário", "Título: Campeão"]
    grade_skins(im, [skin(n) for n in tits], 1000, cols=3, cw=290, ch=250, gap=20)
    slides.append(moldura(im, 4, TOTAL))
    slides.append(slide_cta(84, "vem subir de patente"))
    leg = ("o KAVIX tem RANKING e modo COMPETITIVO 🏆\n"
           "patentes Diamante 💎, Rubi, Esmeralda, Safira e Ouro, ranking em cada um dos 30 jogos e títulos pra conquistar\n"
           "quem vai ser o 1º? comenta 👇\n\n"
           "👉 kavixbrasil.com.br (link na bio)")
    return "ranking_competitivo", slides, leg


RECORDES = [2428, 574, 501, 298, 244]  # ranking geral do site (print de 13/10/2026)


def numero(n):
    return f"{n:,}".replace(",", ".")


def modelo_recorde():
    slides = []
    dia, rubi = PATENTES[0], PATENTES[1]
    # capa
    im = fundo(90, SKY, VIOLET)
    titulo(im, "se tu é bom mesmo…", 230, 70, hl=(2, 3))
    titulo(im, "bate esse recorde 😤", 390, 92, hl=(1, 2))
    put(im, gema(dia[1], dia[2], 300), W / 2, 680)
    lay = g.text_layer(numero(RECORDES[0]), 210, fill=WHITE, path=g.F_DISPLAY, shadow_a=200)
    put(im, lay, W / 2, 960)
    texto(im, "pontos · 1º lugar do ranking geral 💎", W / 2, 1090, 38, WHITE, g.F_BOLD, True)
    slides.append(moldura(im, 1, TOTAL))
    # como funciona
    im = fundo(91)
    titulo(im, "teu recorde em cada jogo soma no ranking 🏆", 250, 70, hl=(2, 3))
    for k, nome in enumerate(["Espinhos", "Empilha", "Cobrinha"]):
        x = W / 2 + (k - 1) * 320
        put(im, card_jogo(nome, 240, (-5, 0, 5)[k], 6, 28), x, 720)
        sticker(im, "+ recorde", x, 980, 32, (-4, 0, 4)[k], LIME, INK)
    texto(im, "30 jogos  =  30 chances de subir 📈", W / 2, 1110, 42, WHITE, g.F_BLACK, True)
    slides.append(moldura(im, 2, TOTAL))
    # ranking
    im = fundo(92)
    sticker(im, "RANKING GERAL · TOP 5", W / 2, 210, 50, -3, WHITE, INK)
    for k, (pts, pat) in enumerate(zip(RECORDES, PATENTES)):
        y = 400 + k * 175
        top = k == 0
        row = g.rounded((920, 150), 42, (255, 255, 255, 40 if top else 24),
                        outline=pat[2] + (230,), width=5 if top else 3)
        put(im, row, W / 2, y)
        texto(im, f"{k + 1}º", 110, y - 34, 52, pat[1], g.F_DISPLAY)
        put(im, avatar(96, "?", pat[1]), 280, y)
        texto(im, "???" if top else "pode ser tu 👀", 350, y - 44, 38, WHITE, g.F_BLACK)
        sticker(im, pat[0], 350 + 110, y + 28, 24, 0, pat[1], INK)
        lay = g.text_layer(numero(pts), 56, fill=WHITE, path=g.F_DISPLAY)
        im.alpha_composite(lay, (int(W - 120 - lay.width), int(y - lay.height / 2)))
    slides.append(moldura(im, 3, TOTAL))
    # desafio
    im = fundo(93, rubi[2], VIOLET)
    titulo(im, "duvido tu passar 👀", 300, 104, hl=(1, 2))
    texto(im, "quando conseguir, manda print nos comentários 📸", W / 2, 470, 36, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(["Reflexo", "Quebra Blocos", "Gravidade"]):
        put(im, card_jogo(nome, 250, (-8, 0, 8)[k], 6, 28), W / 2 + (k - 1) * 300, 840)
    sticker(im, "começa pelo jogo que tu é melhor 😎", W / 2, 1130, 34, -2, LIME, INK)
    slides.append(moldura(im, 4, TOTAL))
    slides.append(slide_cta(94, "aceita o desafio?"))
    leg = (f"se tu é bom mesmo, bate esse recorde 😤 {numero(RECORDES[0])} pontos no ranking geral do KAVIX 💎\n"
           "teu recorde em cada um dos 30 jogos soma no ranking, e quem sobe ganha patente: "
           "Diamante, Rubi, Esmeralda, Safira e Ouro 🏆\n"
           "conseguiu? manda print nos comentários 📸 marca quem tu acha que passa 👇\n\n"
           "👉 kavixbrasil.com.br (link na bio)")
    return "desafio_do_recorde", slides, leg


TAGS = ("#kavix #kavixarcade #fyp #viral #explore #paravoce #roblox #robloxbrasil "
        "#jogosonline #gamerbrasil #minigames #jogosgratis #ranked #passedebatalha")


def main():
    import shutil
    modelos = [modelo_30_jogos, modelo_top5, modelo_skins, modelo_conhece, modelo_passe,
               modelo_ranking, modelo_recorde]
    for d in os.listdir(OUT):
        if d.startswith("modelo_"):
            shutil.rmtree(os.path.join(OUT, d))
    for i, fn in enumerate(modelos, 1):
        nome, slides, leg = fn()
        assert len(slides) <= 5, (nome, len(slides))
        pasta = os.path.join(OUT, f"modelo_{i}_{nome}")
        os.makedirs(pasta, exist_ok=True)
        for k, im in enumerate(slides, 1):
            im.convert("RGB").save(os.path.join(pasta, f"slide_{k:02d}.jpg"), quality=92)
        with open(os.path.join(pasta, "legenda.txt"), "w") as fh:
            fh.write(leg + "\n\n" + TAGS + "\n")
        print("ok:", pasta, len(slides), "slides")


if __name__ == "__main__":
    main()
