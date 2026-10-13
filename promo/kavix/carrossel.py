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


def slide_cta(seed, n, total, chamada, foto=None):
    im = fundo(seed, foto=foto)
    lg = g.logo_image(300, 0.22)
    put(im, g.shadow(lg.size, 66, 30, 170), W / 2, 330)
    put(im, lg, W / 2, 320)
    titulo(im, chamada, 600, 74, hl=(len(chamada.split()) - 1,))
    sticker(im, "🎁 cadastro novo ganha itens exclusivos", W / 2, 760, 34, -2, LIME)
    botao(im, "Jogar agora", 900)
    sticker(im, "🔗 kavixbrasil.com.br", W / 2, 1050, 44, 0)
    texto(im, "📱 celular  •  💻 PC  •  sem baixar nada", W / 2, 1130, 32, centro=True,
          path=g.F_BOLD)
    texto(im, "link na bio 👆", W / 2, 1190, 30, (190, 190, 205), centro=True)
    return moldura(im, n, total, swipe=False)


# ---------------------------------------------------------------- modelos

def modelo_30_jogos():
    jogos = [x["nome"] for x in g.library()]
    slides = []
    total = 7
    # capa
    im = fundo(1)
    for k, (nome, x, y, r) in enumerate([(jogos[3], 200, 860, -10), (jogos[9], 880, 860, 9),
                                         (jogos[0], 540, 930, 0)]):
        put(im, card_jogo(nome, 300 if k < 2 else 340, r), x, y)
    sticker(im, "POV:", 230, 250, 54, -5, LIME)
    titulo(im, "tem 30 jogos nesse site 😳", 400, 104, hl=(1, 2))
    sticker(im, "e é de graça", W / 2, 1180, 46, 3, WHITE)
    slides.append(moldura(im, 1, total))
    # 5 grades de 6 jogos
    for p in range(5):
        im = fundo(10 + p)
        grupo = jogos[p * 6:(p + 1) * 6]
        frase = ["os clássicos 🔥", "pra testar reflexo ⚡", "os mais viciantes 🫠",
                 "pra jogar no intervalo ⏱️", "pra quem curte desafio 😤"][p]
        titulo(im, frase, 205, 64, hl=(len(frase.split()) - 2,))
        cw = 250
        for k, nome in enumerate(grupo):
            r, q = divmod(k, 3)
            x = W / 2 + (q - 1) * (cw + 70)
            y = 480 + r * 480
            put(im, card_jogo(nome, cw, (-3, 2, -2, 3, -1, 2)[k], 6, 28), x, y)
            sticker(im, nome, x, y + 222, 28, (-3, 3)[k % 2], WHITE)
        slides.append(moldura(im, p + 2, total))
    slides.append(slide_cta(20, total, total, "qual tu vai jogar primeiro?"))
    leg = ("tem 30 jogos nesse site e tu ainda não conhecia 😳\n"
           "salva esse post e comenta qual tu vai jogar primeiro 👇\n\n"
           "joga grátis no celular ou no PC, sem baixar nada 👉 kavixbrasil.com.br (link na bio)\n"
           "cadastro novo ganha itens exclusivos 🎁")
    return "30_jogos", slides, leg


TOP = [("Empilha", "um bloco fora do lugar e acabou 😭"),
       ("Cobrinha", "o clássico que nunca envelhece 🐍"),
       ("Espinhos", "um toque errado e já era 💀"),
       ("Quebra Blocos", "não dá pra jogar só uma 🫠"),
       ("Reflexo", "o mais viciante de todos 👑")]


