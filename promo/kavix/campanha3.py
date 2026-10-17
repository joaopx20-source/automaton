#!/usr/bin/env python3
"""Campanha 3: 300 reels do KAVIX ARCADE sobre JOGOS, SKINS e RANKED.

10 formatos novos (30 vídeos cada), diferentes das campanhas 1 e 2:
  jogos:  ficha (ficha do jogo), escada (fácil → difícil), escolha (1, 2 ou 3),
          cronometro (10 segundos de jogo)
  skins:  abrindo (comum → lendário), kit (monta teu kit), top3 (3 skins de um tipo)
  ranked: patentes (Ouro → Diamante), vaga_top (ranking com vaga pra ti),
          duelo_online (VOCÊ vs TEU AMIGO)

Uso:
    python3 promo/kavix/campanha3.py lista
    python3 promo/kavix/campanha3.py render [n ...]
    python3 promo/kavix/campanha3.py plano [AAAA-MM-DD]

Saída: campanha3/videos/NNN_<formato>_<assunto>.mp4, plano_postagem.{csv,json}
"""
import csv
import datetime as dt
import functools
import json
import math
import os
import random
import sys
from multiprocessing import Pool

import campanha as c1
import carrossel as C
import gerar_videos as g
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "campanha3")
W, H, PLATFORM = c1.W, c1.H, c1.PLATFORM
cel, pc, cap, label, last, nomes = c1.cel, c1.pc, c1.cap, c1.label, c1.last, c1.nomes
URL_LABEL = "🔗 kavixbrasil.com.br"
g.SHOW_HANDLE[0] = False    # sem logo/@ no topo (não parecer story)
g.SHOW_PROGRESS[0] = False  # sem barra de progresso de story

# gênero e dificuldade (1 a 5) de cada jogo
INFO = {
    "Espinhos": ("reflexo", 3), "Passagem": ("reflexo", 3), "Quebra Blocos": ("precisão", 2),
    "Três Pistas": ("reflexo", 3), "Pega Tudo": ("reflexo", 1), "Órbita": ("timing", 3),
    "Reflexo": ("reflexo", 4), "Gravidade": ("timing", 4), "Troca Cor": ("reflexo", 2),
    "Empilha": ("timing", 2), "Cobrinha": ("estratégia", 3), "Memória": ("memória", 3),
    "Ricochete": ("precisão", 4), "Balanço": ("timing", 3), "Escudo": ("reflexo", 3),
    "Corte": ("precisão", 3), "Pulso": ("timing", 4), "Hélice": ("relaxante", 2),
    "Boliche": ("precisão", 2), "Ponte": ("timing", 3), "Bolhas": ("mira", 2),
    "Encaixe": ("lógica", 3), "Trampolim": ("timing", 2), "Pula Corda": ("timing", 3),
    "Zigue-Zague": ("reflexo", 3), "Equilíbrio": ("precisão", 5), "Espelho": ("lógica", 4),
    "Canhão": ("mira", 2), "Fio": ("precisão", 5), "Sinal": ("reflexo", 4),
}
NIVEL = {1: "muito fácil", 2: "fácil", 3: "médio", 4: "difícil", 5: "insano"}
NIVEL_COR = {1: (120, 230, 140), 2: (198, 255, 61), 3: (255, 214, 64), 4: (255, 150, 60),
             5: (255, 80, 110)}
RAR_COR = {"comum": (200, 205, 220), "raro": (80, 170, 255), "epico": (190, 110, 255),
           "lendario": (255, 200, 60)}
PAT = list(reversed(C.PATENTES))  # Ouro → Diamante


def url_label(t0, t1, y=0.8):
    return label(t0, t1, URL_LABEL, y, 44, -2)


def info(nome):
    return INFO.get(nome, ("arcade", 3))


def bg_clip(st, src, c, key="bg"):
    if key not in st:
        st[key] = g.Clip(src[0], 540, 960, src[1], g.HEADER_PX)
    return st[key]


def finish(img, c, t, texts):
    img.alpha_composite(g.top_shade(c.W, c.H))
    g.handle(img, c)
    g.draw_texts(img, c, t, texts)


def glass(w, h, u, a=40):
    return g.rounded((w, h), int(40 * u), (20, 16, 44, 215),
                     outline=(255, 255, 255, 70), width=max(2, int(3 * u)))


# ------------------------------------------------------------ cenas: jogos

