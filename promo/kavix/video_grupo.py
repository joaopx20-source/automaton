#!/usr/bin/env python3
"""Vídeo-convite para grupos do Facebook (horizontal 16:9, sem cara de anúncio).

Apresenta o KAVIX ARCADE intercalando modos de jogo, benefícios, ganhos e ranked:
texto de um lado e jogo/arte do outro (alternando), transições em fade e trilha
house animada (diferente do trap dos reels).

Uso:  python3 promo/kavix/video_grupo.py
Saída: grupo_facebook/kavix_convite_grupo.mp4 + legenda.txt
"""
import math
import os
import subprocess

import numpy as np

import carrossel as C
import gerar_videos as g
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "grupo_facebook")
W, H = 1920, 1080
FPS = g.FPS
PUNCH = 0.22

TAG = {"modo": ("MODO DE JOGO", (56, 210, 255)),
       "beneficio": ("BENEFÍCIO", (198, 255, 61)),
       "ganhos": ("GANHOS", (255, 206, 64)),
       "ranked": ("RANKED", (255, 110, 150))}


def cel(nome, frac=0.4):
    return g.at(g.game(0, nome)["celular"], frac)


def pc(nome, frac=0.5):
    return g.at(g.game(0, nome)["pc"], frac)


# ------------------------------------------------------------- visual base

def ease_out_cubic(x):
    return 1 - (1 - g.clamp01(x)) ** 3


_bg_cache = {}


def fundo(seed, cor1=g.VIOLET, cor2=g.SKY):
    key = (seed, cor1, cor2)
    if key not in _bg_cache:
        im = Image.new("RGBA", (W, H), (8, 7, 20, 255))
        rng = np.random.default_rng(seed)
        for cor, (cx, cy) in ((cor1, (rng.uniform(.05, .35), rng.uniform(.1, .4))),
                              (cor2, (rng.uniform(.65, .95), rng.uniform(.6, .9)))):
            blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            R = int(W * .42)
            ImageDraw.Draw(blob).ellipse((cx * W - R, cy * H - R, cx * W + R, cy * H + R),
                                         fill=cor + (70,))
            im.alpha_composite(blob.filter(ImageFilter.GaussianBlur(W * .12)))
        _bg_cache[key] = im
    return _bg_cache[key].copy()


def card_retrato(frame, h, raio=40, borda=8):
    """Jogo em pé num cartão com borda branca e sombra."""
    w = int(h * 9 / 16)
    im = frame.convert("RGBA").resize((w, h), Image.BILINEAR)
    im.putalpha(g.rounded((w, h), raio, g.WHITE).getchannel("A"))
    ring = g.rounded((w + 2 * borda, h + 2 * borda), raio + borda, g.WHITE + (255,))
    ring.alpha_composite(im, (borda, borda))
    out = g.shadow(ring.size, raio, 30, 170)
    p = (out.width - ring.width) // 2
    out.alpha_composite(ring, (p, p - 8))
    return out


def card_imagem(img, h, raio=36):
    w = int(h * img.width / img.height)
    im = img.convert("RGBA").resize((w, h), Image.LANCZOS)
    im.putalpha(g.rounded((w, h), raio, g.WHITE).getchannel("A"))
    out = g.shadow((w, h), raio, 30, 170)
    p = (out.width - w) // 2
    out.alpha_composite(im, (p, p - 8))
    return out


def logo_canto(im):
    lg = g.logo_image(84, 0.24)
    im.alpha_composite(g.set_alpha(lg, 0.9), (W - 84 - 36, H - 84 - 30))