def modelo_top5():
    total = 7
    slides = []
    im = fundo(30, foto=shot("Reflexo"))
    sticker(im, "TOP 5", W / 2, 330, 90, -5, LIME)
    titulo(im, "jogos mais viciantes do KAVIX 🔥", 560, 92, hl=(2,))
    texto(im, "o #1 vai te surpreender 👀", W / 2, 760, 40, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(["Empilha", "Cobrinha", "Espinhos"]):
        put(im, card_jogo(nome, 220, (-8, 0, 8)[k], 6, 26), W / 2 + (k - 1) * 270, 1040)
    slides.append(moldura(im, 1, total))
    for k, (nome, fala) in enumerate(TOP):
        rank = 5 - k
        im = fundo(31 + k, foto=shot(nome))
        put(im, card_jogo(nome, 470, (-4, 3)[k % 2]), 330, 760)
        cor = LIME if rank > 1 else (255, 206, 64)
        sticker(im, f"#{rank}", 820, 380, 120, 6, cor)
        sticker(im, nome, 820, 560, 54, -3, WHITE)
        lay = g.text_layer(fala, 40, fill=WHITE, path=g.F_BLACK, shadow_a=170)
        if lay.width > 400:
            # quebra em duas linhas
            ws = fala.split()
            meio = len(ws) // 2
            for j, linha in enumerate((" ".join(ws[:meio]), " ".join(ws[meio:]))):
                texto(im, linha, 820, 680 + j * 56, 40, WHITE, g.F_BLACK, True)
        else:
            texto(im, fala, 820, 680, 40, WHITE, g.F_BLACK, True)
        sticker(im, "joga no celular e no PC", 820, 900, 30, 2, (40, 38, 60), WHITE, g.F_BOLD)
        slides.append(moldura(im, k + 2, total))
    slides.append(slide_cta(40, total, total, "concorda com o top? comenta o teu"))
    leg = ("TOP 5 jogos mais viciantes do KAVIX 🔥 o #1 é covardia 👑\n"
           "concorda? comenta o teu favorito 👇\n\n"
           "todos de graça no celular e no PC 👉 kavixbrasil.com.br (link na bio)")
    return "top5_viciantes", slides, leg


def grade_skins(im, itens, y0, cols=3, cw=300, ch=340):
    for k, it in enumerate(itens):
        r, q = divmod(k, cols)
        x = W / 2 + (q - (cols - 1) / 2) * (cw + 26)
        y = y0 + r * (ch + 26)
        col = g.hexrgb(it["cor"])
        card = g.rounded((cw, ch), 34, (255, 255, 255, 30), outline=col + (200,), width=4)
        glow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((cw * .15, ch * .05, cw * .85, ch * .65), fill=col + (90,))
        card.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
        sk = g.skin_image(it["arquivo"], int(cw * 0.62))
        card.alpha_composite(sk, ((cw - sk.width) // 2, int(ch * 0.33 - sk.height / 2)))
        nm = g.text_layer(it["nome"], 30, path=g.F_BOLD)
        if nm.width > cw - 20:
            nm = g.scaled(nm, (cw - 20) / nm.width)
        card.alpha_composite(nm, ((cw - nm.width) // 2, int(ch * 0.64)))
        chip = g.rounded((int(cw * 0.5), 38), 19, col + (255,))
        cl = g.text_layer(it["raridade_nome"].upper(), 20, fill=INK, path=g.F_BLACK)
        chip.alpha_composite(cl, ((chip.width - cl.width) // 2, (38 - cl.height) // 2))
        card.alpha_composite(chip, ((cw - chip.width) // 2, int(ch * 0.84)))
        put(im, card, x, y)


def modelo_skins():
    sk = g.skins()
    lend = [x for x in sk if x["raridade"] == "lendario"]
    epic = [x for x in sk if x["raridade"] == "epico" and x["tipo"] in ("roupa", "chapeu", "aura", "olhos")]
    raro = [x for x in sk if x["raridade"] == "raro" and x["tipo"] in ("chapeu", "olhos", "aura", "roupa", "cor")]
    total = 6
    slides = []
    im = fundo(50, (255, 206, 64), VIOLET)
    top = sorted(lend, key=lambda x: x["tipo"] != "roupa")[:3]
    for k, it in enumerate(top):
        s = g.skin_image(it["arquivo"], (300, 380, 300)[k])
        put(im, s, W / 2 + (k - 1) * 330, (930, 880, 930)[k])
    titulo(im, "monta tua bolinha do teu jeito 👀", 360, 92, hl=(3,))
    sticker(im, f"+{len(sk) // 10 * 10} skins", W / 2, 1180, 56, -3, LIME)
    slides.append(moldura(im, 1, total))
    for p, (nomep, lst, cor) in enumerate((("LENDÁRIAS 👑", lend[:6], (255, 206, 64)),
                                          ("ÉPICAS 💜", epic[:6], (176, 107, 255)),
                                          ("RARAS 💎", raro[:6], SKY))):
        im = fundo(51 + p, cor, VIOLET)
        sticker(im, nomep, W / 2, 230, 64, -3, cor, INK)
        grade_skins(im, lst, 560 if len(lst) > 3 else 700)
        slides.append(moldura(im, p + 2, total))
    im = fundo(55)
    titulo(im, "qual tu ia usar primeiro?", 330, 84, hl=(4,))
    duo = lend[:2]
    for k, it in enumerate(duo):
        x = W / 2 + (k - .5) * 420
        put(im, g.skin_image(it["arquivo"], 330), x, 720)
        sticker(im, "A" if k == 0 else "B", x, 520, 64, (-6, 6)[k], LIME)
        sticker(im, it["nome"], x, 930, 36, (-3, 3)[k], WHITE)
    texto(im, "comenta A ou B 👇", W / 2, 1060, 46, WHITE, g.F_BLACK, True)
    slides.append(moldura(im, 5, total))
    slides.append(slide_cta(56, total, total, "cria tua conta e escolhe a tua"))
    leg = (f"monta tua bolinha do teu jeito 👀 são +{len(sk) // 10 * 10} skins: lendárias, épicas, raras…\n"
           "qual tu ia usar primeiro? comenta 👇\n\n"
           "cadastro novo ganha itens exclusivos 🎁 👉 kavixbrasil.com.br (link na bio)")
    return "skins", slides, leg


def modelo_conhece():
    total = 6
    slides = []
    im = fundo(60, foto=shot("Bolhas"))
    titulo(im, "tu ainda não conhece o KAVIX? 🤔", 330, 100, hl=(4,))
    texto(im, "salva esse post antes que suma 📌", W / 2, 560, 40, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(["Hélice", "Bolhas", "Canhão"]):
        put(im, card_jogo(nome, 260, (-7, 0, 7)[k], 6, 28), W / 2 + (k - 1) * 300, 930)
    slides.append(moldura(im, 1, total))
    passos = [("1", "entra no site", "kavixbrasil.com.br no navegador do celular ou do PC",
               "Quebra Blocos"),
              ("2", "escolhe um dos 30 jogos", "partidas rápidas, de reflexo, de lógica e de desafio",
               "Trampolim"),
              ("3", "cria tua conta", "e ganha itens exclusivos pra tua bolinha 🎁", "Órbita")]
    for k, (num, tit, desc, nome) in enumerate(passos):
        im = fundo(61 + k, foto=shot(nome))
        sticker(im, f"PASSO {num}", W / 2, 230, 66, -4, LIME)
        titulo(im, tit, 380, 80, hl=(len(tit.split()) - 1,))
        texto(im, desc, W / 2, 470, 34, (225, 225, 235), g.F_SEMI, True)
        if k == 0:
            # janela do navegador com o site
            fr = Image.open(os.path.join(PRINTS, "quebra_blocos.jpg"))
            pcf = os.path.join(HERE, "gameplay", "jogos", "quebra_blocos_pc.mp4")
            if os.path.exists(pcf):
                import subprocess
                tmp = os.path.join(OUT, ".pc.jpg")
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "8", "-i", pcf,
                                "-frames:v", "1", tmp], check=True)
                fr = Image.open(tmp)
                os.remove(tmp)
            put(im, g.window_card(fr, 900, 1.0).rotate(-3, expand=True, resample=Image.BICUBIC),
                W / 2, 870)
        elif k == 1:
            for j, n2 in enumerate(["Trampolim", "Pula Corda", "Zigue-Zague"]):
                put(im, card_jogo(n2, 260, (-6, 0, 6)[j], 6, 28), W / 2 + (j - 1) * 300, 900)
        else:
            its = [x for x in g.skins() if x["raridade"] in ("lendario", "epico")
                   and x["tipo"] in ("roupa", "chapeu")][:3]
            grade_skins(im, its, 880)
        slides.append(moldura(im, k + 2, total))
    im = fundo(65)
    titulo(im, "sem baixar nada 🙌", 260, 92, hl=(2,))
    itens = [("📱", "roda no celular"), ("💻", "roda no PC"), ("⚡", "partidas rápidas"),
             ("🎮", "30 jogos"), ("🎁", "itens no cadastro"), ("🆓", "de graça")]
    for k, (e, s) in enumerate(itens):
        r, q = divmod(k, 2)
        x = W / 2 + (q - .5) * 470
        y = 520 + r * 210
        card = g.rounded((430, 170), 40, (255, 255, 255, 28), outline=(255, 255, 255, 80), width=3)
        card.alpha_composite(g.emoji_layer(e, 76), (34, 47))
        lay = g.text_layer(s, 38, fill=WHITE, path=g.F_BOLD)
        if lay.width > 270:
            lay = g.scaled(lay, 270 / lay.width)
        card.alpha_composite(lay, (130, (170 - lay.height) // 2))
        put(im, card, x, y)
    slides.append(moldura(im, 5, total))
    slides.append(slide_cta(66, total, total, "bora jogar agora?"))
    leg = ("tu ainda não conhece o KAVIX? 🤔 30 jogos no navegador, no celular e no PC, sem baixar nada\n"
           "salva esse post 📌 e manda pra quem vive entediado 👀\n\n"
           "👉 kavixbrasil.com.br (link na bio) · cadastro novo ganha itens exclusivos 🎁")
    return "conhece_o_kavix", slides, leg


TAGS = ("#kavix #kavixarcade #fyp #viral #explore #paravoce #roblox #robloxbrasil "
        "#jogosonline #gamerbrasil #minigames #jogosgratis #carrossel")


def main():
    modelos = [modelo_30_jogos, modelo_top5, modelo_skins, modelo_conhece]
    for i, fn in enumerate(modelos, 1):
        nome, slides, leg = fn()
        pasta = os.path.join(OUT, f"modelo_{i}_{nome}")
        os.makedirs(pasta, exist_ok=True)
        for k, im in enumerate(slides, 1):
            im.convert("RGB").save(os.path.join(pasta, f"slide_{k:02d}.jpg"), quality=92)
        with open(os.path.join(pasta, "legenda.txt"), "w") as fh:
            fh.write(leg + "\n\n" + TAGS + "\n")
        print("ok:", pasta, len(slides), "slides")


if __name__ == "__main__":
    main()
