#!/usr/bin/env python3
"""Campanha 2: mais 100 reels do KAVIX ARCADE focados em conversão
(levar a pessoa a jogar em kavixbrasil.com.br).

Formatos diferentes da campanha 1: desafio do dia, pergunta frequente, meme,
skin do dia, tutorial em 3 passos, duelo de skins e tier list. Em todos o
endereço do site aparece durante o vídeo, não só no final.

Uso:
    python3 promo/kavix/campanha2.py lista
    python3 promo/kavix/campanha2.py render [n ...]
    python3 promo/kavix/campanha2.py plano              # calendário sem datas (Dia 1..25)
    python3 promo/kavix/campanha2.py plano 2026-12-01   # preenche as datas a partir do dia

Saída: campanha2/videos/NNN_<formato>_<assunto>.mp4, plano_postagem.{csv,json}
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
import gerar_videos as g
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "campanha2")
W, H, PLATFORM = c1.W, c1.H, c1.PLATFORM
cel, pc, cap, label, last, nomes = c1.cel, c1.pc, c1.cap, c1.label, c1.last, c1.nomes

URL_LABEL = "🔗 kavixbrasil.com.br"


def url_label(t0, t1, y=0.8):
    """Endereço do site no meio do vídeo (conversão)."""
    return label(t0, t1, URL_LABEL, y, 44, -2)


# ------------------------------------------------------------ cenas novas

def sc_faq(src, pergunta, texts=()):
    """Balão 'pergunta que todo mundo faz' sobre o jogo, como resposta em vídeo."""
    st = {}

    def f(img, t, dur, c):
        if "clip" not in st:
            st["clip"] = g.Clip(src[0], c.panel_w, c.panel_h, src[1], g.HEADER_PX)
        g.game_panel(img, c, st["clip"], t, 1.0 + 0.05 * t / dur)
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        # balão
        k = g.spring(t / 0.45)
        bw = int(c.W * 0.8)
        top = g.text_layer("💬 pergunta que todo mundo faz", int(36 * c.u),
                           fill=(110, 110, 125), path=g.F_SEMI)
        q = g.text_layer(pergunta, int(68 * c.u), fill=g.BLACK, path=g.F_BLACK)
        if q.width > bw - 60 * c.u:
            q = g.scaled(q, (bw - 60 * c.u) / q.width)
        bh = int(top.height + q.height + 70 * c.u)
        box = g.rounded((bw, bh), int(34 * c.u), (255, 255, 255, 250))
        box.alpha_composite(top, (int(30 * c.u), int(22 * c.u)))
        box.alpha_composite(q, (int(30 * c.u), int(30 * c.u + top.height)))
        sh = g.shadow(box.size, int(34 * c.u), 20 * c.u, 140)
        cy = c.Y(0.27) + c.top_off * 0.5
        g.put(img, g.set_alpha(g.scaled(sh, g.lerp(0.6, 1, k)), g.clamp01(t / 0.1)),
              c.text_cx, cy + 8 * c.u)
        g.put(img, g.set_alpha(g.scaled(box, g.lerp(0.6, 1, k)), g.clamp01(t / 0.1)),
              c.text_cx, cy)
        g.draw_texts(img, c, t, texts)
    return f


def sc_steps(steps, texts=()):
    """Tutorial: cada passo com número grande e a cena (celular ou PC)."""
    st = {}

    def f(img, t, dur, c):
        per = dur / len(steps)
        i = min(len(steps) - 1, int(t / per))
        lt = t - i * per
        kind, src, txt = steps[i]
        key = f"c{i}"
        if key not in st:
            if kind == "pc":
                st[key] = g.Clip(src[0], 1280, 720, src[1])
            else:
                st[key] = g.Clip(src[0], c.panel_w, c.panel_h, src[1], g.HEADER_PX)
        clip = st[key]
        if kind == "pc":
            fr = clip.get(lt)
            img.alpha_composite(g.blurred_bg(fr, c.W, c.H, 0.5))
            card = g.window_card(fr, int(c.W * 0.94), c.u,
                                 bar=not src[0].endswith("_pc.mp4"))
            g.put(img, g.scaled(card, g.lerp(0.8, 1, g.spring(lt / 0.4))), c.cx, c.Y(0.5))
        else:
            g.game_panel(img, c, clip, lt)
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        g.draw_sticker(img, f"PASSO {i + 1}", c.text_cx, c.Y(0.21) + c.top_off * 0.5,
                       60 * c.u, lt, -4, g.ACCENT[0], g.BLACK, path=g.F_DISPLAY)
        g.caption(img, txt, c.text_cx, c.Y(0.7), c.cap_size * 0.9, lt - 0.15, c.max_w,
                  highlight=last(txt))
        g.draw_texts(img, c, t, texts)
    return f


TIER_CORES = {"S": (255, 90, 110), "A": (255, 170, 60), "B": (250, 220, 70),
              "C": (120, 220, 120)}


def sc_tier(src_bg, tiers, texts=()):
    """Tier list: linhas S/A/B/C com os nomes dos jogos entrando um a um."""
    st = {}

    def f(img, t, dur, c):
        if "bg" not in st:
            st["bg"] = g.Clip(src_bg[0], 540, 960, src_bg[1], g.HEADER_PX)
        img.alpha_composite(g.blurred_bg(st["bg"].get(t), c.W, c.H, 0.62))
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        rows = list(tiers.items())
        rh = int(c.H * 0.1)
        y0 = c.Y(0.32)
        n = 0
        for r, (tier, jogos) in enumerate(rows):
            y = y0 + r * (rh + 18 * c.u)
            box = Image.new("RGBA", (int(c.W * 0.86), rh), (255, 255, 255, 30))
            ImageDraw.Draw(box).rectangle((0, 0, rh, rh), fill=TIER_CORES[tier] + (255,))
            lt = g.text_layer(tier, int(rh * 0.6), fill=g.BLACK, path=g.F_DISPLAY)
            box.alpha_composite(lt, ((rh - lt.width) // 2, (rh - lt.height) // 2))
            g.composite(img, box, c.text_cx - box.width / 2, y)
            x = c.text_cx - box.width / 2 + rh + 16 * c.u
            for j in jogos:
                when = 0.5 + n * 0.55
                n += 1
                if t < when:
                    continue
                stk = g.sticker(j, int(38 * c.u), g.WHITE, g.BLACK, g.F_DISPLAY)
                s = g.lerp(0.3, 1, g.spring((t - when) / 0.4))
                g.put(img, g.scaled(stk, s), x + stk.width / 2, y + rh / 2)
                x += stk.width - 10 * c.u
        g.draw_texts(img, c, t, texts)
    return f


def sc_skin_duel(src_bg, a, b, texts=()):
    """Duas skins lado a lado: A ou B."""
    st = {}

    def f(img, t, dur, c):
        if "bg" not in st:
            st["bg"] = g.Clip(src_bg[0], 540, 960, src_bg[1], g.HEADER_PX)
        img.alpha_composite(g.blurred_bg(st["bg"].get(t), c.W, c.H, 0.6))
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        size = int(c.W * 0.4)
        for k, (it, lado) in enumerate(((a, -1), (b, 1))):
            lt = t - 0.3 - k * 0.25
            if lt < 0:
                continue
            e = g.spring(lt / 0.5)
            col = g.hexrgb(it["cor"])
            x = c.text_cx + lado * c.W * 0.22
            y = c.Y(0.5) + math.sin(t * 3 + k) * 10 * c.u
            glow = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse((size * 0.5, size * 0.5, size * 1.5, size * 1.5),
                                         fill=col + (120,))
            from PIL import ImageFilter
            glow = glow.filter(ImageFilter.GaussianBlur(size * 0.15))
            g.put(img, g.scaled(glow, g.lerp(0.4, 1, e)), x, y)
            g.put(img, g.scaled(g.skin_image(it["arquivo"], size), g.lerp(0.2, 1, e)), x, y)
            g.draw_sticker(img, "A" if k == 0 else "B", x, y - size * 0.72, 60 * c.u, lt,
                           -5 * lado, g.ACCENT[0], g.BLACK, path=g.F_DISPLAY)
            g.draw_sticker(img, it["nome"], x, y + size * 0.7, 44 * c.u, lt - 0.1, 3 * lado,
                           g.WHITE, g.BLACK, path=g.F_DISPLAY, max_w=c.W * 0.44)
            g.draw_sticker(img, it["raridade_nome"].upper(), x, y + size * 0.92, 32 * c.u,
                           lt - 0.2, 0, col, g.INK)
        vs = g.sticker("VS", int(56 * c.u), "brand", g.INK, g.F_DISPLAY)
        if t > 0.8:
            g.put(img, g.scaled(vs, g.spring((t - 0.8) / 0.4)), c.text_cx, c.Y(0.5))
        g.draw_texts(img, c, t, texts)
    return f


def sc_skin_one(src_bg, it, texts=()):
    """Uma skin em destaque, girando devagar, com raridade e tipo."""
    return g.sc_skin_reveal(src_bg, [it], texts)


# --------------------------------------------------------------- conteúdos

CTAS2 = [("Joga agora no site", "Jogar agora"), ("Cria tua conta grátis", "Criar conta"),
         ("Teu recorde começa hoje", "Jogar agora"), ("Bora pro KAVIX?", "Entrar agora"),
         ("30 jogos te esperando", "Jogar agora")]


def cta(i, src):
    title, button = CTAS2[i % len(CTAS2)]
    return (5.0, g.sc_cta(src, title, button))


def build(i, scenes, extra=()):
    rng = random.Random(1000 + i)
    s = g.build(scenes, bpm=rng.choice([128, 134, 140, 146, 152]),
                prog_=rng.choice(["AFCG", "FCGA", "ADFE", "AFDE", "CGAF", "DEAF"]),
                seed=2000 + i, extra=extra)
    s["accent"] = c1.ACCENTS[(i + 2) % len(c1.ACCENTS)]
    assert s["dur"] >= 15, (i, s["dur"])
    return s


METAS = [10, 15, 20, 25, 30]
DESAFIO_FALAS = ["manda print nos comentários 📸", "marca quem consegue 👇",
                 "duvido tu bater 😤", "comenta teu recorde 👇", "quem passar é lenda 👑"]

FAQ = [("precisa baixar alguma coisa?", "não! roda direto no navegador 🙌"),
       ("funciona no celular?", "funciona! é só abrir o site 📱"),
       ("dá pra jogar no PC?", "dá sim, no navegador do PC 💻"),
       ("é de graça?", "é! joga de graça 🎮"),
       ("quantos jogos tem?", "30 jogos e contando 🔥"),
       ("como eu ganho skins?", "cria tua conta e já ganha itens 🎁"),
       ("qual é o site?", "kavixbrasil.com.br 🔗"),
       ("roda em celular fraco?", "roda leve no navegador 📱"),
       ("precisa de cadastro pra jogar?", "cadastro rápido e ainda ganha itens 🎁"),
       ("qual o jogo mais difícil?", "Fio... boa sorte 💀"),
       ("qual o mais viciante?", "Empilha, fácil 🫠"),
       ("tem jogo de reflexo?", "tem vários: Pulso, Sinal, Corte ⚡"),
       ("dá pra jogar no intervalo?", "partidas rapidinhas ⏱️"),
       ("tem jogo tipo cobrinha?", "tem a própria Cobrinha 🐍"),
       ("tem coisa pra quem curte Roblox?", "minigames rápidos e skins 👀")]

MEMES = [("eu às 22h: só uma partida", "eu às 3h:", "3h"),
         ("expectativa: jogo fácil ❌", "realidade:", "real"),
         ("minha mãe: vai dormir", "eu no KAVIX:", "mae"),
         ("o professor explicando", "eu no intervalo:", "aula"),
         ("eu achando que sou bom", "o jogo Fio:", "fio"),
         ("meu amigo: esse é fácil", "o nível 3:", "nivel"),
         ("quando a fila não anda", "eu tranquilão:", "fila"),
         ("eu jurando que é o último", "eu 10 jogos depois:", "ultimo"),
         ("bateria 5%", "eu tentando bater o recorde:", "bateria"),
         ("domingo à noite", "eu descobrindo 30 jogos:", "domingo"),
         ("meu recorde: 12", "meu irmão: 47", "irmao"),
         ("quando o wifi cai", "o KAVIX no navegador:", "wifi"),
         ("ninguém:", "eu no Empilha:", "empilha"),
         ("eu: vou só testar", "eu 2 horas depois:", "testar"),
         ("segunda-feira", "eu no ônibus jogando:", "segunda")]

TUTORIAL = [
    ["entra em kavixbrasil.com.br 🔗", "escolhe um dos 30 jogos 🎮", "joga e bate teu recorde 🔥"],
    ["abre o navegador 🌐", "digita kavixbrasil.com.br ⌨️", "pronto, já tá jogando 🙌"],
    ["no celular ou no PC 📱💻", "entra no site 🔗", "cria conta e ganha itens 🎁"],
    ["sem baixar nada 🙌", "toca no jogo 👆", "segura o recorde 🏆"],
    ["cria tua conta 📝", "veste tua bolinha 👕", "desafia teus amigos 😤"],
    ["link na bio 🔗", "escolhe o jogo 🎮", "joga de graça 🎮"],
    ["passo fácil: entra no site 🔗", "pega um jogo rápido ⏱️", "vicia 🫠"],
    ["tá entediado? 😴", "kavixbrasil.com.br 🔗", "problema resolvido 😎"],
    ["salva esse vídeo 📌", "entra no site depois 🔗", "me agradece 😎"],
    ["chama teu amigo 👥", "cada um no seu celular 📱", "quem fizer mais ganha 🏆"],
]

TIERS = [("tier list dos jogos mais difíceis",
          {"S": ["Fio", "Equilíbrio"], "A": ["Ricochete", "Gravidade"], "B": ["Pulso", "Corte"],
           "C": ["Bolhas", "Pega Tudo"]}),
         ("tier list dos mais viciantes",
          {"S": ["Empilha", "Cobrinha"], "A": ["Espinhos", "Reflexo"], "B": ["Boliche", "Hélice"],
           "C": ["Ponte", "Balanço"]}),
         ("tier list pra jogar no ônibus",
          {"S": ["Pega Tudo", "Troca Cor"], "A": ["Passagem", "Trampolim"],
           "B": ["Memória", "Sinal"], "C": ["Canhão", "Espelho"]}),
         ("tier list de reflexo",
          {"S": ["Pulso", "Sinal"], "A": ["Corte", "Escudo"], "B": ["Três Pistas", "Zigue-Zague"],
           "C": ["Órbita", "Encaixe"]}),
         ("tier list dos mais satisfatórios",
          {"S": ["Bolhas", "Empilha"], "A": ["Quebra Blocos", "Boliche"],
           "B": ["Encaixe", "Hélice"], "C": ["Fio", "Canhão"]})]


def ordem_rng(i):
    lst = nomes()[:]
    random.Random(5000 + i).shuffle(lst)
    return lst


def skins_ordenadas(seed):
    lst = [x for x in g.skins() if x["tipo"] in ("roupa", "chapeu", "aura", "olhos", "cor")]
    random.Random(seed).shuffle(lst)
    lst.sort(key=lambda x: -g.RAR_ORDEM.get(x["raridade"], 0))
    return lst


# ------------------------------------------------------------ roteiros

def spec_desafio(i, nome, k):
    meta = METAS[k % len(METAS)]
    fala = DESAFIO_FALAS[k % len(DESAFIO_FALAS)]
    sc = [(6.8, g.sc_game(cel(nome, 0.1 + (k % 4) * 0.15), name=nome, texts=[
              label(0.0, 6.8, f"DESAFIO #{k + 1}", 0.31, 52, 4, c1.ACCENTS[k % 5]),
              cap(0.2, 3.4, f"faz {meta} pontos no {nome}", 0.44, (1,)),
              cap(3.5, 6.8, fala, 0.44, last(fala)),
              url_label(3.5, 6.8)])),
          (3.4, g.sc_pc(pc(nome, 0.55), texts=[
              cap(0.1, 3.4, "valendo no celular e no PC", 0.24, (3, 5))])),
          cta(i, cel(nome, 0.8))]
    return build(i, sc, extra=[("pop", 0.05)])


def spec_faq(i, pergunta, resposta):
    o = ordem_rng(i)
    sc = [(6.0, sc_faq(cel(o[0], 0.3), pergunta, texts=[
              cap(1.2, 6.0, resposta, 0.55, last(resposta)),
              url_label(2.5, 6.0, 0.72)])),
          (2.2, g.sc_game(cel(o[1], 0.5), name=o[1])),
          (2.2, g.sc_game(cel(o[2], 0.5), name=o[2], texts=[
              cap(0.1, 2.2, "testa agora 👇", 0.4, (0,))])),
          cta(i, cel(o[3], 0.6))]
    return build(i, sc, extra=[("pop", 0.05)])


def spec_meme(i, a, b):
    o = ordem_rng(i)
    sc = [(3.6, g.sc_game(cel(o[0], 0.05), texts=[cap(0.1, 3.6, a, 0.38, ())])),
          (4.4, g.sc_game(cel(o[1], 0.7), name=o[1], texts=[
              cap(0.0, 4.4, b, 0.38, last(b)),
              label(1.0, 4.4, "😭😭😭", 0.58, 70, 4)])),
          (2.4, g.sc_game(cel(o[2], 0.5), texts=[
              cap(0.1, 2.4, "tu também? 👇", 0.4, (1,)), url_label(0.4, 2.4)])),
          cta(i, cel(o[3], 0.6))]
    return build(i, sc)


def spec_skin_dia(i, it, k):
    o = ordem_rng(i)
    tipo = it["tipo_nome"].lower()
    sc = [(2.2, g.sc_game(cel(o[0], 0.4), texts=[
              label(0.0, 2.2, "SKIN DO DIA", 0.3, 60, -4, c1.ACCENTS[k % 5]),
              cap(0.2, 2.2, f"{tipo} {it['raridade_nome'].lower()} ✨", 0.42, (1,))])),
          (4.6, sc_skin_one(cel(o[1], 0.3), it, texts=[
              cap(0.0, 4.6, "olha isso 👀", 0.2, (1,), 0.8)])),
          (3.4, g.sc_game(cel(o[2], 0.5), texts=[
              cap(0.1, 3.4, "como pegar: cria tua conta no site 🎁", 0.38, (5, 6)),
              url_label(0.6, 3.4)])),
          cta(i, cel(o[3], 0.6))]
    return build(i, sc, extra=[("pop", 2.3)])


def spec_tutorial(i, passos):
    o = ordem_rng(i)
    steps = [("pc", pc(o[0], 0.3), passos[0]),
             ("cel", cel(o[1], 0.2), passos[1]),
             ("cel", cel(o[2], 0.5), passos[2])]
    sc = [(1.8, g.sc_game(cel(o[3], 0.4), texts=[
              cap(0.0, 1.8, "como jogar em 3 passos 👇", 0.4, (3,))])),
          (8.4, sc_steps(steps, texts=[url_label(0.3, 8.4, 0.31)])),
          cta(i, cel(o[4], 0.6))]
    return build(i, sc, extra=[("pop", 1.8 + 2.8 * k) for k in range(3)])


def spec_duelo(i, a, b):
    o = ordem_rng(i)
    sc = [(7.0, sc_skin_duel(cel(o[0], 0.3), a, b, texts=[
              cap(0.0, 7.0, "qual é mais bonita? 👇", 0.2, (2,), 0.85),
              cap(3.0, 7.0, "comenta A ou B", 0.78, (1, 3), 0.8)])),
          (3.2, g.sc_game(cel(o[1], 0.5), name=o[1], texts=[
              cap(0.1, 3.2, "as duas tão no site 🎁", 0.4, (4,)), url_label(0.5, 3.2)])),
          cta(i, cel(o[2], 0.6))]
    return build(i, sc, extra=[("pop", 0.3), ("pop", 0.55)])


def spec_tier(i, titulo, tiers):
    o = ordem_rng(i)
    sc = [(2.0, g.sc_game(cel(tiers["S"][0], 0.5), texts=[
              label(0.0, 2.0, "TIER LIST", 0.28, 66, -4, g.LIME),
              cap(0.2, 2.0, titulo.replace("tier list ", ""), 0.42, last(titulo))])),
          (6.4, sc_tier(cel(o[0], 0.3), tiers, texts=[
              cap(0.0, 6.4, "concorda? 👇", 0.2, (0,), 0.85)])),
          (2.6, g.sc_game(cel(tiers["S"][1], 0.5), name=tiers["S"][1], texts=[
              cap(0.1, 2.6, "testa e me fala 👇", 0.4, (0,)), url_label(0.4, 2.6)])),
          cta(i, cel(o[1], 0.6))]
    return build(i, sc, extra=[("pop", 2.5 + 0.55 * k) for k in range(8)])


# ------------------------------------------------------------ catálogo

def catalogo():
    itens = []
    for k, nome in enumerate(nomes()):
        meta = METAS[k % len(METAS)]
        itens.append(("desafio", nome, functools.partial(spec_desafio, nome=nome, k=k),
                      f"DESAFIO: faz {meta} pontos no {nome} 😤 {DESAFIO_FALAS[k % 5]}"))
    for p, r in FAQ:
        itens.append(("pergunta", p, functools.partial(spec_faq, pergunta=p, resposta=r),
                      f"{p} {r}"))
    for a, b, slug in MEMES:
        itens.append(("meme", slug, functools.partial(spec_meme, a=a, b=b), f"{a} / {b} 😭"))
    sk = skins_ordenadas(7)
    for k, it in enumerate(sk[:15]):
        itens.append(("skin_do_dia", it["nome"], functools.partial(spec_skin_dia, it=it, k=k),
                      f"skin do dia: {it['nome']} ({it['raridade_nome']}) ✨"))
    for k, passos in enumerate(TUTORIAL):
        itens.append(("tutorial", f"passos_{k + 1}", functools.partial(spec_tutorial, passos=passos),
                      "como jogar em 3 passos 👇 " + " → ".join(passos)))
    rest = sk[15:]
    for k in range(10):
        a, b = rest[2 * k], rest[2 * k + 1]
        itens.append(("duelo_skins", f"{a['nome']} vs {b['nome']}",
                      functools.partial(spec_duelo, a=a, b=b),
                      f"{a['nome']} ou {b['nome']}? qual é mais bonita? 👇"))
    for titulo, tiers in TIERS:
        itens.append(("tier_list", titulo, functools.partial(spec_tier, titulo=titulo, tiers=tiers),
                      f"{titulo} 🔥 concorda?"))
    rng = random.Random(77)
    por_fmt = {}
    for it in itens:
        por_fmt.setdefault(it[0], []).append(it)
    pos = []
    for f, lst in por_fmt.items():
        rng.shuffle(lst)
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


CHAMADAS2 = ["Joga agora 👉 kavixbrasil.com.br (link na bio)",
             "Sem baixar nada: abre kavixbrasil.com.br e joga 🎮",
             "Cria tua conta grátis e ganha itens exclusivos 🎁 link na bio",
             "30 jogos no celular e no PC 🔗 kavixbrasil.com.br",
             "Salva esse vídeo e joga depois 📌 kavixbrasil.com.br"]


def legenda(v):
    rng = random.Random(9000 + v["id"])
    tags = (["#kavix", "#kavixarcade"] + rng.sample(c1.TAGS_VIRAIS, 3) +
            rng.sample(c1.TAGS_ROBLOX, 2 + (v["id"] % 2)) +
            rng.sample([t for t in c1.TAGS_JOGOS if t not in ("#kavix", "#kavixarcade")], 2))
    texto = f"{v['gancho']}\n{CHAMADAS2[v['id'] % len(CHAMADAS2)]}"
    return texto, " ".join(tags), (v["gancho"][:80] + " #shorts").strip()


@functools.lru_cache(maxsize=1)
def _catalogo():
    return {v["id"]: v for v in catalogo()}


def render_one(vid):
    v = _catalogo()[vid]
    path = os.path.join(OUT, v["arquivo"])
    if os.path.exists(path) and os.path.getsize(path) > 200_000:
        return path + " (já existia)"
    g.render_spec(v["fn"](v["id"]), W, H, PLATFORM, path)
    return path


RAW = ("https://raw.githubusercontent.com/joaopx20-source/automaton/"
       "claude/kavix-promotional-videos-e6f1vd/promo/kavix/campanha2/")


def plano(vs, inicio=None):
    """Calendário por 'dia da campanha' (1 a 25). Sem `inicio`, fica sem datas,
    para usar depois; com `inicio`, preenche data e data_hora."""
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
            "fuso": c1.FUSO,
            "arquivo": v["arquivo"], "url_download": RAW + v["arquivo"],
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
              "formato",
              "legenda_instagram_facebook", "legenda_tiktok", "titulo_youtube",
              "descricao_youtube"]
    with open(os.path.join(OUT, "plano_postagem.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(posts)
    print("ok:", len(posts), "posts em", posts[-1]["dia_campanha"], "dias",
          f"(de {posts[0]['data']} a {posts[-1]['data']})" if inicio else "(sem datas)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lista"
    vs = catalogo()
    if cmd == "lista":
        for v in vs:
            print(f"{v['id']:3d}  {v['formato']:12s} {v['assunto']}")
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