def bloco_texto(im, t, x, tipo, titulo, sub, chips=()):
    """Etiqueta do tema + título grande + subtítulo + chips, entrando em sequência."""
    nome, cor = TAG[tipo]
    t *= 1.8  # entrada rápida
    a = g.clamp01(t / 0.25)
    dx = (1 - g.ease_out_back(t / 0.5)) * 60
    tag = g.sticker(nome, 34, cor, g.INK, g.F_DISPLAY)
    im.alpha_composite(g.set_alpha(tag, a), (int(x + dx - 12), 250))
    g.ACCENT[0] = cor
    words = titulo.split()
    lines, cur = [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if g.text_layer(test, 78, path=g.F_DISPLAY).width > 760 and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = test
    lines.append(cur)
    y = 350
    for k, ln in enumerate(lines):
        lt = t - 0.12 - k * 0.1
        if lt <= 0:
            continue
        hl = k == len(lines) - 1
        lay = g.text_layer(ln, 78, fill=cor if hl else g.WHITE, path=g.F_DISPLAY, shadow_a=150)
        im.alpha_composite(g.set_alpha(lay, g.clamp01(lt / 0.2)),
                           (int(x + (1 - ease_out_cubic(lt / 0.4)) * 80), int(y)))
        y += 100
    if sub and t > 0.45:
        lay = g.text_layer(sub, 42, fill=(215, 215, 230), path=g.F_SEMI)
        im.alpha_composite(g.set_alpha(lay, g.clamp01((t - 0.45) / 0.25)), (int(x), int(y + 20)))
        y += 90
    for k, ch in enumerate(chips):
        lt = t - 0.7 - k * 0.12
        if lt <= 0:
            continue
        lay = g.sticker(ch, 36, (40, 38, 62), g.WHITE, g.F_BOLD)
        lay = g.scaled(lay, g.lerp(0.6, 1, g.spring(lt / 0.4)))
        im.alpha_composite(lay, (int(x + (k % 2) * 300), int(y + 20 + (k // 2) * 90)))


# ----------------------------------------------------------------- cenas
# f(im, t, dur) -> desenha a cena no tempo local t

def cena_montagem(nomes, passo, titulo="30 JOGOS • celular e PC"):
    """Abertura agitada: 3 jogos por vez trocando a cada `passo` segundos."""
    srcs = [cel(n, (0.25 + 0.17 * k) % 0.8) for k, n in enumerate(nomes)]
    clips = {}

    def clip(j):
        if j not in clips:
            clips[j] = g.Clip(srcs[j][0], 540, 960, srcs[j][1], g.HEADER_PX)
        return clips[j]

    def f(im, t, dur):
        k = int(t / passo)
        lt = t - k * passo
        n = len(nomes)
        im.alpha_composite(fundo(30 + k % 4, (g.VIOLET, (255, 110, 150), g.SKY, (255, 206, 64))[k % 4]))
        punch = 1 + 0.10 * math.exp(-lt * 12)
        for j, (x, h, rot) in ((k + 3, (380, 700, 6)), (k + 6, (1540, 700, -6)), (k, (960, 940, 0))):
            j %= n
            card = card_retrato(clip(j).get(lt), h).rotate(rot, expand=True, resample=Image.BICUBIC)
            if x == 960:
                card = g.scaled(card, punch)
            g.put(im, card, x, H / 2 + (0 if x == 960 else 40))
            if x == 960:
                g.draw_sticker(im, nomes[j], 960, 70, 54, lt + 0.15, -3, g.WHITE, g.BLACK,
                               path=g.F_DISPLAY)
        if t > passo * 1.5:
            g.draw_sticker(im, titulo, 960, H - 70, 50, t - passo * 1.5, 2, g.LIME, g.INK,
                           path=g.F_DISPLAY)
        # flash rápido em cada troca
        if lt < 0.08 and t > 0.05:
            fl = Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - lt / 0.08))))
            im.alpha_composite(fl)
        logo_canto(im)
    return f


def cena_jogo(tipo, titulo, sub, src, lado, chips=(), nome=None, seed=2):
    st = {}

    def f(im, t, dur):
        if "c" not in st:
            st["c"] = g.Clip(src[0], 540, 960, src[1], g.HEADER_PX)
        im.alpha_composite(fundo(seed))
        fr = st["c"].get(t)
        card = card_retrato(fr, 860)
        k = g.spring(t / 0.3)
        vx = 1420 if lado == "dir" else 500
        g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.85, 1, k)), g.clamp01(t / 0.1)),
              vx, H / 2 + (1 - k) * 40)
        if nome:
            g.draw_sticker(im, nome, vx, 105, 40, t - 0.2, -3, g.WHITE, g.BLACK,
                           path=g.F_DISPLAY)
        bloco_texto(im, t, 140 if lado == "dir" else 1000, tipo, titulo, sub, chips)
        logo_canto(im)
    return f


