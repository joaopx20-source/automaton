#!/usr/bin/env python3
"""Campanha de 100 reels do KAVIX ARCADE + calendário de postagem.

Monta 100 roteiros diferentes (10 formatos) com os 30 jogos gravados e as
skins do inventário, renderiza em 9:16 (área segura do TikTok, serve para
Instagram, TikTok, YouTube Shorts e Facebook) e gera o calendário com
legendas e hashtags.

Uso:
    python3 promo/kavix/campanha.py lista              # lista os 100 roteiros
    python3 promo/kavix/campanha.py render [n ...]     # renderiza (todos ou alguns)
    python3 promo/kavix/campanha.py plano 2026-10-12   # calendário a partir da data

Saída: campanha/videos/NNN_<formato>_<assunto>.mp4 e campanha/plano_postagem.csv
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

import gerar_videos as g
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "campanha")
W, H, PLATFORM = 1080, 1920, "tiktok"  # área segura mais apertada: serve em todas
POR_DIA = 4
HORARIOS = ["09:00", "12:30", "17:00", "20:30"]

ACCENTS = [g.LIME, (255, 214, 64), (56, 210, 255), (255, 120, 200), (170, 140, 255)]


def jogo(nome):
    return g.game(0, nome)


def nomes():
    return [x["nome"] for x in g.library()]


def cel(nome, frac=0.35):
    return g.at(jogo(nome)["celular"], frac)


def pc(nome, frac=0.5):
    return g.at(jogo(nome)["pc"], frac)


# ------------------------------------------------------------ cenas novas

def sc_versus(a, b, texts=()):
    """Tela dividida: dois jogos (em cima/embaixo) com etiquetas A e B."""
    st = {}

    def f(img, t, dur, c):
        h2 = c.H // 2
        if not st:
            st["a"] = g.Clip(cel(a, 0.4)[0], c.W, h2, cel(a, 0.4)[1], g.HEADER_PX)
            st["b"] = g.Clip(cel(b, 0.4)[0], c.W, h2, cel(b, 0.4)[1], g.HEADER_PX)
        img.alpha_composite(st["a"].get(t).convert("RGBA"), (0, 0))
        img.alpha_composite(st["b"].get(t).convert("RGBA"), (0, h2))
        d = ImageDraw.Draw(img)
        d.rectangle((0, h2 - 4 * c.u, c.W, h2 + 4 * c.u), fill=(255, 255, 255, 255))
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        g.draw_sticker(img, f"A · {a}", c.text_cx, h2 * 0.36 + c.top_off * 0.5,
                       58 * c.u, t - 0.05, -3, g.WHITE, g.BLACK, path=g.F_DISPLAY,
                       max_w=c.max_w)
        g.draw_sticker(img, f"B · {b}", c.text_cx, h2 + h2 * 0.2, 58 * c.u,
                       t - 0.2, 3, g.WHITE, g.BLACK, path=g.F_DISPLAY, max_w=c.max_w)
        vs = g.sticker("VS", int(64 * c.u), "brand", g.INK, g.F_DISPLAY)
        k = g.spring((t - 0.3) / 0.4)
        if t > 0.3:
            g.put(img, g.scaled(vs, max(0.05, k)), c.cx, h2)
        g.draw_texts(img, c, t, texts)
    return f


def sc_quiz(nome, texts=(), reveal=2.2):
    """'Adivinha o jogo': desfocado até `reveal`, depois mostra o nome."""
    st = {}

    def f(img, t, dur, c):
        if "clip" not in st:
            st["clip"] = g.Clip(cel(nome, 0.5)[0], c.panel_w, c.panel_h,
                                cel(nome, 0.5)[1], g.HEADER_PX)
        fr = st["clip"].get(t)
        if t < reveal:
            blur = 26 * (1 - 0.6 * t / reveal)
            im = fr.resize((c.W // 6, c.H // 6)).filter(ImageFilter.GaussianBlur(blur / 6))
            img.alpha_composite(im.resize((c.W, c.H), Image.BILINEAR).convert("RGBA"))
            g.draw_sticker(img, "?", c.cx, c.Y(0.45), 160 * c.u, t, -6, g.WHITE,
                           g.BLACK, path=g.F_DISPLAY)
            # contagem regressiva
            n = max(1, math.ceil(reveal - t))
            g.draw_sticker(img, str(n), c.cx, c.Y(0.62), 70 * c.u, (t % 1.0), 4,
                           g.ACCENT[0], g.BLACK, path=g.F_DISPLAY)
        else:
            g.game_panel(img, c, st["clip"], t)
            g.draw_sticker(img, nome, c.text_cx, c.Y(0.24) + c.top_off * 0.6,
                           70 * c.u, t - reveal, -3, g.ACCENT[0], g.BLACK,
                           path=g.F_DISPLAY, max_w=c.max_w)
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        g.draw_texts(img, c, t, texts)
    return f


def sc_items_list(src_bg, items, texts=()):
    """Grade 2x2 de skins reais (variação do sc_items com itens escolhidos)."""
    st = {}

    def f(img, t, dur, c):
        if "bg" not in st:
            st["bg"] = g.Clip(src_bg[0], 540, 960, src_bg[1], g.HEADER_PX)
        img.alpha_composite(g.blurred_bg(st["bg"].get(t), c.W, c.H, 0.55))
        cw = int(c.W * 0.66 / 2)
        ch = int(cw * 1.25)
        gx, gy = c.text_cx, c.Y(0.56)
        for i, it in enumerate(items[:4]):
            lt = t - 0.4 - i * 0.2
            if lt < 0:
                continue
            r, q = divmod(i, 2)
            x = gx + (q - 0.5) * (cw + 24 * c.u)
            y = gy + (r - 0.5) * (ch + 24 * c.u)
            k = g.spring(lt / 0.5)
            card = g.rounded((cw, ch), int(34 * c.u), (255, 255, 255, 38),
                             outline=(255, 255, 255, 90), width=max(2, int(3 * c.u)))
            m = g.skin_image(it["arquivo"], int(cw * 0.66))
            card.alpha_composite(m, ((cw - m.width) // 2, int(ch * 0.36 - m.height / 2 +
                                                              math.sin(t * 4 + i) * 8 * c.u)))
            nm = g.text_layer(it["nome"], int(32 * c.u), path=g.F_BOLD, shadow_a=150)
            card.alpha_composite(nm, ((cw - nm.width) // 2, int(ch * 0.66)))
            chip = g.sticker(it["raridade_nome"].upper(), int(24 * c.u),
                             g.hexrgb(it["cor"]), g.INK)
            card.alpha_composite(chip, ((cw - chip.width) // 2, int(ch * 0.86 - chip.height / 2)))
            card = card.rotate((-1) ** i * 3 * (1 - k), expand=True, resample=Image.BICUBIC)
            g.put(img, g.set_alpha(g.scaled(card, g.lerp(0.4, 1, k)), g.clamp01(lt / 0.1)), x, y)
        img.alpha_composite(g.top_shade(c.W, c.H))
        g.handle(img, c)
        g.draw_texts(img, c, t, texts)
    return f


# --------------------------------------------------------------- textos

def cap(t0, t1, text, y=0.38, hl=(), size=1.0):
    return (t0, t1, "cap", text, {"y": y, "hl": hl, "size": size})


def label(t0, t1, text, y=0.3, size=58, rot=-3, bg=g.WHITE):
    return (t0, t1, "label", text, {"y": y, "size": size, "rot": rot, "bg": bg})


def last(text, n=1):
    """Índices das últimas n palavras (sem contar emoji) para destacar."""
    w = text.split()
    idx = [i for i, x in enumerate(w) if not g.is_emoji(x[0])]
    return tuple(idx[-n:])


CTAS = [("Cria sua conta agora", "Criar minha conta"),
        ("Joga agora de graça", "Jogar agora"),
        ("Bora jogar?", "Criar minha conta"),
        ("Teu recorde te espera", "Jogar agora"),
        ("Entra e joga agora", "Criar minha conta")]


def cta(i, src):
    title, button = CTAS[i % len(CTAS)]
    return (5.0, g.sc_cta(src, title, button))


def build(i, scenes, extra=()):
    rng = random.Random(i)
    s = g.build(scenes, bpm=rng.choice([132, 136, 140, 144, 148, 150]),
                prog_=rng.choice(["AFCG", "FCGA", "ADFE", "AFDE", "CGAF"]), seed=100 + i,
                extra=extra)
    s["accent"] = ACCENTS[i % len(ACCENTS)]
    assert s["dur"] >= 15, (i, s["dur"])
    return s


# ------------------------------------------------------------ conteúdos

DESTAQUE_HOOKS = [
    "duvido você passar de 30 pontos 😤", "esse jogo é viciante demais 😭",
    "aposto que tu não dura 1 minuto 💀", "testa teus reflexos aqui ⚡",
    "só os brabos passam do nível 3 🔥", "parece fácil né? 🙂", "tenta não perder em 10 segundos 😳",
    "meu irmão ficou 2 horas nisso 💀", "esse é o mais difícil do site 😤",
    "joguei 5 minutos e já era madrugada 🌙", "se tu curte Roblox vai viciar nisso 👀",
    "o jogo mais satisfatório que tu vai ver hoje 🤤", "ninguém no meu grupo passou do 20 😭",
    "esse aqui separa os fortes dos fracos 💪", "quem fizer mais de 50 manda print 📸",
    "o tipo de jogo que tu promete que é o último 😅", "rápido demais pra mim 😵",
    "olha a paz desse jogo 😌", "meu recorde é 42, bate aí 👀", "esse jogo testa tua paciência 🫠",
    "um toque e acabou 💀", "jogo perfeito pra fila do banco ⏳", "relaxante até tu errar 😤",
    "joga 1 vez e me fala 👇", "a última fase é surreal 🤯", "pra quem tem dedo rápido ⚡",
    "o que tu faria pra passar disso? 😂", "esse viciou a sala inteira 🏫",
    "tu é bom em jogo de reflexo? 🤔", "se tu piscar tu perde 👁️",
]
DESTAQUE_MIDS = ["joga direto do celular 📱", "sem baixar nada 🙌", "e é de graça 🎮",
                 "dá pra jogar no intervalo ⏱️", "roda até em celular fraco 📱",
                 "tem mais 29 jogos assim 🎮"]

TOP5 = [
    ("jogos mais viciantes", ["Empilha", "Cobrinha", "Espinhos", "Quebra Blocos", "Reflexo"]),
    ("jogos mais difíceis", ["Fio", "Equilíbrio", "Ricochete", "Gravidade", "Zigue-Zague"]),
    ("pra testar teu reflexo", ["Pulso", "Sinal", "Corte", "Escudo", "Três Pistas"]),
    ("jogos mais relaxantes", ["Bolhas", "Encaixe", "Ponte", "Balanço", "Órbita"]),
    ("pra jogar na fila do banco", ["Pega Tudo", "Troca Cor", "Hélice", "Boliche", "Passagem"]),
    ("que ninguém passa do nível 5", ["Canhão", "Pula Corda", "Trampolim", "Espelho", "Memória"]),
]
REACOES = ["esse aqui é tenso 😤", "não consigo parar 😭", "um toque errado e já era 💀",
           "clássico demais 🔥", "o mais insano 🤯", "viciante nível máximo 🫠",
           "olha que satisfatório 🤤", "parece fácil mas não é 🙂", "o meu favorito 👑",
           "esse aqui é paz 😌"]

TOP3 = [
    ("3 jogos pra quando tá entediado", ["Pega Tudo", "Bolhas", "Cobrinha"]),
    ("3 jogos pra jogar no intervalo", ["Reflexo", "Passagem", "Empilha"]),
    ("3 jogos que viciam em 10 segundos", ["Espinhos", "Gravidade", "Trampolim"]),
    ("3 jogos pra desafiar teu amigo", ["Quebra Blocos", "Pulso", "Equilíbrio"]),
    ("3 jogos pra quem curte Roblox", ["Pula Corda", "Canhão", "Zigue-Zague"]),
    ("3 jogos pra testar teu cérebro", ["Memória", "Encaixe", "Espelho"]),
    ("3 jogos pra jogar deitado", ["Órbita", "Balanço", "Ponte"]),
    ("3 jogos de reflexo insano", ["Corte", "Sinal", "Escudo"]),
    ("3 jogos que parecem fáceis", ["Fio", "Hélice", "Boliche"]),
    ("3 jogos pra jogar antes de dormir", ["Troca Cor", "Três Pistas", "Ricochete"]),
]

VERSUS = [("Cobrinha", "Boliche"), ("Espinhos", "Gravidade"), ("Quebra Blocos", "Canhão"),
          ("Empilha", "Encaixe"), ("Reflexo", "Pulso"), ("Bolhas", "Pega Tudo"),
          ("Órbita", "Hélice"), ("Trampolim", "Pula Corda"), ("Memória", "Sinal"),
          ("Três Pistas", "Zigue-Zague"), ("Troca Cor", "Espelho"), ("Ponte", "Balanço"),
          ("Ricochete", "Fio"), ("Corte", "Escudo"), ("Passagem", "Equilíbrio")]
VERSUS_HOOKS = ["qual tu escolhe? 👇", "só pode jogar um pra sempre 😳", "qual é mais difícil? 🤔",
                "comenta A ou B 👇", "qual vicia mais? 🫠"]

POV = [
    ("POV: abri o site pra jogar 1 partida...", "3 horas depois 💀"),
    ("POV: tu falou que era o último jogo", "spoiler: não era 😅"),
    ("POV: a aula tá chata", "e tu descobre 30 jogos 🎮"),
    ("POV: teu amigo bateu teu recorde", "e tu não dorme até passar ele 😤"),
    ("POV: acabou a bateria do controle", "e tu acha jogos no navegador 🙌"),
    ("POV: tu tá esperando o ônibus", "e o ônibus passou 💀"),
    ("POV: tu curte Roblox", "e acha isso aqui 👀"),
    ("POV: tu prometeu dormir cedo", "são 3 da manhã 🌙"),
    ("POV: tu achou que era fácil", "não era 😭"),
    ("POV: o wifi caiu no meio do jogo", "e tu descobre que aqui roda liso 😎"),
]

QUIZ = [["Espinhos", "Bolhas", "Órbita"], ["Cobrinha", "Hélice", "Trampolim"],
        ["Quebra Blocos", "Memória", "Pulso"], ["Empilha", "Canhão", "Sinal"],
        ["Reflexo", "Balanço", "Fio"], ["Passagem", "Encaixe", "Corte"],
        ["Gravidade", "Ponte", "Escudo"], ["Boliche", "Espelho", "Zigue-Zague"]]

SKINS = [
    ("as skins lendárias 👑", lambda s: [x for x in s if x["raridade"] == "lendario"]),
    ("roupas completas pra tua bolinha 🥷", lambda s: [x for x in s if x["tipo"] == "roupa"]),
    ("chapéus que tu precisa ter 🎩", lambda s: [x for x in s if x["tipo"] == "chapeu"]),
    ("auras que brilham ✨", lambda s: [x for x in s if x["tipo"] == "aura"]),
    ("olhos com personalidade 👀", lambda s: [x for x in s if x["tipo"] == "olhos"]),
    ("skins épicas 💜", lambda s: [x for x in s if x["raridade"] == "epico"]),
    ("rastros pra deixar tua marca 💨", lambda s: [x for x in s if x["tipo"] == "rastro"]),
    ("da comum à lendária 🔥", lambda s: s),
]

ITENS = ["cadastro novo = itens exclusivos 🎁", "cria conta e já ganha itens 🎁",
         "skins exclusivas pra quem chega agora 👀", "quem se cadastra hoje ganha 🎁",
         "tua bolinha merece um visual novo ✨"]

PLATAF = [("começa no celular 📱", "termina no PC 💻"),
          ("joga no celular 📱", "ou no PC 💻"),
          ("na escola 📱", "em casa 💻"),
          ("no ônibus 📱", "no quarto 💻"),
          ("sem baixar nada 🙌", "direto no navegador 💻")]

TODOS = [("30 jogos em 30 segundos 😳", 0.45), ("qual desses tu jogaria primeiro? 👇", 0.25),
         ("não pisca 👀", 0.65)]


def ordem_rng(i):
    lst = nomes()[:]
    random.Random(i).shuffle(lst)
    return lst


# ------------------------------------------------------------ roteiros

def spec_destaque(i, nome, k):
    hook = DESTAQUE_HOOKS[k % len(DESTAQUE_HOOKS)]
    mid = DESTAQUE_MIDS[k % len(DESTAQUE_MIDS)]
    sc = [
        (6.5, g.sc_game(cel(nome, 0.05 + (k % 5) * 0.12), name=nome, texts=[
            cap(0.1, 3.0, hook, 0.38, last(hook)),
            cap(3.2, 6.5, mid, 0.38, last(mid))])),
        (3.6, g.sc_pc(pc(nome, 0.6), texts=[
            label(0.1, 3.6, "💻 e no PC também", 0.2, 56),
            cap(0.3, 3.6, "direto no navegador", 0.7, (2,))])),
        cta(i, cel(nome, 0.7)),
    ]
    return build(i, sc, extra=[("pop", 0.1)])


def spec_top(i, titulo, lista, n):
    sc = [(2.4, g.sc_game(cel(lista[0], 0.6), texts=[
        label(0.0, 2.4, f"TOP {n}", 0.27, 70, -4, g.LIME),
        cap(0.2, 2.4, titulo + " 🔥", 0.4, (len(titulo.split()) - 1,))]))]
    for k, nome in enumerate(lista):
        rank = n - k
        fala = REACOES[(i + k) % len(REACOES)]
        sc.append((2.6 if n == 5 else 3.2, g.sc_game(cel(nome, 0.3 + 0.1 * k), texts=[
            label(0.0, 3.2, f"#{rank}", 0.2, 66, -5, g.LIME if rank > 1 else (255, 206, 64)),
            label(0.1, 3.2, nome, 0.27, 62, 3),
            cap(0.6, 3.2, fala, 0.62, last(fala))])))
    sc.append((2.2, g.sc_collage(cel(lista[-1], 0.5), pc(lista[0], 0.5), texts=[
        cap(0.1, 2.2, "concorda? comenta o teu 👇", 0.72, (2, 3))])))
    sc.append(cta(i, cel(lista[-1], 0.7)))
    return build(i, sc, extra=[("pop", 2.4 + 2.6 * k) for k in range(n)])


def spec_versus(i, a, b, k):
    hook = VERSUS_HOOKS[k % len(VERSUS_HOOKS)]
    sc = [(9.0, sc_versus(a, b, texts=[cap(0.4, 9.0, hook, 0.36, last(hook))])),
          (3.0, g.sc_collage(cel(a, 0.7), pc(b, 0.5), texts=[
              cap(0.1, 3.0, "os dois no mesmo site 🎮", 0.72, (4,))])),
          cta(i, cel(b, 0.6))]
    return build(i, sc, extra=[("pop", 0.3)])


def spec_pov(i, hook, punch, k):
    lst = ordem_rng(i)[:5]
    sc = [(3.0, g.sc_game(cel(lst[0], 0.2), texts=[cap(0.1, 3.0, hook, 0.36, ())]))]
    for j, nome in enumerate(lst[1:4]):
        sc.append((1.4, g.sc_game(cel(nome, 0.5), name=nome)))
    sc.append((3.2, g.sc_game(cel(lst[4], 0.6), texts=[
        cap(0.1, 3.2, punch, 0.4, last(punch, 2))])))
    sc.append(cta(i, cel(lst[0], 0.8)))
    return build(i, sc, extra=[("pop", 3.0 + 1.4 * j) for j in range(3)])


def spec_quiz(i, lista):
    sc = [(2.0, g.sc_game(cel(lista[0], 0.2), texts=[
        cap(0.1, 2.0, "adivinha o jogo só pela tela 🤔", 0.4, (1, 2))]))]
    for nome in lista:
        sc.append((3.4, sc_quiz(nome, texts=[cap(2.4, 3.4, "acertou? 👀", 0.7, (0,))])))
    sc.append(cta(i, cel(lista[-1], 0.6)))
    return build(i, sc, extra=[("pop", 2.0 + 3.4 * j + 2.2) for j in range(3)])


def spec_skins(i, titulo, filtro):
    todas = g.skins()
    lst = sorted(filtro(todas), key=lambda x: g.RAR_ORDEM.get(x["raridade"], 0))
    random.Random(i).shuffle(lst)
    lst = sorted(lst[:6], key=lambda x: g.RAR_ORDEM.get(x["raridade"], 0))
    order = ordem_rng(i)
    sc = [(2.4, g.sc_game(cel(order[0], 0.5), texts=[
              cap(0.1, 2.4, "tua bolinha pode ficar assim 👀", 0.38, (4,))])),
          (max(5.4, 0.9 * len(lst)), g.sc_skin_reveal(cel(order[1], 0.3), lst, texts=[
              cap(0.0, 9.0, titulo, 0.23, last(titulo), 0.8)])),
          (3.4, sc_items_list(cel(order[2], 0.3), lst[::-1][:4], texts=[
              cap(0.0, 3.4, "cadastro novo = itens exclusivos 🎁", 0.25, (3, 4), 0.85)])),
          cta(i, cel(order[3], 0.6))]
    return build(i, sc, extra=[("pop", 2.4 + 0.9 * k) for k in range(len(lst))])


def spec_itens(i, hook):
    order = ordem_rng(i)
    pool = [x for x in g.skins() if x["tipo"] in ("roupa", "chapeu", "aura", "olhos")]
    random.Random(i).shuffle(pool)
    sc = [(4.6, sc_items_list(cel(order[0], 0.3), pool[:4], texts=[
              cap(0.0, 4.6, hook, 0.25, last(hook, 2), 0.85)])),
          (2.6, g.sc_game(cel(order[1], 0.4), name=order[1])),
          (3.0, g.sc_game(cel(order[2], 0.5), name=order[2], texts=[
              cap(0.1, 3.0, f"e {g.total_jogos()} jogos pra jogar 🎮", 0.4, (1, 2))])),
          cta(i, cel(order[3], 0.6))]
    return build(i, sc, extra=[("pop", 0.4 + 0.2 * k) for k in range(4)])


def spec_plataf(i, a, b):
    order = ordem_rng(i)
    sc = [(3.6, g.sc_game(cel(order[0], 0.3), name=order[0], texts=[
              cap(0.1, 3.6, a, 0.38, last(a))])),
          (3.6, g.sc_pc(pc(order[1], 0.4), texts=[cap(0.1, 3.6, b, 0.24, last(b))])),
          (3.0, g.sc_collage(cel(order[2], 0.2), pc(order[3], 0.3), texts=[
              cap(0.2, 3.0, "mesma conta nos dois 🔄" if i % 2 else "sem baixar nada 🙌",
                  0.72, (1,))])),
          cta(i, cel(order[4], 0.6))]
    return build(i, sc)


def spec_todos(i, hook, frac):
    order = ordem_rng(i)
    sc = [(2.0, g.sc_game(cel(order[0], frac), texts=[cap(0.0, 2.0, hook, 0.4, last(hook))]))]
    for j, nome in enumerate(order[1:], 2):
        sc.append((0.7, g.sc_game(cel(nome, frac), name=nome, texts=[
            label(0, 0.7, f"#{j}", 0.72, 44, 4, g.LIME)])))
    sc.append(cta(i, cel(order[0], 0.8)))
    return build(i, sc)


# ------------------------------------------------------------ catálogo

def catalogo():
    """Lista dos 100 vídeos: (id, formato, assunto, função do roteiro, ganchos p/ legenda)."""
    itens = []
    n = nomes()
    for k, nome in enumerate(n):
        itens.append(("destaque", nome, functools.partial(spec_destaque, nome=nome, k=k),
                      DESTAQUE_HOOKS[k % len(DESTAQUE_HOOKS)]))
    for k, (a, b) in enumerate(VERSUS):
        itens.append(("versus", f"{a} vs {b}", functools.partial(spec_versus, a=a, b=b, k=k),
                      f"{a} ou {b}? {VERSUS_HOOKS[k % len(VERSUS_HOOKS)]}"))
    for titulo, lst in TOP3:
        itens.append(("top3", titulo, functools.partial(spec_top, titulo=titulo, lista=lst, n=3),
                      titulo))
    for k, (hook, punch) in enumerate(POV):
        itens.append(("pov", hook, functools.partial(spec_pov, hook=hook, punch=punch, k=k),
                      f"{hook} {punch}"))
    for lst in QUIZ:
        itens.append(("quiz", " / ".join(lst), functools.partial(spec_quiz, lista=lst),
                      "adivinha o jogo só pela tela 🤔"))
    for titulo, filtro in SKINS:
        itens.append(("skins", titulo, functools.partial(spec_skins, titulo=titulo, filtro=filtro),
                      titulo))
    for titulo, lst in TOP5:
        itens.append(("top5", titulo, functools.partial(spec_top, titulo=titulo, lista=lst, n=5),
                      f"TOP 5 {titulo} 🔥"))
    for hook in ITENS:
        itens.append(("itens", hook, functools.partial(spec_itens, hook=hook), hook))
    for a, b in PLATAF:
        itens.append(("plataforma", f"{a} {b}", functools.partial(spec_plataf, a=a, b=b),
                      f"{a} {b}"))
    for hook, frac in TODOS:
        itens.append(("todos", hook, functools.partial(spec_todos, hook=hook, frac=frac), hook))
    # espalha cada formato por toda a campanha (sem dois iguais seguidos)
    rng = random.Random(42)
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


# ------------------------------------------------------------ legendas

TAGS_VIRAIS = ["#fyp", "#viral", "#foryou", "#paravoce", "#explore", "#trend", "#viralvideo"]
TAGS_ROBLOX = ["#roblox", "#robloxbrasil", "#robloxedit", "#robloxfyp", "#robloxgames"]
TAGS_JOGOS = ["#kavix", "#kavixarcade", "#jogosonline", "#gamerbrasil", "#minigames",
              "#jogosgratis", "#mobilegames", "#jogosdecelular"]
CHAMADAS = ["Joga grátis no celular ou no PC 👉 kavixbrasil.com.br (link na bio)",
            "Cria tua conta e ganha itens exclusivos 🎁 link na bio",
            "Mais de 30 jogos te esperando 🎮 kavixbrasil.com.br",
            "Comenta teu recorde 👇 e joga em kavixbrasil.com.br",
            "Marca aquele amigo que acha que é bom 😤 link na bio"]


def legenda(v):
    rng = random.Random(v["id"])
    tags = (["#kavix", "#kavixarcade"] + rng.sample(TAGS_VIRAIS, 3) +
            rng.sample(TAGS_ROBLOX, 2 + (v["id"] % 2)) +
            rng.sample([t for t in TAGS_JOGOS if t not in ("#kavix", "#kavixarcade")], 2))
    texto = f"{v['gancho']}\n{CHAMADAS[v['id'] % len(CHAMADAS)]}"
    titulo_yt = (v["gancho"][:80] + " #shorts").strip()
    return texto, " ".join(tags), titulo_yt


# ------------------------------------------------------------ comandos

@functools.lru_cache(maxsize=1)
def _catalogo():
    return {v["id"]: v for v in catalogo()}


def render_one(vid):
    v = _catalogo()[vid]
    path = os.path.join(OUT, v["arquivo"])
    if os.path.exists(path) and os.path.getsize(path) > 200_000:
        return path + " (já existia)"
    s = v["fn"](v["id"])
    g.render_spec(s, W, H, PLATFORM, path)
    return path


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lista"
    vs = catalogo()
    if cmd == "lista":
        for v in vs:
            print(f"{v['id']:3d}  {v['formato']:10s} {v['assunto']}")
        print(len(vs), "vídeos")
    elif cmd == "render":
        sel = set(int(x) for x in sys.argv[2:]) or {v["id"] for v in vs}
        todo = [v["id"] for v in vs if v["id"] in sel]
        with Pool(int(os.environ.get("KAVIX_PROCS", "3"))) as pool:
            for p in pool.imap_unordered(render_one, todo):
                print("ok:", p, flush=True)
    elif cmd == "plano":
        inicio = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else \
            dt.date.today() + dt.timedelta(days=1)
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "plano_postagem.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["n", "data", "hora", "arquivo", "formato", "redes", "legenda",
                        "hashtags", "titulo_youtube"])
            for k, v in enumerate(vs):
                dia = inicio + dt.timedelta(days=k // POR_DIA)
                texto, tags, yt = legenda(v)
                w.writerow([v["id"], dia.isoformat(), HORARIOS[k % POR_DIA], v["arquivo"],
                            v["formato"], "Instagram; TikTok; YouTube Shorts; Facebook",
                            texto, tags, yt])
        print("ok:", os.path.join(OUT, "plano_postagem.csv"))


if __name__ == "__main__":
    main()
