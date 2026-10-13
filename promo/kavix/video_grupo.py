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
FADE = 0.35

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

def cena_intro():
    def f(im, t, dur):
        im.alpha_composite(fundo(1))
        k = g.spring(t / 0.6)
        lg = g.logo_image(380, 0.24)
        g.put(im, g.shadow(lg.size, 90, 40, 170), W / 2, 380 + 14)
        g.put(im, g.scaled(lg, g.lerp(0.5, 1, k)), W / 2, 380)
        if t > 0.5:
            g.ACCENT[0] = g.LIME
            g.caption(im, "bora jogar com a gente?", W / 2, 700, 92, t - 0.5, 1500,
                      highlight=(2, 3), per_word=0.08)
        if t > 1.3:
            lay = g.text_layer("30 jogos  •  ranked com patentes  •  recompensas todo dia",
                               40, fill=(220, 220, 235), path=g.F_BOLD)
            g.put(im, g.set_alpha(lay, g.clamp01((t - 1.3) / 0.3)), W / 2, 830)
    return f


def cena_jogo(tipo, titulo, sub, src, lado, chips=(), nome=None, seed=2):
    st = {}

    def f(im, t, dur):
        if "c" not in st:
            st["c"] = g.Clip(src[0], 540, 960, src[1], g.HEADER_PX)
        im.alpha_composite(fundo(seed))
        fr = st["c"].get(t)
        card = card_retrato(fr, 860)
        k = g.spring(t / 0.55)
        vx = 1420 if lado == "dir" else 500
        g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.85, 1, k)), g.clamp01(t / 0.2)),
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
        k = g.spring(t / 0.55)
        z = 1 + 0.04 * t / dur
        vx = 1400 if lado == "dir" else 520
        g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.85, 1, k) * z), g.clamp01(t / 0.2)),
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
        k = g.spring(t / 0.55)
        g.put(im, g.set_alpha(g.scaled(card.rotate(-2, expand=True, resample=Image.BICUBIC),
                                       g.lerp(0.85, 1, k)), g.clamp01(t / 0.2)), 1360, H / 2)
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
        k = g.spring(t / 0.55)
        for j, (key, x, rot, nm, cor) in enumerate((("a", 1180, -4, "VOCÊ", g.LIME),
                                                   ("b", 1620, 4, "TEU AMIGO", g.WHITE))):
            card = card_retrato(st[key].get(t), 760).rotate(rot, expand=True, resample=Image.BICUBIC)
            g.put(im, g.set_alpha(g.scaled(card, g.lerp(0.8, 1, k)), g.clamp01(t / 0.2)),
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
        g.draw_sticker(im, "🔗 kavixbrasil.com.br", 1300, 680, 50, t - 1.0, 0)
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


def musica(dur, cortes, seed=11, bpm=118):
    """House animada: bumbo 4/4, chimbal no contratempo, palma no 2 e 4,
    baixo saltitante e acordes 'pluck' (bem diferente do trap dos reels)."""
    SR = g.SR
    rng = np.random.default_rng(seed)
    out = np.zeros(int(dur * SR))
    beat = 60 / bpm
    prog = [(57, (0, 3, 7)), (53, (0, 4, 7)), (48, (0, 4, 7)), (55, (0, 4, 7))]  # Am F C G

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def add(sig, t):
        i = int(t * SR)
        if 0 <= i < len(out):
            j = min(len(out), i + len(sig))
            out[i:j] += sig[:j - i]

    n_beats = int(dur / beat)
    for b in range(n_beats):
        t = b * beat
        bar = b // 4
        root, chord = prog[bar % 4]
        intro = t < 3.5
        # bumbo
        if not intro:
            n = int(.3 * SR)
            tt = np.arange(n) / SR
            f = 50 + 90 * np.exp(-tt / .025)
            add(np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .16) * .8, t)
        # palma no 2 e 4
        if b % 2 == 1 and not intro:
            n = int(.2 * SR)
            x = rng.uniform(-1, 1, n)
            x = x - np.convolve(x, np.ones(8) / 8, "same")
            add(x * _env(n, .06) * .22, t)
        # chimbal no contratempo
        n = int(.06 * SR)
        x = rng.uniform(-1, 1, n)
        x = x - np.convolve(x, np.ones(3) / 3, "same")
        add(x * _env(n, .02) * (.12 if intro else .18), t + beat / 2)
        # baixo no contratempo
        if not intro:
            n = int(beat * .45 * SR)
            tt = np.arange(n) / SR
            f = hz(root - 24 + (12 if b % 4 == 3 else 0))
            saw = 2 * ((tt * f) % 1) - 1
            saw = np.convolve(saw, np.ones(10) / 10, "same")
            add(saw * np.minimum(1, tt / .005) * _env(n, .12) * .35, t + beat / 2)
        # acordes pluck: no tempo 1 e no "e" do 2 e do 3 (ritmo de house)
        for off in ((0, .75 * beat * 2 / 2, 1.5 * beat) if b % 4 == 0 else ((.5 * beat,) if b % 2 else ())):
            n = int(.35 * SR)
            tt = np.arange(n) / SR
            sig = np.zeros(n)
            for semi in chord + (12,):
                f = hz(root + semi)
                sig += (np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * 2 * f * tt))
            add(sig * _env(n, .11) * .05, t + off)
    # pad suave por baixo
    tt = np.arange(len(out)) / SR
    pad = np.zeros(len(out))
    for k in range(int(dur / (4 * beat)) + 1):
        i0, i1 = int(k * 4 * beat * SR), min(len(out), int((k + 1) * 4 * beat * SR))
        if i0 >= len(out):
            break
        root, chord = prog[k % 4]
        for semi in chord:
            pad[i0:i1] += np.sin(2 * np.pi * hz(root + semi - 12) * tt[i0:i1]) * .03
    out += pad
    # 'whoosh' suave nas trocas de cena
    for c in cortes:
        n = int(.5 * SR)
        x = rng.uniform(-1, 1, n)
        w = np.sin(np.linspace(0, np.pi, n)) ** 2
        add((x - np.convolve(x, np.ones(40) / 40, "same")) * w * .08, c - .25)
    fade = int(1.2 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out[:int(.3 * SR)] *= np.linspace(0, 1, int(.3 * SR))
    out = np.tanh(out * 1.4)
    return out / max(1e-6, np.abs(out).max()) * .88


# --------------------------------------------------------------- roteiro

def roteiro():
    return [
        (4.2, cena_intro()),
        (4.2, cena_jogo("modo", "30 jogos rápidos", "partidas de 1 minuto, de reflexo, lógica e precisão",
                        cel("Espinhos", .3), "dir", nome="Espinhos", seed=2)),
        (4.2, cena_pc("beneficio", "sem baixar nada", "roda no navegador do celular e do PC",
                      pc("Quebra Blocos", .4), chips=("celular", "PC"))),
        (3.8, cena_jogo("modo", "um jogo diferente a cada partida", "Empilha, Cobrinha, Bolhas, Hélice…",
                        cel("Empilha", .4), "esq", nome="Empilha", seed=4)),
        (4.5, cena_arte("ranked", "modo competitivo com patentes", "sobe de Ouro até Diamante",
                        arte("modelo_6_ranking_competitivo/slide_02.jpg"), "dir",
                        chips=("Diamante", "Rubi", "Esmeralda", "Safira"), seed=6,
                        cor=(255, 110, 150))),
        (4.5, cena_duelo("modo", "batalha online", "desafia teus amigos ao vivo",
                         cel("Reflexo", .3), g.at(g.game(0, "Reflexo")["celular"], .75))),
        (4.2, cena_arte("ganhos", "recompensas todo dia", "volta todo dia e ganha mais",
                        arte_diarias(), "esq", seed=8, cor=(255, 206, 64))),
        (3.6, cena_jogo("modo", "partidas que viciam", "e cada recorde vale ponto",
                        cel("Bolhas", .5), "dir", nome="Bolhas", seed=10)),
        (4.2, cena_arte("ranked", "ranking geral e de cada jogo", "teu recorde soma no ranking",
                        arte("modelo_7_desafio_do_recorde/slide_03.jpg"), "esq", seed=12,
                        cor=(255, 110, 150))),
        (4.2, cena_arte("ganhos", "passe de batalha", "30 níveis com trilha grátis e premium",
                        arte("modelo_5_passe_de_batalha/slide_02.jpg"), "dir", seed=14,
                        cor=(255, 206, 64))),
        (3.6, cena_jogo("modo", "pra todo tipo de jogador", "do relaxante ao mais difícil",
                        cel("Hélice", .4), "esq", nome="Hélice", seed=16)),
        (4.0, cena_arte("ganhos", "+90 skins pra tua bolinha", "lendárias, épicas e raras",
                        arte("modelo_3_skins/slide_02.jpg"), "dir", seed=18, cor=(255, 206, 64))),
        (3.6, cena_jogo("beneficio", "itens exclusivos no cadastro", "é só criar a conta",
                        cel("Trampolim", .4), "esq", nome="Trampolim", seed=20,
                        chips=("itens raros", "100% grátis"))),
        (6.5, cena_cta()),
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
    g.write_wav(wav, musica(dur, starts[1:]))
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
        if i > 0 and tt - starts[i] < FADE:
            prev = Image.new("RGBA", (W, H), (8, 7, 20, 255))
            cenas[i - 1][1](prev, cenas[i - 1][0] - FADE + (tt - starts[i]), cenas[i - 1][0])
            im = Image.blend(prev, im, (tt - starts[i]) / FADE)
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