def cena_arte(tipo, titulo, sub, img, lado, chips=(), seed=3, cor=None):
    def f(im, t, dur):
        im.alpha_composite(fundo(seed, cor or g.VIOLET))
        card = card_imagem(img, 900)
        k = g.spring(t / 0.3)
        z = 1 + 0.04 * t / dur
        vx = 1400 if lado == "dir" else 520
        g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.85, 1, k) * z), g.clamp01(t / 0.1)),
              vx, H / 2)
        bloco_texto(im, t, 140 if lado == "dir" else 1000, tipo, titulo, sub, chips)
        logo_canto(im)
    return f


def cena_pc(tipo, titulo, sub, src, chips=()):
    st = {}

    def f(im, t, dur):
        if "c" not in st:
            st["c"] = g.Clip(src[0], 1280, 720, src[1])
        im.alpha_composite(fundo(5, g.SKY, g.VIOLET))
        fr = st["c"].get(t)
        card = g.window_card(fr, 1080, 1.0, bar=not src[0].endswith("_pc.mp4"))
        k = g.spring(t / 0.3)
        g.put(im, g.set_alpha(g.scaled(card.rotate(-2, expand=True, resample=Image.BICUBIC),
                                       g.lerp(0.85, 1, k)), g.clamp01(t / 0.1)), 1360, H / 2)
        bloco_texto(im, t, 120, tipo, titulo, sub, chips)
        logo_canto(im)
    return f


def cena_duelo(tipo, titulo, sub, a, b):
    st = {}

    def f(im, t, dur):
        if not st:
            st["a"] = g.Clip(a[0], 540, 960, a[1], g.HEADER_PX)
            st["b"] = g.Clip(b[0], 540, 960, b[1], g.HEADER_PX)
        im.alpha_composite(fundo(7, (255, 90, 110), g.SKY))
        k = g.spring(t / 0.3)
        for j, (key, x, rot, nm, cor) in enumerate((("a", 1180, -4, "VOCÊ", g.LIME),
                                                   ("b", 1620, 4, "TEU AMIGO", g.WHITE))):
            card = card_retrato(st[key].get(t), 760).rotate(rot, expand=True, resample=Image.BICUBIC)
            g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.8, 1, k)), g.clamp01(t / 0.1)),
                  x, H / 2 + 30)
            g.draw_sticker(im, nm, x, 110, 42, t - 0.2 - j * 0.1, rot, cor, g.INK,
                           path=g.F_DISPLAY)
        if t > 0.4:
            g.put(im, g.scaled(g.sticker("VS", 76, "brand", g.INK, g.F_DISPLAY),
                               g.spring((t - 0.4) / 0.4)), 1400, H / 2 + 30)
        bloco_texto(im, t, 120, tipo, titulo, sub)
        logo_canto(im)
    return f