def sc_ficha(src, nome, texts=()):
    """Ficha do jogo: gênero, dificuldade (5 barras), duração e plataformas."""
    st = {}
    gen, dif = info(nome)

    def f(img, t, dur, c):
        if "clip" not in st:
            st["clip"] = g.Clip(src[0], c.panel_w, c.panel_h, src[1], g.HEADER_PX)
        g.game_panel(img, c, st["clip"], t, 1.0 + 0.04 * t / dur)
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        g.draw_sticker(img, nome, c.text_cx, c.Y(0.2) + c.top_off * 0.6, 66 * c.u, t - 0.05,
                       -3, path=g.F_DISPLAY)
        cw, ch = int(c.W * 0.84), int(700 * c.u)
        k = g.spring((t - 0.3) / 0.5)
        if t < 0.3:
            return g.draw_texts(img, c, t, texts)
        card = glass(cw, ch, c.u)
        dd = ImageDraw.Draw(card)
        pad = int(44 * c.u)
        y = pad
        lab = g.text_layer("FICHA DO JOGO", int(44 * c.u), fill=g.ACCENT[0], path=g.F_DISPLAY)
        card.alpha_composite(lab, (pad, y))
        y += int(100 * c.u)
        rows = [("gênero", gen), ("dificuldade", None), ("partida", "~1 minuto"),
                ("onde", "celular e PC")]
        for r, (a, b) in enumerate(rows):
            lt = t - 0.6 - r * 0.35
            if lt < 0:
                break
            al = g.clamp01(lt / 0.2)
            ka = g.text_layer(a, int(44 * c.u), fill=(190, 186, 215), path=g.F_SEMI)
            card.alpha_composite(g.set_alpha(ka, al), (pad, y))
            x0 = int(cw * 0.44)
            if b is None:
                for p in range(5):
                    on = p < dif and lt > 0.1 + p * 0.12
                    col = NIVEL_COR[dif] if on else (60, 56, 90)
                    dd.rounded_rectangle((x0 + p * int(70 * c.u), y + int(6 * c.u),
                                          x0 + p * int(70 * c.u) + int(56 * c.u),
                                          y + int(52 * c.u)), int(12 * c.u), fill=col + (255,))
                tx = g.text_layer(NIVEL[dif], int(40 * c.u), fill=NIVEL_COR[dif], path=g.F_BOLD)
                if lt > 0.8:
                    card.alpha_composite(tx, (x0, y + int(62 * c.u)))
            else:
                kb = g.text_layer(b, int(50 * c.u), fill=g.WHITE, path=g.F_BOLD)
                card.alpha_composite(g.set_alpha(kb, al), (x0, y - int(2 * c.u)))
            y += int(140 * c.u) if b is None else int(108 * c.u)
        g.put(img, g.shadow(card.size, int(40 * c.u), 24 * c.u, 160), c.text_cx,
              c.Y(0.53) + 10 * c.u)
        g.put(img, g.set_alpha(g.scaled(card, g.lerp(0.6, 1, k)), g.clamp01((t - 0.3) / 0.12)),
              c.text_cx, c.Y(0.53))
        g.draw_texts(img, c, t, texts)
    return f


def sc_tres(srcs, nomes3, texts=()):
    """Três jogos lado a lado, com 1, 2 e 3: 'qual tu escolhe?'."""
    st = {}

    def f(img, t, dur, c):
        sw, sh = int(c.W / 3), int(c.H * 0.52)
        if not st:
            for k, s in enumerate(srcs):
                st[k] = g.Clip(s[0], sw - 12, sh, s[1], g.HEADER_PX)
        img.alpha_composite(g.blurred_bg(st[1].get(t), c.W, c.H, 0.7))
        for k in range(3):
            lt = t - k * 0.15
            if lt < 0:
                continue
            fr = st[k].get(t).convert("RGBA")
            fr.putalpha(g.rounded(fr.size, int(28 * c.u), g.WHITE).getchannel("A"))
            e = g.spring(lt / 0.45)
            x = sw * k + sw / 2
            y = c.Y(0.56) + (1 - e) * 200 * c.u
            g.put(img, g.set_alpha(fr, g.clamp01(lt / 0.1)), x, y)
            g.draw_sticker(img, str(k + 1), x, y - sh / 2 - 10 * c.u, 70 * c.u, lt - 0.2,
                           (-4, 3, -2)[k], c1.ACCENTS[k], g.BLACK, path=g.F_DISPLAY)
            g.draw_sticker(img, nomes3[k], x, y + sh / 2 - 40 * c.u, 34 * c.u, lt - 0.35,
                           (2, -3, 3)[k], g.WHITE, g.BLACK, path=g.F_DISPLAY, max_w=sw - 16)
        finish(img, c, t, texts)
    return f