def cena_cta():
    def f(im, t, dur):
        im.alpha_composite(fundo(9))
        k = g.spring(t / 0.6)
        lg = g.logo_image(420, 0.24)
        g.put(im, g.shadow(lg.size, 100, 40, 170), 520, H / 2 + 14)
        g.put(im, g.scaled(lg, g.lerp(0.5, 1, k)), 520, H / 2)
        g.ACCENT[0] = g.LIME
        if t > 0.3:
            g.caption(im, "vem jogar com a gente!", 1300, 330, 84, t - 0.3, 1000,
                      highlight=(3,), per_word=0.08)
        if t > 0.8:
            b = g.cta_button(620, 120, "Jogar agora")
            g.put(im, g.scaled(b, g.spring((t - 0.8) / 0.45) * (1 + 0.03 * math.sin(t * 6))),
                  1300, 520)
        g.draw_sticker(im, "🔗 kavixbrasil.com.br", 1300, 680, 50, t - 0.8, 0)
        if t > 1.3:
            lay = g.text_layer("comenta teu nick que a gente se desafia 👇", 40,
                               fill=g.WHITE, path=g.F_BOLD, shadow_a=150)
            g.put(im, g.set_alpha(lay, g.clamp01((t - 1.3) / 0.3)), 1300, 810)
        if t > 1.6:
            lay = g.text_layer("celular  •  PC  •  sem baixar nada  •  itens no cadastro",
                               32, fill=(210, 210, 228), path=g.F_SEMI)
            g.put(im, g.set_alpha(lay, g.clamp01((t - 1.6) / 0.3)), 1300, 890)
    return f


# --------------------------------------------------------------- artes

def arte(slide):
    im = Image.open(os.path.join(C.OUT, slide)).convert("RGBA")
    return im.crop((0, 140, im.width, im.height - 120))


def arte_diarias():
    im = C.fundo(200, (255, 206, 64), C.VIOLET)
    C.sticker(im, "RECOMPENSA DIÁRIA", 540, 200, 56, -3, (255, 206, 64), C.INK)
    for k in range(7):
        r, q = divmod(k, 4)
        n_col = 4 if r == 0 else 3
        x = 540 + (q - (n_col - 1) / 2) * 240
        y = 520 + r * 340
        big = k == 6
        cw, ch = 220, 290
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
    C.texto(im, "quanto mais dias seguidos, melhor o prêmio 🔥", 540, 1110, 36, C.WHITE,
            g.F_BOLD, True)
    return im.crop((0, 120, 1080, 1230))


# ----------------------------------------------------------------- música

def _env(n, d):
    return np.exp(-np.arange(n) / g.SR / d)