def sc_timer(src, nome, n=10, texts=()):
    """Jogo com contagem regressiva grande de `n` segundos."""
    st = {}

    def f(img, t, dur, c):
        if "clip" not in st:
            st["clip"] = g.Clip(src[0], c.panel_w, c.panel_h, src[1], g.HEADER_PX)
        g.game_panel(img, c, st["clip"], t)
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        tt = min(t, n)
        rest = max(0, math.ceil(n - tt - 1e-6))
        R = int(120 * c.u)
        ring = Image.new("RGBA", (2 * R + 20, 2 * R + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(ring)
        d.ellipse((10, 10, 2 * R + 10, 2 * R + 10), fill=(12, 10, 30, 200))
        frac = 1 - tt / n
        col = g.ACCENT[0] if rest > 3 else (255, 80, 110)
        d.arc((10, 10, 2 * R + 10, 2 * R + 10), -90, -90 + 360 * frac, fill=col + (255,),
              width=int(18 * c.u))
        num = g.text_layer(str(rest), int(110 * c.u), fill=g.WHITE, path=g.F_DISPLAY)
        ring.alpha_composite(num, ((ring.width - num.width) // 2,
                                   (ring.height - num.height) // 2 - int(6 * c.u)))
        pulse = 1 + 0.08 * math.exp(-((t % 1.0) * 8)) if t < n else 1
        g.put(img, g.scaled(ring, pulse), c.text_cx, c.Y(0.34) + c.top_off * 0.3)
        g.draw_sticker(img, nome, c.text_cx, c.Y(0.2) + c.top_off * 0.5, 50 * c.u, t, -3,
                       path=g.F_DISPLAY)
        if t >= n:
            g.draw_sticker(img, "ACABOU! ⏰", c.text_cx, c.Y(0.52), 80 * c.u, t - n, -4,
                           (255, 80, 110), g.WHITE, path=g.F_DISPLAY)
        g.draw_texts(img, c, t, texts)
    return f


# ------------------------------------------------------------ cenas: skins

def _glow(size, col, a=150):
    gl = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse((size * 0.4, size * 0.4, size * 1.6, size * 1.6), fill=col + (a,))
    return gl.filter(ImageFilter.GaussianBlur(size * 0.18))


def sc_abrindo(src_bg, items, texts=()):
    """Cartas misteriosas: tremem, piscam e revelam (comum → lendário)."""
    st = {}

    def f(img, t, dur, c):
        img.alpha_composite(g.blurred_bg(bg_clip(st, src_bg, c).get(t), c.W, c.H, 0.66))
        per = dur / len(items)
        i = min(len(items) - 1, int(t / per))
        it, lt = items[i], t - i * per
        col = RAR_COR.get(it["raridade"], g.WHITE)
        size = int(c.W * 0.52)
        cy = c.Y(0.45)
        # mini trilha de raridades no topo
        for k, x in enumerate(items):
            on = k <= i
            stc = g.sticker(x["raridade_nome"].upper(), int(26 * c.u),
                            RAR_COR.get(x["raridade"], g.WHITE) if on else (70, 66, 100),
                            g.INK if on else (150, 146, 180))
            g.put(img, stc, c.text_cx + (k - (len(items) - 1) / 2) * c.W * 0.22,
                  c.Y(0.165) + c.top_off * 0.4)
        sus = per * 0.42
        if lt < sus:
            sh = math.sin(lt * 60) * 14 * c.u * (lt / sus)
            card = g.rounded((int(size * 0.8), int(size * 1.05)), int(40 * c.u),
                             (40, 34, 80, 255), outline=col + (255,), width=int(8 * c.u))
            q = g.text_layer("?", int(260 * c.u), fill=col, path=g.F_DISPLAY)
            card.alpha_composite(q, ((card.width - q.width) // 2, (card.height - q.height) // 2))
            g.put(img, _glow(size, col, int(90 + 100 * lt / sus)), c.text_cx, cy)
            g.put(img, card.rotate(sh * 0.3, expand=True, resample=Image.BICUBIC),
                  c.text_cx + sh, cy)
        else:
            rl = lt - sus
            if rl < 0.12:
                img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, int(200 * (1 - rl / 0.12)))))
            k = g.spring(rl / 0.45)
            g.put(img, _glow(size, col), c.text_cx, cy)
            sk = g.skin_image(it["arquivo"], size)
            g.put(img, g.scaled(sk, g.lerp(0.3, 1, k)), c.text_cx,
                  cy + math.sin(t * 4) * 10 * c.u)
            g.draw_sticker(img, it["raridade_nome"].upper(), c.text_cx, cy - size * 0.62,
                           50 * c.u, rl, -4, col, g.INK, path=g.F_DISPLAY)
            g.caption(img, it["nome"], c.text_cx, cy + size * 0.66, c.cap_size * 0.85, rl - 0.1,
                      c.max_w, highlight=(0,) if it["raridade"] == "lendario" else ())
        finish(img, c, t, texts)
    return f


def sc_kit(src_bg, items, texts=()):
    """Monta teu kit: cada parte entra grande e vai para a lista de baixo."""
    st = {}

    def f(img, t, dur, c):
        img.alpha_composite(g.blurred_bg(bg_clip(st, src_bg, c).get(t), c.W, c.H, 0.66))
        n = len(items)
        per = (dur - 1.2) / n
        i = min(n - 1, int(t / per))
        lt = t - i * per
        it = items[i]
        col = g.hexrgb(it["cor"])
        size = int(c.W * 0.34)
        cy = c.Y(0.27) + c.top_off * 0.3
        if t < n * per:
            k = g.spring(lt / 0.4)
            g.put(img, _glow(size, col), c.text_cx, cy)
            g.put(img, g.scaled(g.skin_image(it["arquivo"], size), g.lerp(0.3, 1, k)),
                  c.text_cx, cy + math.sin(t * 4) * 8 * c.u)
            g.draw_sticker(img, it["tipo_nome"].upper(), c.text_cx, cy - size * 0.66, 44 * c.u,
                           lt, -4, g.ACCENT[0], g.BLACK, path=g.F_DISPLAY)
        else:
            g.draw_sticker(img, "KIT COMPLETO ✅", c.text_cx, cy - 40 * c.u, 64 * c.u, t - n * per, -4,
                           g.ACCENT[0], g.BLACK, path=g.F_DISPLAY)
        # lista
        rw, rh = int(c.W * 0.8), int(112 * c.u)
        y0 = c.Y(0.42)
        for k in range(n):
            if t < k * per + 0.3:
                break
            x = items[k]
            e = g.spring((t - k * per - 0.3) / 0.35)
            row = g.rounded((rw, rh), int(26 * c.u), (20, 16, 44, 220),
                            outline=g.hexrgb(x["cor"]) + (200,), width=max(2, int(3 * c.u)))
            ic = g.skin_image(x["arquivo"], int(rh * 0.84))
            row.alpha_composite(ic, (int(10 * c.u), (rh - ic.height) // 2))
            a = g.text_layer(x["tipo_nome"], int(32 * c.u), fill=(180, 176, 210), path=g.F_SEMI)
            b = g.text_layer(x["nome"], int(42 * c.u), fill=g.WHITE, path=g.F_BOLD)
            row.alpha_composite(a, (int(rh + 14 * c.u), int(10 * c.u)))
            row.alpha_composite(b, (int(rh + 14 * c.u), int(46 * c.u)))
            chip = g.sticker(x["raridade_nome"].upper(), int(26 * c.u), g.hexrgb(x["cor"]), g.INK)
            row.alpha_composite(chip, (rw - chip.width - int(10 * c.u), (rh - chip.height) // 2))
            g.put(img, g.set_alpha(row, g.clamp01(e * 2)),
                  c.text_cx + (1 - e) * 300 * c.u, y0 + k * (rh + 12 * c.u) + rh / 2)
        finish(img, c, t, texts)
    return f


def sc_top3(src_bg, items, texts=()):
    """Top 3: 3º, 2º e 1º lugar, cada um com sua vez."""
    st = {}

    def f(img, t, dur, c):
        img.alpha_composite(g.blurred_bg(bg_clip(st, src_bg, c).get(t), c.W, c.H, 0.64))
        per = dur / 3
        i = min(2, int(t / per))
        lt = t - i * per
        it = items[2 - i]
        col = g.hexrgb(it["cor"])
        size = int(c.W * 0.5)
        cy = c.Y(0.44)
        k = g.spring(lt / 0.45)
        g.put(img, _glow(size, col), c.text_cx, cy)
        g.put(img, g.scaled(g.skin_image(it["arquivo"], size), g.lerp(0.2, 1, k)), c.text_cx,
              cy + math.sin(t * 4) * 10 * c.u)
        g.draw_sticker(img, f"#{3 - i}", c.text_cx - size * 0.42, cy - size * 0.5,
                       96 * c.u, lt, -8, (g.ACCENT[0] if i == 2 else g.WHITE), g.BLACK,
                       path=g.F_DISPLAY)
        g.draw_sticker(img, it["raridade_nome"].upper(), c.text_cx + size * 0.3,
                       cy - size * 0.52, 36 * c.u, lt - 0.1, 5, col, g.INK)
        g.caption(img, it["nome"], c.text_cx, cy + size * 0.64, c.cap_size * 0.9, lt - 0.15,
                  c.max_w, highlight=(0,) if i == 2 else ())
        finish(img, c, t, texts)
    return f


# ------------------------------------------------------------ cenas: ranked

@functools.lru_cache(maxsize=16)
def gema_img(k, s):
    _, c1_, c2_ = PAT[k]
    return C.gema(c1_, c2_, s)


def sc_patentes(src_bg, ate=4, texts=()):
    """Escada de patentes (Ouro embaixo, Diamante em cima) com subida animada."""
    st = {}

    def f(img, t, dur, c):
        img.alpha_composite(g.blurred_bg(bg_clip(st, src_bg, c).get(t), c.W, c.H, 0.66))
        n = len(PAT)
        y_top, y_bot = c.Y(0.22) + c.top_off * 0.3, c.Y(0.6)
        step = (y_bot - y_top) / (n - 1)
        x = c.text_cx - c.W * 0.12
        prog = g.clamp01((t - 0.4) / max(0.5, dur * 0.7)) * ate
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((x - 8 * c.u, y_top, x + 8 * c.u, y_bot), int(8 * c.u),
                            fill=(60, 56, 90, 255))
        yh = y_bot - step * prog
        d.rounded_rectangle((x - 8 * c.u, yh, x + 8 * c.u, y_bot), int(8 * c.u),
                            fill=g.ACCENT[0] + (255,))
        for k in range(n):
            y = y_bot - k * step
            on = prog >= k - 0.02
            s = int(130 * c.u * (1.15 if on and k == round(min(prog, ate)) else 1))
            gm = gema_img(k, int(130 * c.u))
            if not on:
                gm = g.set_alpha(gm.convert("LA").convert("RGBA"), 0.45)
            g.put(img, g.scaled(gm, s / (130 * c.u)), x, y)
            nm = g.text_layer(PAT[k][0], int(48 * c.u), fill=g.WHITE if on else (130, 126, 160),
                              path=g.F_DISPLAY, shadow_a=150)
            g.composite(img, nm, x + 100 * c.u, y - nm.height / 2)
        finish(img, c, t, texts)
    return f


AV_CORES = [(255, 200, 60), (190, 200, 220), (230, 150, 90), (120, 170, 255), (190, 110, 255)]


def sc_vaga(src_bg, nome, texts=()):
    """Ranking do jogo com nomes escondidos e uma vaga piscando: 'teu nome aqui?'."""
    st = {}
    vaga = 0

    def f(img, t, dur, c):
        img.alpha_composite(g.blurred_bg(bg_clip(st, src_bg, c).get(t), c.W, c.H, 0.66))
        cw = int(c.W * 0.84)
        rh = int(140 * c.u)
        y0 = c.Y(0.26) + c.top_off * 0.3
        head = g.sticker(f"🏆 RANKING · {nome.upper()}", int(40 * c.u), g.ACCENT[0], g.BLACK,
                         g.F_DISPLAY)
        g.put(img, g.scaled(head, g.lerp(0.4, 1, g.spring(t / 0.4))), c.text_cx, y0 - 40 * c.u)
        for r in range(5):
            lt = t - 0.3 - r * 0.15
            if lt < 0:
                continue
            e = g.spring(lt / 0.4)
            hi = r == vaga
            blink = hi and (int(t * 3) % 2 == 0) and t > 1.5
            row = g.rounded((cw, rh), int(30 * c.u),
                            (g.ACCENT[0] + (235,)) if blink else (22, 18, 48, 225),
                            outline=(PAT[4 - r][1] + (220,)), width=max(2, int(4 * c.u)))
            fg = g.INK if blink else g.WHITE
            pos = g.text_layer(f"{r + 1}º", int(54 * c.u), fill=fg, path=g.F_DISPLAY)
            row.alpha_composite(pos, (int(26 * c.u), (rh - pos.height) // 2))
            av = C.avatar(int(rh * 0.66), "?", AV_CORES[r])
            row.alpha_composite(av, (int(130 * c.u), (rh - av.height) // 2))
            txt = "TEU NOME AQUI? 👀" if hi else ("???" if r % 2 else "pode ser tu")
            tl = g.text_layer(txt, int(48 * c.u), fill=fg, path=g.F_BOLD)
            row.alpha_composite(tl, (int(130 * c.u + av.width + 22 * c.u), (rh - tl.height) // 2))
            gm = gema_img(4 - r, int(rh * 0.7))
            row.alpha_composite(gm, (cw - gm.width - int(20 * c.u), (rh - gm.height) // 2))
            g.put(img, g.set_alpha(row, g.clamp01(e * 2)), c.text_cx + (1 - e) * 260 * c.u,
                  y0 + 40 * c.u + r * (rh + 14 * c.u) + rh / 2)
        finish(img, c, t, texts)
    return f


def sc_1v1(a, b, texts=()):
    """O mesmo jogo em dois celulares lado a lado: VOCÊ x TEU AMIGO."""
    st = {}

    def f(img, t, dur, c):
        if not st:
            st["a"] = g.Clip(a[0], 540, 960, a[1], g.HEADER_PX)
            st["b"] = g.Clip(b[0], 540, 960, b[1], g.HEADER_PX)
        fa, fb = st["a"].get(t), st["b"].get(t)
        img.alpha_composite(g.blurred_bg(fa, c.W, c.H, 0.6))
        ph = int(c.H * 0.42)
        k = g.spring(t / 0.5)
        for j, (fr, x, rot, nm, bg) in enumerate(((fa, c.W * 0.27, -4, "VOCÊ", g.ACCENT[0]),
                                                 (fb, c.W * 0.73, 4, "TEU AMIGO", g.WHITE))):
            card = g.phone_card(fr, ph, c.u).rotate(rot, expand=True, resample=Image.BICUBIC)
            y = c.Y(0.52) + (1 - k) * 200 * c.u
            g.put(img, g.set_alpha(card, g.clamp01(t / 0.12)), x, y)
            g.draw_sticker(img, nm, x, y - ph / 2 - 30 * c.u, 50 * c.u, t - 0.1 - j * 0.1,
                           rot, bg, g.BLACK, path=g.F_DISPLAY)
        if t > 0.3:
            vs = g.sticker("VS", int(70 * c.u), "brand", g.INK, g.F_DISPLAY)
            g.put(img, g.scaled(vs, max(0.05, g.spring((t - 0.3) / 0.4))), c.cx, c.Y(0.52))
        finish(img, c, t, texts)
    return f


# ------------------------------------------------------------ montagem

CTAS3 = [("Joga agora no site", "Jogar agora"), ("Cria tua conta grátis", "Criar conta"),
         ("Bora subir no ranking?", "Jogar agora"), ("Tua skin te espera", "Criar conta"),
         ("30 jogos de graça", "Jogar agora"), ("Desafia teus amigos", "Entrar agora")]


def cta(i, src):
    title, button = CTAS3[i % len(CTAS3)]
    return (5.0, g.sc_cta(src, title, button))


def build(i, scenes, extra=()):
    rng = random.Random(3000 + i)
    s = g.build(scenes, bpm=rng.choice([124, 130, 136, 142, 148, 154]),
                prog_=rng.choice(["AFCG", "FCGA", "ADFE", "AFDE", "CGAF", "DEAF", "GACF"]),
                seed=4000 + i, extra=extra)
    s["accent"] = c1.ACCENTS[(i + 1) % len(c1.ACCENTS)]
    assert s["dur"] >= 15, (i, s["dur"])
    return s


def ordem_rng(i):
    lst = nomes()[:]
    random.Random(6000 + i).shuffle(lst)
    return lst


def skins_tipo(tipos):
    return [x for x in g.skins() if x["tipo"] in tipos]


# ---- jogos

GANCHO_FICHA = ["conhece o {n}?", "esse aqui é o {n} 👀", "jogo do dia: {n}",
                "tu já jogou {n}?", "{n} em 15 segundos"]


def spec_ficha(i, nome, k):
    gen, dif = info(nome)
    gancho = GANCHO_FICHA[k % len(GANCHO_FICHA)].format(n=nome)
    sc = [(2.4, g.sc_game(cel(nome, 0.15), texts=[cap(0.1, 2.4, gancho, 0.42, last(gancho))])),
          (6.6, sc_ficha(cel(nome, 0.45), nome, texts=[url_label(4.0, 6.6, 0.82)])),
          (2.6, g.sc_pc(pc(nome, 0.5), texts=[
              cap(0.1, 2.6, f"nível {NIVEL[dif]}: aguenta?", 0.24, (1,))])),
          cta(i, cel(nome, 0.8))]
    return build(i, sc, extra=[("pop", 2.9 + 0.35 * r) for r in range(4)])


def spec_escada(i, trio):
    sc = []
    for k, nome in enumerate(trio):
        dif = info(nome)[1]
        sc.append((3.0, g.sc_game(cel(nome, 0.3 + 0.2 * k), name=nome, texts=[
            label(0.0, 3.0, ("1. ", "2. ", "3. ")[k] + NIVEL[dif].upper(), 0.33, 56,
                  (-4, 3, -3)[k], NIVEL_COR[dif])])))
    sc[0] = (3.0, g.sc_game(cel(trio[0], 0.3), name=trio[0], texts=[
        label(0.0, 3.0, "1. " + NIVEL[info(trio[0])[1]].upper(), 0.33, 56, -4,
              NIVEL_COR[info(trio[0])[1]]),
        cap(0.2, 3.0, "do fácil ao insano 👇", 0.45, (3,))]))
    sc.append((2.4, g.sc_game(cel(trio[2], 0.75), texts=[
        cap(0.1, 2.4, "até onde tu chega? 👀", 0.42, (3,)), url_label(0.3, 2.4)])))
    sc.append(cta(i, cel(trio[1], 0.8)))
    return build(i, sc)


def spec_escolha(i, trio):
    sc = [(6.2, sc_tres([cel(n, 0.4) for n in trio], trio, texts=[
              cap(0.0, 6.2, "qual tu escolhe? 1, 2 ou 3 👇", 0.17, (4, 5, 6), 0.8)])),
          (2.0, g.sc_game(cel(trio[0], 0.6), name="1 · " + trio[0])),
          (2.0, g.sc_game(cel(trio[1], 0.6), name="2 · " + trio[1])),
          (2.0, g.sc_game(cel(trio[2], 0.6), name="3 · " + trio[2], texts=[url_label(0.2, 2.0)])),
          cta(i, cel(trio[0], 0.85))]
    return build(i, sc, extra=[("pop", 0.2 + 0.15 * k) for k in range(3)])


def spec_cronometro(i, nome, k):
    pergunta = ["quantos pontos tu faz em 10s?", "consegue passar de 5 em 10s?",
                "10 segundos: bate esse?"][k % 3]
    sc = [(12.0, sc_timer(cel(nome, 0.2 + (k % 3) * 0.2), nome, 10, texts=[
              cap(0.0, 2.6, "10 segundos de " + nome, 0.62, last(nome, 2)),
              cap(10.0, 12.0, pergunta, 0.66, last(pergunta, 2))])),
          (2.4, g.sc_pc(pc(nome, 0.5), texts=[
              cap(0.1, 2.4, "tenta no celular ou no PC", 0.24, (3, 5)), url_label(0.3, 2.4)])),
          cta(i, cel(nome, 0.85))]
    return build(i, sc, extra=[("pop", 10.0)])


# ---- skins

def spec_abrindo(i, itens, k):
    o = ordem_rng(i)
    hook = ["abrindo do comum ao lendário 😳", "qual raridade vem? 👀",
            "do cinza ao dourado ✨"][k % 3]
    sc = [(2.0, g.sc_game(cel(o[0], 0.4), texts=[
              label(0.0, 2.0, "SKINS", 0.3, 64, -4, g.ACCENT[0]),
              cap(0.2, 2.0, hook, 0.43, last(hook))])),
          (9.6, sc_abrindo(cel(o[1], 0.3), itens, texts=[url_label(7.5, 9.6, 0.84)])),
          cta(i, cel(o[2], 0.6))]
    return build(i, sc, extra=[("pop", 2.0 + 2.4 * r + 1.0) for r in range(4)])


def spec_kit(i, itens, k):
    o = ordem_rng(i)
    hook = ["monta teu kit comigo 👕", "kit pra entrar no ranked 😎", "meu kit favorito ✨",
            "kit de quem joga muito 🔥", "monta o kit e vem jogar 🎮"][k % 5]
    sc = [(2.0, g.sc_game(cel(o[0], 0.4), texts=[cap(0.1, 2.0, hook, 0.42, last(hook))])),
          (9.2, sc_kit(cel(o[1], 0.3), itens, texts=[
              cap(8.0, 9.2, "e o teu, como fica? 👇", 0.37, (4,), 0.8)])),
          cta(i, cel(o[2], 0.6))]
    return build(i, sc, extra=[("pop", 2.0 + r * 1.6) for r in range(len(itens))])


TIPO_PLURAL = {"roupa": "roupas", "chapeu": "chapéus", "olhos": "olhos", "aura": "auras",
               "cor": "cores", "rastro": "rastros", "moldura": "molduras", "titulo": "títulos"}


def spec_top3(i, tipo, itens, k):
    o = ordem_rng(i)
    hook = f"3 {TIPO_PLURAL[tipo]} que tu precisa ter"
    sc = [(2.2, g.sc_game(cel(o[0], 0.4), texts=[
              label(0.0, 2.2, "TOP 3", 0.3, 70, -4, g.ACCENT[0]),
              cap(0.2, 2.2, hook, 0.43, (1,))])),
          (8.4, sc_top3(cel(o[1], 0.3), itens, texts=[url_label(5.8, 8.4, 0.84)])),
          cta(i, cel(o[2], 0.6))]
    return build(i, sc, extra=[("pop", 2.2 + 2.8 * r) for r in range(3)])


# ---- ranked

GANCHO_PAT = ["em qual patente tu tá? 👇", "do Ouro ao Diamante 💎", "quanto tempo pra chegar no Diamante?",
              "comenta tua patente 👇", "ranked de verdade no navegador 😳"]


def spec_patentes(i, k):
    o = ordem_rng(i)
    hook = GANCHO_PAT[k % len(GANCHO_PAT)]
    sc = [(2.4, g.sc_game(cel(o[0], 0.35), name=o[0], texts=[
              label(0.0, 2.4, "MODO RANKED", 0.32, 60, -4, g.ACCENT[0]),
              cap(0.2, 2.4, hook, 0.45, last(hook))])),
          (7.0, sc_patentes(cel(o[1], 0.3), texts=[
              cap(0.0, 7.0, "sobe de patente jogando 💎", 0.7, (4,), 0.75)])),
          (2.4, g.sc_game(cel(o[2], 0.5), name=o[2], texts=[
              cap(0.1, 2.4, "cada partida conta ponto", 0.42, (3,)), url_label(0.3, 2.4)])),
          cta(i, cel(o[3], 0.6))]
    return build(i, sc, extra=[("pop", 2.4 + 0.4 + r * 1.2) for r in range(5)])


def spec_vaga(i, nome, k):
    hook = ["tem vaga no top 5 do " + nome, "o ranking do " + nome + " tá te esperando",
            "quem vai ser o 1º no " + nome + "?"][k % 3]
    sc = [(2.6, g.sc_game(cel(nome, 0.3), name=nome, texts=[cap(0.1, 2.6, hook, 0.45, last(hook))])),
          (7.0, sc_vaga(cel(nome, 0.55), nome, texts=[
              cap(4.4, 7.0, "cria conta e entra no ranking", 0.72, (4,), 0.75)])),
          (2.2, g.sc_pc(pc(nome, 0.5), texts=[url_label(0.1, 2.2, 0.78)])),
          cta(i, cel(nome, 0.85))]
    return build(i, sc, extra=[("pop", 2.9 + 0.15 * r) for r in range(5)])


def spec_duelo(i, nome, k):
    hook = ["1v1 no " + nome, "quem ganha esse? 👇", "chama teu amigo pro " + nome][k % 3]
    sc = [(7.4, sc_1v1(cel(nome, 0.2), cel(nome, 0.65), texts=[
              cap(0.4, 3.6, hook, 0.2, last(hook)),
              cap(3.7, 7.4, "batalha online ao vivo ⚔️", 0.2, (1, 2))])),
          (3.0, g.sc_game(cel(nome, 0.85), name=nome, texts=[
              cap(0.1, 3.0, "manda o link pro teu amigo", 0.42, (4,)), url_label(0.4, 3.0)])),
          cta(i, cel(nome, 0.5))]
    return build(i, sc, extra=[("pop", 0.3)])


# ------------------------------------------------------------ catálogo

def trios(seed, chave):
    """30 trios de jogos diferentes, usando cada jogo 3 vezes."""
    js = nomes()
    rng = random.Random(seed)
    out = []
    for r in range(3):
        lst = js[:]
        rng.shuffle(lst)
        out += [lst[k:k + 3] for k in range(0, 30, 3)]
    return [sorted(t, key=chave) for t in out]


def catalogo():
    js = nomes()
    itens = []
    for k, n in enumerate(js):
        itens.append(("ficha", n, functools.partial(spec_ficha, nome=n, k=k),
                      f"{GANCHO_FICHA[k % 5].format(n=n)} {info(n)[0]}, nível {NIVEL[info(n)[1]]} 🎮"))
    for k, tr in enumerate(trios(11, lambda n: info(n)[1])):
        itens.append(("escada", " ".join(tr), functools.partial(spec_escada, trio=tr),
                      f"do fácil ao insano: {tr[0]} → {tr[1]} → {tr[2]} 😳 até onde tu chega?"))
    for k, tr in enumerate(trios(23, lambda n: 0)):
        itens.append(("escolha", " ".join(tr), functools.partial(spec_escolha, trio=tr),
                      f"qual tu escolhe? 1 {tr[0]}, 2 {tr[1]} ou 3 {tr[2]} 👇"))
    for k, n in enumerate(random.Random(31).sample(js, 30)):
        itens.append(("cronometro", n, functools.partial(spec_cronometro, nome=n, k=k),
                      f"10 segundos de {n} ⏱️ quantos pontos tu faz?"))
    # skins
    por_rar = {r: [x for x in g.skins() if x["raridade"] == r]
               for r in ("comum", "raro", "epico", "lendario")}
    rng = random.Random(41)
    for k in range(30):
        seq = [rng.choice(por_rar[r]) for r in ("comum", "raro", "epico", "lendario")]
        itens.append(("abrindo", seq[-1]["nome"], functools.partial(spec_abrindo, itens=seq, k=k),
                      f"abrindo do comum ao lendário 😳 no final veio {seq[-1]['nome']} ✨"))
    tipos_kit = ["cor", "chapeu", "olhos", "roupa", "aura"]
    rng = random.Random(53)
    for k in range(30):
        kit = [rng.choice(skins_tipo((tp,))) for tp in tipos_kit]
        itens.append(("kit", f"kit {k + 1}", functools.partial(spec_kit, itens=kit, k=k),
                      "monta teu kit 👕 " + " + ".join(x["nome"] for x in kit)))
    rng = random.Random(67)
    tipos = ["chapeu", "roupa", "aura", "olhos", "cor", "rastro", "moldura", "titulo"]
    usados = set()
    for k in range(30):
        tp = tipos[k % len(tipos)]
        pool = sorted(skins_tipo((tp,)), key=lambda x: -g.RAR_ORDEM[x["raridade"]])
        for _ in range(50):
            esc = rng.sample(pool[:min(len(pool), 9)], 3)
            esc.sort(key=lambda x: -g.RAR_ORDEM[x["raridade"]])
            key = (tp, tuple(x["id"] for x in esc))
            if key not in usados:
                break
        usados.add(key)
        itens.append(("top3", f"{TIPO_PLURAL[tp]} {k + 1}",
                      functools.partial(spec_top3, tipo=tp, itens=esc, k=k),
                      f"3 {TIPO_PLURAL[tp]} que tu precisa ter: " +
                      ", ".join(x["nome"] for x in esc) + " 🔥"))
    # ranked
    for k in range(30):
        itens.append(("patentes", f"ranked {k + 1}", functools.partial(spec_patentes, k=k),
                      f"{GANCHO_PAT[k % 5]} Ouro → Safira → Esmeralda → Rubi → Diamante 💎"))
    for k, n in enumerate(random.Random(71).sample(js, 30)):
        itens.append(("vaga_top", n, functools.partial(spec_vaga, nome=n, k=k),
                      f"o top 5 do {n} tem vaga pra ti 🏆 teu nome aqui?"))
    for k, n in enumerate(random.Random(83).sample(js, 30)):
        itens.append(("duelo_online", n, functools.partial(spec_duelo, nome=n, k=k),
                      f"1v1 no {n} ⚔️ batalha online: chama teu amigo"))
    # intercala formatos (nunca dois iguais seguidos)
    rng = random.Random(97)
    pos = []
    por_fmt = {}
    for it in itens:
        por_fmt.setdefault(it[0], []).append(it)
    for f_, lst in por_fmt.items():
        for k, it in enumerate(lst):
            pos.append(((k + 0.2 + 0.6 * rng.random()) / len(lst), it))
    ordem = [it for _, it in sorted(pos, key=lambda x: x[0])]
    for k in range(1, len(ordem)):
        if ordem[k][0] == ordem[k - 1][0]:
            for m in range(k + 1, len(ordem)):
                if ordem[m][0] != ordem[k - 1][0] and (m + 1 >= len(ordem) or
                                                       ordem[m + 1][0] != ordem[k][0]):
                    ordem[k], ordem[m] = ordem[m], ordem[k]
                    break
    out = []
    for i, (fmt, assunto, fn, gancho) in enumerate(ordem, 1):
        slug = g._slug(assunto)[:40].strip("_")
        out.append(dict(id=i, formato=fmt, assunto=assunto, gancho=gancho, fn=fn,
                        arquivo=f"videos/{i:03d}_{fmt}_{slug}.mp4"))
    return out


CHAMADAS3 = ["Joga agora 👉 kavixbrasil.com.br (link na bio)",
             "Sem baixar nada: abre kavixbrasil.com.br e joga 🎮",
             "Cria tua conta grátis e ganha itens exclusivos 🎁 link na bio",
             "Ranked, skins e 30 jogos no celular e no PC 🔗 kavixbrasil.com.br",
             "Salva esse vídeo e joga depois 📌 kavixbrasil.com.br",
             "Chama teu amigo e vem pro ranking 🏆 kavixbrasil.com.br"]


TAGS_FIXAS = ["#kavix", "#kavixarcade", "#roblox", "#jogosonline", "#jogos", "#mobile"]
TAGS_VIRAIS3 = ["#fyp", "#viral", "#foryou", "#paravoce", "#explore", "#trend", "#viralvideo",
                "#foryoupage", "#gaming", "#games", "#mobilegames", "#gamer"]


def tags_virais(seed):
    """Fixas em todas as legendas + virais sorteadas."""
    rng = random.Random(seed)
    extra = (rng.sample(TAGS_VIRAIS3, 4) +
             rng.sample([t for t in c1.TAGS_ROBLOX if t != "#roblox"], 1) +
             rng.sample([t for t in c1.TAGS_JOGOS if t not in TAGS_FIXAS], 1))
    return list(dict.fromkeys(TAGS_FIXAS + extra + ["#gamerbrasil"]))[:13]


def legenda(v):
    tags = tags_virais(9500 + v["id"])
    texto = f"{v['gancho']}\n{CHAMADAS3[v['id'] % len(CHAMADAS3)]}"
    return texto, " ".join(tags), (v["gancho"][:80] + " #shorts").strip()


@functools.lru_cache(maxsize=1)
def _catalogo():
    return {v["id"]: v for v in catalogo()}


def render_one(vid):
    v = _catalogo()[vid]
    path = os.path.join(OUT, v["arquivo"])
    if os.path.exists(path) and os.path.getsize(path) > 200_000:
        return path + " (já existia)"
    tmp = path[:-4] + ".tmp.mp4"
    g.render_spec(v["fn"](v["id"]), W, H, PLATFORM, tmp)
    os.replace(tmp, path)
    return path


RAW = ("https://raw.githubusercontent.com/joaopx20-source/automaton/"
       "claude/kavix-promotional-videos-e6f1vd/promo/kavix/campanha3/")


def plano(vs, inicio=None):
    os.makedirs(OUT, exist_ok=True)
    posts = []
    for k, v in enumerate(vs):
        n_dia = k // c1.POR_DIA + 1
        dia = inicio + dt.timedelta(days=n_dia - 1) if inicio else None
        hora = c1.HORARIOS[k % c1.POR_DIA]
        texto, tags, yt = legenda(v)
        posts.append({
            "n": v["id"], "dia_campanha": n_dia,
            "data": dia.isoformat() if dia else "", "hora": hora,
            "data_hora": f"{dia.isoformat()}T{hora}:00-03:00" if dia else "",
            "fuso": c1.FUSO, "arquivo": v["arquivo"], "url_download": RAW + v["arquivo"],
            "formato": v["formato"], "assunto": v["assunto"],
            "redes": ["Instagram", "Facebook", "TikTok", "YouTube Shorts"],
            "legenda_instagram_facebook": f"{texto}\n\n{tags}",
            "legenda_tiktok": f"{texto}\n\n{tags}",
            "titulo_youtube": yt[:100],
            "descricao_youtube": f"{texto}\n\n{tags} #shorts",
            "hashtags": tags,
        })
    with open(os.path.join(OUT, "plano_postagem.json"), "w") as fh:
        json.dump(posts, fh, ensure_ascii=False, indent=2)
    campos = ["n", "dia_campanha", "data", "hora", "data_hora", "arquivo", "url_download",
              "formato", "legenda_instagram_facebook", "legenda_tiktok", "titulo_youtube",
              "descricao_youtube"]
    with open(os.path.join(OUT, "plano_postagem.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(posts)
    print("ok:", len(posts), "posts em", posts[-1]["dia_campanha"], "dias")
    return posts


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lista"
    vs = catalogo()
    if cmd == "lista":
        for v in vs:
            print(f"{v['id']:3d}  {v['formato']:13s} {v['assunto']}")
        print(len(vs), "vídeos")
    elif cmd == "render":
        sel = set(int(x) for x in sys.argv[2:]) or {v["id"] for v in vs}
        with Pool(int(os.environ.get("KAVIX_PROCS", "3"))) as pool:
            for p in pool.imap_unordered(render_one, [v["id"] for v in vs if v["id"] in sel]):
                print("ok:", p, flush=True)
    elif cmd == "plano":
        plano(vs, dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None)


if __name__ == "__main__":
    main()