def musica(dur, cortes, seed=11, bpm=128, drop=None):
    """House/eletrônica agitada: bumbo 4/4 desde o 1º segundo, chimbal em
    semicolcheias, palma forte, baixo rolando e stabs de acorde. Virada de
    caixa antes de `drop` e antes do final."""
    SR = g.SR
    rng = np.random.default_rng(seed)
    out = np.zeros(int(dur * SR) + SR)
    beat = 60 / bpm
    s16 = beat / 4
    prog = [(57, (0, 3, 7)), (53, (0, 4, 7)), (48, (0, 4, 7)), (55, (0, 4, 7))]  # Am F C G

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def add(sig, t):
        i = int(t * SR)
        if 0 <= i < len(out):
            j = min(len(out), i + len(sig))
            out[i:j] += sig[:j - i]

    def noise(n, k=3):
        x = rng.uniform(-1, 1, n)
        return x - np.convolve(x, np.ones(k) / k, "same")

    rolls = [x for x in (drop, dur - 12 * beat) if x]
    for b in range(int(dur / beat) + 1):
        t = b * beat
        root, chord = prog[(b // 4) % 4]
        em_virada = any(r - 2 * beat <= t < r for r in rolls)
        # bumbo (some durante a virada)
        if not em_virada:
            n = int(.28 * SR)
            tt = np.arange(n) / SR
            f = 48 + 110 * np.exp(-tt / .02)
            add(np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .14) * .9, t)
        # palma no 2 e 4
        if b % 2 == 1:
            n = int(.18 * SR)
            add(noise(n, 8) * _env(n, .05) * .32, t)
        # chimbal em semicolcheias (aberto no contratempo)
        for k in range(4):
            aberto = k == 2
            n = int((.16 if aberto else .04) * SR)
            add(noise(n) * _env(n, .05 if aberto else .012) * (.16 if aberto else .09 + .04 * (k % 2)),
                t + k * s16)
        # baixo rolando em semicolcheias (pula a cabeça do tempo, estilo house)
        for k in (1, 2, 3):
            n = int(s16 * .9 * SR)
            tt = np.arange(n) / SR
            f = hz(root - 24 + (12 if k == 3 else 0))
            saw = 2 * ((tt * f) % 1) - 1
            saw = np.convolve(saw, np.ones(8) / 8, "same")
            add(saw * np.minimum(1, tt / .004) * _env(n, .07) * .3, t + k * s16)
        # stabs de acorde sincopados
        if b % 4 in (0, 2):
            for off in ((0.5 * beat, 1.5 * beat) if b % 4 == 0 else (0.75 * beat,)):
                n = int(.22 * SR)
                tt = np.arange(n) / SR
                sig = np.zeros(n)
                for semi in chord + (12,):
                    f = hz(root + semi)
                    sig += np.sign(np.sin(2 * np.pi * f * tt)) * .4 + np.sin(2 * np.pi * 2 * f * tt) * .3
                sig = np.convolve(sig, np.ones(6) / 6, "same")
                add(sig * _env(n, .08) * .045, t + off)
    # viradas de caixa (acelerando) + subida de ruído
    for r in rolls:
        t0 = r - 2 * beat
        k, step = 0, beat / 2
        tt_ = t0
        while tt_ < r - 1e-3:
            n = int(.1 * SR)
            add(noise(n, 4) * _env(n, .04) * (.15 + .2 * (tt_ - t0) / (2 * beat)), tt_)
            step = beat / 2 if tt_ - t0 < beat else beat / 4 if tt_ - t0 < 1.5 * beat else beat / 8
            tt_ += step
        n = int(2 * beat * SR)
        add(noise(n, 30) * np.linspace(0, 1, n) ** 2 * .15, t0)
        n = int(.8 * SR)
        add(noise(n, 60) * _env(n, .3) * .2, r)  # impacto
    # 'swish' nas trocas de cena
    for c in cortes:
        n = int(.3 * SR)
        w = np.sin(np.linspace(0, np.pi, n)) ** 2
        add(noise(n, 20) * w * .1, c - .15)
    out = out[:int(dur * SR)]
    fade = int(1.0 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = np.tanh(out * 1.6)
    return out / max(1e-6, np.abs(out).max()) * .9


# --------------------------------------------------------------- roteiro

BPM = 128
BEAT = 60 / BPM
JOGOS = ["Espinhos", "Empilha", "Bolhas", "Hélice", "Cobrinha", "Órbita", "Quebra Blocos",
         "Trampolim", "Reflexo", "Canhão", "Ricochete", "Zigue-Zague", "Boliche", "Troca Cor",
         "Pula Corda", "Gravidade"]


def roteiro():
    b = BEAT
    return [
        (16 * 2 * b / 2, cena_montagem(JOGOS, b)),
        (6 * b, cena_pc("beneficio", "sem baixar nada", "roda no navegador do celular e do PC",
                        pc("Quebra Blocos", .4), chips=("celular", "PC"))),
        (6 * b, cena_arte("ranked", "modo competitivo com patentes", "sobe de Ouro até Diamante",
                          arte("modelo_6_ranking_competitivo/slide_02.jpg"), "dir",
                          chips=("Diamante", "Rubi", "Esmeralda", "Safira"), seed=6,
                          cor=(255, 110, 150))),
        (6 * b, cena_duelo("modo", "batalha online", "desafia teus amigos ao vivo",
                           cel("Reflexo", .3), g.at(g.game(0, "Reflexo")["celular"], .75))),
        (6 * b, cena_arte("ganhos", "recompensas todo dia", "volta todo dia e ganha mais",
                          arte_diarias(), "esq", seed=8, cor=(255, 206, 64))),
        (6 * b, cena_arte("ranked", "ranking geral e de cada jogo", "teu recorde soma no ranking",
                          arte("modelo_7_desafio_do_recorde/slide_03.jpg"), "esq", seed=12,
                          cor=(255, 110, 150))),
        (6 * b, cena_arte("ganhos", "passe de batalha", "30 níveis com trilha grátis e premium",
                          arte("modelo_5_passe_de_batalha/slide_02.jpg"), "dir", seed=14,
                          cor=(255, 206, 64))),
        (6 * b, cena_jogo("modo", "pra todo tipo de jogador", "do relaxante ao mais difícil",
                          cel("Hélice", .4), "esq", nome="Hélice", seed=16)),
        (6 * b, cena_arte("ganhos", "+90 skins pra tua bolinha", "lendárias, épicas e raras",
                          arte("modelo_3_skins/slide_02.jpg"), "dir", seed=18, cor=(255, 206, 64))),
        (6 * b, cena_jogo("beneficio", "itens exclusivos no cadastro", "é só criar a conta",
                          cel("Trampolim", .4), "esq", nome="Trampolim", seed=20,
                          chips=("itens raros", "100% grátis"))),
        (12 * b, cena_cta()),
    ]


def render():
    cenas = roteiro()
    starts, t = [], 0.0
    for d, _ in cenas:
        starts.append(t)
        t += d
    dur = t
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, "kavix_convite_grupo.mp4")
    wav = out + ".wav"
    g.write_wav(wav, musica(dur, starts[1:], drop=starts[1], bpm=BPM))
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264",
           "-preset", "medium", "-crf", "20", "-maxrate", "8M", "-bufsize", "16M",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(int(dur * FPS)):
        g.FRAME[0] = fi
        tt = fi / FPS
        i = max(k for k, s in enumerate(starts) if s <= tt)
        im = Image.new("RGBA", (W, H), (8, 7, 20, 255))
        cenas[i][1](im, tt - starts[i], cenas[i][0])
        lt = tt - starts[i]
        if i > 0 and lt < PUNCH:
            z = 1 + 0.07 * (1 - lt / PUNCH) ** 2
            zw, zh = int(W / z), int(H / z)
            im = im.crop(((W - zw) // 2, (H - zh) // 2, (W + zw) // 2, (H + zh) // 2)).resize((W, H))
        proc.stdin.write(im.convert("RGB").tobytes())
        g.close_idle_clips()
    proc.stdin.close()
    proc.wait()
    g.close_clips()
    os.remove(wav)
    return out, dur


LEGENDA = """🎮 Galera, bora jogar junto? Conheçam o KAVIX ARCADE!

São 30 jogos rápidos pra jogar no celular ou no PC, direto no navegador, sem baixar nada.

🕹️ Modos de jogo: reflexo, lógica, precisão, relaxantes e desafios difíceis
⚔️ Batalha online contra os amigos
💎 Ranked com patentes: Ouro, Safira, Esmeralda, Rubi e Diamante
🏆 Ranking geral e de cada jogo (teu recorde soma pontos)
🎁 Recompensas todo dia
🎫 Passe de batalha com 30 níveis, trilha grátis e premium
✨ +90 skins pra montar tua bolinha

Quem criar conta agora ainda ganha itens exclusivos 🎁

👉 kavixbrasil.com.br

Comenta aqui teu nick no jogo que a gente se desafia 👇 Quem chega primeiro no Diamante? 💎

#kavix #kavixarcade #jogosonline #jogosgratis #gamerbrasil"""


def main():
    out, dur = render()
    with open(os.path.join(OUT, "legenda.txt"), "w") as fh:
        fh.write(LEGENDA + "\n")
    print("ok:", out, round(dur, 1), "s")


if __name__ == "__main__":
    main()
