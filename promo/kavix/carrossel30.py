#!/usr/bin/env python3
"""Série de 30 carrosséis (5 slides, 1080x1350) do KAVIX ARCADE, prontos para postar.

Varia os estilos aprovados (carrossel.py): top 5 com temas, desafio do recorde,
skins, versus, 30 jogos, passe de batalha, ranking e "conhece o KAVIX".

Uso:  python3 promo/kavix/carrossel30.py
Saída: carrossel/serie30/NN_<tema>/slide_01..05.jpg + legenda.txt,
       carrossel/serie30/legendas.csv e carrossel/kavix_carrosseis_30.zip
"""
import csv
import os
import random
import shutil
import zipfile

import carrossel as C
import gerar_videos as g

OUT = os.path.join(C.OUT, "serie30")
ZIP = os.path.join(C.OUT, "kavix_carrosseis_30.zip")
T = C.TOTAL
W, H = C.W, C.H
LIME, VIOLET, SKY, WHITE, INK = C.LIME, C.VIOLET, C.SKY, C.WHITE, C.INK
GOLD = (255, 206, 64)

TAGS_BASE = ["#kavix", "#kavixarcade"]
TAGS_VIRAIS = ["#fyp", "#viral", "#explore", "#paravoce", "#foryou", "#trend", "#viralpost"]
TAGS_ROBLOX = ["#roblox", "#robloxbrasil", "#robloxedit", "#robloxfyp", "#robloxgames"]
TAGS_JOGO = ["#jogosonline", "#gamerbrasil", "#minigames", "#jogosgratis", "#mobilegames",
             "#ranked", "#passedebatalha", "#skins", "#desafio", "#jogosdecelular"]


def tags(i):
    r = random.Random(300 + i)
    return " ".join(TAGS_BASE + r.sample(TAGS_VIRAIS, 3) + r.sample(TAGS_ROBLOX, 3) +
                    r.sample(TAGS_JOGO, 4))


FINAL = ["👉 kavixbrasil.com.br (link na bio)",
         "joga grátis no celular ou no PC 👉 kavixbrasil.com.br (link na bio)",
         "sem baixar nada 👉 kavixbrasil.com.br (link na bio) · cadastro novo ganha itens 🎁",
         "salva esse post 📌 e joga depois 👉 kavixbrasil.com.br"]

CTAS = ["bora jogar agora?", "qual tu vai jogar primeiro?", "aceita o desafio?",
        "cria tua conta e vem", "teu recorde começa hoje", "vem subir de patente"]


def skin(nome):
    return C.skin(nome)


# ------------------------------------------------------------ construtores

def b_top5(i, tema, lista, falas):
    s = []
    im = C.fundo(i * 7, foto=C.shot(lista[-1]))
    C.sticker(im, "TOP 5", W / 2, 330, 90, -5, LIME)
    C.titulo(im, f"{tema} do KAVIX 🔥", 560, 86, hl=(len(tema.split()) - 1,))
    C.texto(im, "o #1 vai te surpreender 👀", W / 2, 760, 40, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(lista[:3]):
        C.put(im, C.card_jogo(nome, 220, (-8, 0, 8)[k], 6, 26), W / 2 + (k - 1) * 270, 1040)
    s.append(C.moldura(im, 1, T))
    s.append(C.moldura(C.slide_rank_duplo(i * 7 + 1, [(5, lista[0], falas[0]),
                                                      (4, lista[1], falas[1])]), 2, T))
    s.append(C.moldura(C.slide_rank_duplo(i * 7 + 2, [(3, lista[2], falas[2]),
                                                      (2, lista[3], falas[3])]), 3, T))
    nome = lista[4]
    im = C.fundo(i * 7 + 3, foto=C.shot(nome))
    C.put(im, C.card_jogo(nome, 470, -4), 330, 760)
    C.sticker(im, "#1", 820, 380, 130, 6, GOLD)
    C.sticker(im, nome, 820, 570, 54, -3, WHITE)
    ws = falas[4].split()
    m = (len(ws) + 1) // 2
    for j, linha in enumerate((" ".join(ws[:m]), " ".join(ws[m:]))):
        C.texto(im, linha, 820, 680 + j * 56, 40, WHITE, g.F_BLACK, True)
    C.sticker(im, "vale ponto no ranking 🏆", 820, 900, 30, 2, (40, 38, 60), WHITE, g.F_BOLD)
    s.append(C.moldura(im, 4, T))
    s.append(C.slide_cta(i * 7 + 4, "concorda com o top? comenta o teu"))
    leg = (f"TOP 5 {tema} do KAVIX 🔥 o #1 é covardia 👑\n"
           f"#5 {lista[0]} · #4 {lista[1]} · #3 {lista[2]} · #2 {lista[3]} · #1 {lista[4]}\n"
           "concorda? comenta o teu 👇")
    return s, leg


def b_desafio(i, jogo, alvo, frase):
    s = []
    dia = C.PATENTES[0]
    im = C.fundo(i * 7, SKY, VIOLET, foto=C.shot(jogo))
    C.titulo(im, "se tu é bom mesmo…", 230, 70, hl=(2, 3))
    C.titulo(im, f"faz {alvo} no {jogo} 😤", 390, 84, hl=(1,))
    C.put(im, C.card_jogo(jogo, 380, -4), W / 2, 860)
    C.sticker(im, frase, W / 2, 1170, 38, 3, LIME, INK)
    s.append(C.moldura(im, 1, T))
    im = C.fundo(i * 7 + 1)
    C.titulo(im, "teu recorde em cada jogo soma no ranking 🏆", 250, 70, hl=(2, 3))
    outros = [n for n in ("Espinhos", "Empilha", "Cobrinha", "Reflexo") if n != jogo][:2]
    for k, nome in enumerate([outros[0], jogo, outros[1]]):
        x = W / 2 + (k - 1) * 320
        C.put(im, C.card_jogo(nome, 240, (-5, 0, 5)[k], 6, 28), x, 720)
        C.sticker(im, "+ recorde", x, 980, 32, (-4, 0, 4)[k], LIME, INK)
    C.texto(im, "30 jogos  =  30 chances de subir 📈", W / 2, 1110, 42, WHITE, g.F_BLACK, True)
    s.append(C.moldura(im, 2, T))
    im = C.fundo(i * 7 + 2)
    C.sticker(im, "RANKING GERAL · TOP 5", W / 2, 210, 50, -3, WHITE, INK)
    for k, (pts, pat) in enumerate(zip(C.RECORDES, C.PATENTES)):
        y = 400 + k * 175
        row = g.rounded((920, 150), 42, (255, 255, 255, 40 if k == 0 else 24),
                        outline=pat[2] + (230,), width=5 if k == 0 else 3)
        C.put(im, row, W / 2, y)
        C.texto(im, f"{k + 1}º", 110, y - 34, 52, pat[1], g.F_DISPLAY)
        C.put(im, C.avatar(96, "?", pat[1]), 280, y)
        C.texto(im, "???" if k == 0 else "pode ser tu 👀", 350, y - 44, 38, WHITE, g.F_BLACK)
        C.sticker(im, pat[0], 460, y + 28, 24, 0, pat[1], INK)
        lay = g.text_layer(C.numero(pts), 56, fill=WHITE, path=g.F_DISPLAY)
        im.alpha_composite(lay, (int(W - 120 - lay.width), int(y - lay.height / 2)))
    s.append(C.moldura(im, 3, T))
    im = C.fundo(i * 7 + 3, C.PATENTES[1][2], VIOLET)
    C.titulo(im, "duvido tu passar 👀", 300, 104, hl=(1, 2))
    C.texto(im, "conseguiu? manda print nos comentários 📸", W / 2, 470, 36, WHITE, g.F_BOLD, True)
    C.put(im, C.gema(dia[1], dia[2], 260), W / 2, 760)
    C.sticker(im, "quem sobe vira Diamante 💎", W / 2, 1000, 40, -2, LIME, INK)
    C.texto(im, "marca 3 amigos pra desafiar 👇", W / 2, 1110, 40, WHITE, g.F_BLACK, True)
    s.append(C.moldura(im, 4, T))
    s.append(C.slide_cta(i * 7 + 4, "aceita o desafio?"))
    leg = (f"se tu é bom mesmo, faz {alvo} no {jogo} 😤 {frase}\n"
           "teu recorde em cada jogo soma no ranking geral, e quem sobe ganha patente 💎\n"
           "conseguiu? manda print 📸 e marca 3 amigos 👇")
    return s, leg


def b_skins(i, titulo, grupos, duo):
    s = []
    im = C.fundo(i * 7, GOLD, VIOLET)
    destaque = grupos[0][1][:3]
    for k, it in enumerate(destaque):
        C.put(im, g.skin_image(it["arquivo"], (300, 380, 300)[k]), W / 2 + (k - 1) * 330,
              (930, 880, 930)[k])
    C.titulo(im, titulo, 360, 90, hl=(len(titulo.split()) - 2,))
    C.sticker(im, f"+{len(g.skins()) // 10 * 10} skins", W / 2, 1180, 56, -3, LIME)
    s.append(C.moldura(im, 1, T))
    for p, (nomep, lst, cor) in enumerate(grupos[:2]):
        im = C.fundo(i * 7 + 1 + p, cor, VIOLET)
        C.sticker(im, nomep, W / 2, 230, 60, -3, cor, INK)
        C.grade_skins(im, lst[:6], 560)
        s.append(C.moldura(im, p + 2, T))
    im = C.fundo(i * 7 + 3)
    C.titulo(im, "qual tu ia usar primeiro?", 330, 84, hl=(4,))
    for k, it in enumerate(duo):
        x = W / 2 + (k - .5) * 420
        C.put(im, g.skin_image(it["arquivo"], 330), x, 720)
        C.sticker(im, "A" if k == 0 else "B", x, 520, 64, (-6, 6)[k], LIME)
        C.sticker(im, it["nome"].replace("Título: ", ""), x, 930, 34, (-3, 3)[k], WHITE)
    C.texto(im, "comenta A ou B 👇", W / 2, 1060, 46, WHITE, g.F_BLACK, True)
    s.append(C.moldura(im, 4, T))
    s.append(C.slide_cta(i * 7 + 4, "cria tua conta e escolhe a tua"))
    leg = (f"{titulo} 👀 são +{len(g.skins()) // 10 * 10} skins no KAVIX\n"
           f"{duo[0]['nome']} ou {duo[1]['nome']}? comenta A ou B 👇\n"
           "tem item que só sai no passe de batalha 🎫 e cadastro novo ganha itens exclusivos 🎁")
    return s, leg


def b_versus(i, a, b, pergunta):
    s = []
    im = C.fundo(i * 7)
    C.titulo(im, pergunta, 300, 92, hl=(len(pergunta.split()) - 2,))
    for k, (nome, rot) in enumerate(((a, -7), (b, 7))):
        x = W / 2 + (k - .5) * 440
        C.put(im, C.card_jogo(nome, 340, rot), x, 860)
        C.sticker(im, ("A · " if k == 0 else "B · ") + nome, x, 1180, 40, -rot / 2, WHITE)
    C.put(im, g.sticker("VS", 70, "brand", INK, g.F_DISPLAY), W / 2, 860)
    s.append(C.moldura(im, 1, T))
    for k, nome in enumerate((a, b)):
        im = C.fundo(i * 7 + 1 + k, foto=C.shot(nome))
        C.put(im, C.card_jogo(nome, 470, (-4, 4)[k]), 330 if k == 0 else 750, 760)
        x = 820 if k == 0 else 260
        C.sticker(im, "A" if k == 0 else "B", x, 380, 130, (6, -6)[k], LIME)
        C.sticker(im, nome, x, 570, 50, -3, WHITE)
        C.texto(im, ["fácil de começar", "difícil de largar"][k], x, 680, 40, WHITE, g.F_BLACK, True)
        C.texto(im, ["😅", "🫠"][k], x, 750, 40, WHITE, g.F_BLACK, True)
        s.append(C.moldura(im, 2 + k, T))
    im = C.fundo(i * 7 + 3, LIME, VIOLET)
    C.titulo(im, "só pode jogar um pra sempre 😳", 300, 86, hl=(4,))
    C.texto(im, "comenta A ou B 👇", W / 2, 470, 52, WHITE, g.F_BLACK, True)
    for k, nome in enumerate((a, b)):
        C.put(im, C.card_jogo(nome, 280, (-6, 6)[k], 6, 28), W / 2 + (k - .5) * 360, 860)
    s.append(C.moldura(im, 4, T))
    s.append(C.slide_cta(i * 7 + 4, "joga os dois e decide"))
    leg = (f"{a} ou {b}? {pergunta} 👇\n"
           "só pode jogar um pra sempre… comenta A ou B")
    return s, leg


def b_30jogos(i, capa, frases, ordem):
    s = []
    im = C.fundo(i * 7)
    for k, (nome, x, y, r) in enumerate([(ordem[0], 200, 860, -10), (ordem[1], 880, 860, 9),
                                         (ordem[2], 540, 930, 0)]):
        C.put(im, C.card_jogo(nome, 300 if k < 2 else 340, r), x, y)
    C.sticker(im, "POV:", 230, 250, 54, -5, LIME)
    C.titulo(im, capa, 400, 96, hl=(1, 2))
    C.sticker(im, "e é de graça", W / 2, 1180, 46, 3, WHITE)
    s.append(C.moldura(im, 1, T))
    for p in range(3):
        im = C.fundo(i * 7 + 1 + p)
        C.titulo(im, frases[p], 205, 64, hl=(len(frases[p].split()) - 2,))
        C.grade_jogos(im, ordem[3 + p * 6:3 + p * 6 + 6], y0=480, cw=230, gap_y=470)
        s.append(C.moldura(im, p + 2, T))
    s.append(C.slide_cta(i * 7 + 4, "qual tu vai jogar primeiro?"))
    leg = (f"POV: {capa}\n"
           "salva esse post e comenta qual tu vai jogar primeiro 👇\n"
           "tem ranking competitivo com patentes e passe de batalha com itens raros 🏆🎫")
    return s, leg


def b_passe(i, capa, destaque, foco):
    s = []
    im = C.fundo(i * 7, GOLD, VIOLET)
    C.sticker(im, "PASSE DE BATALHA", W / 2, 260, 58, -4, GOLD, INK)
    C.titulo(im, capa, 410, 92, hl=(len(capa.split()) - 2,))
    for k, n in enumerate(destaque):
        C.put(im, g.skin_image(skin(n)["arquivo"], (280, 360, 280)[k]), W / 2 + (k - 1) * 320,
              (880, 820, 880)[k])
    C.texto(im, "30 níveis · trilha grátis + premium", W / 2, 1110, 40, WHITE, g.F_BLACK, True)
    s.append(C.moldura(im, 1, T))
    ordem = [("TRILHA PREMIUM ⭐", C.PASSE_PREMIUM, GOLD,
              "auras, molduras, títulos e as peças mais chamativas"),
             ("TRILHA GRÁTIS 🎁", C.PASSE_GRATIS, LIME, "todo mundo ganha itens só de jogar")]
    if foco == "gratis":
        ordem.reverse()
    for p, (nomep, itens, cor, sub) in enumerate(ordem):
        im = C.fundo(i * 7 + 1 + p, cor, VIOLET)
        C.sticker(im, nomep, W / 2, 220, 56, (-3, 3)[p], cor, INK)
        C.texto(im, sub, W / 2, 300, 32, (225, 225, 235), g.F_SEMI, True)
        C.grade_skins(im, [skin(n) for n in itens], 560, cw=290, ch=330)
        s.append(C.moldura(im, 2 + p, T))
    im = C.fundo(i * 7 + 3)
    C.titulo(im, "cada partida dá XP ⚡", 250, 86, hl=(3,))
    C.texto(im, "sobe de nível e libera recompensa nova", W / 2, 360, 36, WHITE, g.F_BOLD, True)
    for k, (nivel, frac, item) in enumerate(((1, .25, "Boina"), (12, .6, "Óculos Dourados"),
                                             (30, 1.0, "Aura Estelar"))):
        y = 520 + k * 250
        card = g.rounded((940, 210), 40, (255, 255, 255, 26), outline=(255, 255, 255, 70), width=3)
        C.put(im, card, W / 2, y)
        C.sticker(im, f"NÍVEL {nivel}", 250, y - 40, 40, -3, LIME if nivel < 30 else GOLD, INK)
        C.barra_xp(im, y + 20, frac, w=440, h=30)
        C.put(im, g.skin_image(skin(item)["arquivo"], 150), 860, y)
        C.texto(im, item, 630, y - 58, 30, WHITE, g.F_BOLD)
    s.append(C.moldura(im, 4, T))
    s.append(C.slide_cta(i * 7 + 4, "começa a temporada agora"))
    leg = (f"{capa} 🎫 o KAVIX tem passe de batalha: 30 níveis de recompensas\n"
           "trilha grátis pra todo mundo e trilha premium com auras, coroas, molduras e títulos raros\n"
           "qual item tu quer primeiro? comenta 👇")
    return s, leg


def b_ranking(i, capa):
    s, leg = C.modelo_ranking()[1:]
    im = C.fundo(i * 7, SKY, VIOLET)
    C.titulo(im, capa, 330, 92, hl=(len(capa.split()) - 2,))
    pats = C.PATENTES[i % 3: i % 3 + 3]
    for k, (nome, c1, c2) in enumerate(pats):
        C.put(im, C.gema(c1, c2, (260, 340, 260)[k]), W / 2 + (k - 1) * 300, (880, 820, 880)[k])
    C.texto(im, "sobe de patente e mostra quem manda 😤", W / 2, 1120, 38, WHITE, g.F_BLACK, True)
    s[0] = C.moldura(im, 1, T)
    leg = capa + " 🏆\n" + leg.split("\n", 1)[1]
    return s, leg


def b_conhece(i, capa, jogos3):
    s, leg = C.modelo_conhece()[1:]
    im = C.fundo(i * 7, foto=C.shot(jogos3[1]))
    C.titulo(im, capa, 330, 96, hl=(len(capa.split()) - 2,))
    C.texto(im, "salva esse post antes que suma 📌", W / 2, 560, 40, WHITE, g.F_BOLD, True)
    for k, nome in enumerate(jogos3):
        C.put(im, C.card_jogo(nome, 260, (-7, 0, 7)[k], 6, 28), W / 2 + (k - 1) * 300, 930)
    s[0] = C.moldura(im, 1, T)
    return s, capa + "\n" + leg.split("\n", 1)[1]


# ---------------------------------------------------------------- catálogo

def catalogo():
    sk = g.skins()
    jogos = [x["nome"] for x in g.library()]

    def tipo(t, rar=None):
        return [x for x in sk if x["tipo"] == t and (rar is None or x["raridade"] == rar)]

    lend = [x for x in sk if x["raridade"] == "lendario"]
    epic = [x for x in sk if x["raridade"] == "epico" and x["tipo"] in ("roupa", "chapeu", "aura", "olhos")]
    raro = [x for x in sk if x["raridade"] == "raro" and x["tipo"] in ("chapeu", "olhos", "aura", "roupa")]
    falas = ["esse aqui é tenso 😤", "não consigo parar 😭", "um toque errado e já era 💀",
             "clássico demais 🔥", "o mais insano de todos 🤯", "viciante nível máximo 🫠",
             "olha que satisfatório 🤤", "parece fácil mas não é 🙂", "o meu favorito 👑",
             "esse aqui é paz 😌", "testa teu reflexo ⚡", "dá raiva e vicia 😂"]

    def f5(k):
        return [falas[(k + j) % len(falas)] for j in range(5)]

    itens = [
        ("top5", "jogos mais difíceis", lambda i: b_top5(i, "jogos mais difíceis",
         ["Ricochete", "Gravidade", "Zigue-Zague", "Equilíbrio", "Fio"], f5(0))),
        ("desafio", "recorde geral", None),
        ("skins", "lendárias", lambda i: b_skins(i, "as skins mais raras do jogo",
         [("LENDÁRIAS 👑", lend, GOLD), ("ÉPICAS 💜", epic, (176, 107, 255))], lend[:2])),
        ("versus", "Cobrinha x Boliche", lambda i: b_versus(i, "Cobrinha", "Boliche", "qual tu escolhe?")),
        ("passe", "temporada 1", lambda i: b_passe(i, "temporada 1 chegou",
         ["Aura Cosmos", "Coroa Suprema", "Aura Estelar"], "premium")),
        ("30jogos", "30 jogos", lambda i: b_30jogos(i, "tem 30 jogos nesse site 😳",
         ["os clássicos 🔥", "pra testar reflexo ⚡", "e muito mais 🫠"], jogos)),
        ("ranking", "patentes", lambda i: b_ranking(i, "tem RANKING e modo COMPETITIVO")),
        ("top5", "pra testar reflexo", lambda i: b_top5(i, "jogos pra testar reflexo",
         ["Três Pistas", "Escudo", "Corte", "Sinal", "Pulso"], f5(3))),
        ("desafio", "Espinhos", lambda i: b_desafio(i, "Espinhos", "30 pontos", "duvido 😤")),
        ("conhece", "conhece o KAVIX", lambda i: b_conhece(i, "tu ainda não conhece o KAVIX? 🤔",
         ["Hélice", "Bolhas", "Canhão"])),
        ("skins", "roupas", lambda i: b_skins(i, "roupas completas pra tua bolinha",
         [("ROUPAS 🥷", tipo("roupa"), (176, 107, 255)), ("CHAPÉUS 🎩", tipo("chapeu"), SKY)],
         tipo("roupa")[3:5])),
        ("versus", "Empilha x Encaixe", lambda i: b_versus(i, "Empilha", "Encaixe", "qual vicia mais?")),
        ("top5", "mais relaxantes", lambda i: b_top5(i, "jogos mais relaxantes",
         ["Ponte", "Balanço", "Encaixe", "Órbita", "Bolhas"], f5(6))),
        ("passe", "trilha grátis", lambda i: b_passe(i, "tem item grátis pra todo mundo",
         ["Óculos Dourados", "Aura Estelar", "Rastro Prata"], "gratis")),
        ("desafio", "Empilha", lambda i: b_desafio(i, "Empilha", "20 andares", "quero ver 👀")),
        ("30jogos", "30 jogos 2", lambda i: b_30jogos(i, "achei 30 jogos num site só 🎮",
         ["pra jogar no ônibus 🚌", "pra quem curte desafio 😤", "pra jogar antes de dormir 🌙"],
         jogos[::-1])),
        ("ranking", "ranking por jogo", lambda i: b_ranking(i, "cada jogo tem seu ranking")),
        ("top5", "mais viciantes", lambda i: b_top5(i, "jogos mais viciantes",
         ["Empilha", "Cobrinha", "Espinhos", "Quebra Blocos", "Reflexo"], f5(1))),
        ("skins", "auras", lambda i: b_skins(i, "auras e chapéus que brilham",
         [("AURAS ✨", tipo("aura"), SKY), ("CHAPÉUS 👑", tipo("chapeu"), GOLD)],
         tipo("aura")[:2])),
        ("versus", "Reflexo x Pulso", lambda i: b_versus(i, "Reflexo", "Pulso", "qual é mais difícil?")),
        ("desafio", "Cobrinha", lambda i: b_desafio(i, "Cobrinha", "25 pontos", "marca quem consegue 👇")),
        ("passe", "itens raros", lambda i: b_passe(i, "itens raros te esperando",
         ["Moldura Esmeralda", "Coroa de Gelo", "Aura Dourada"], "premium")),
        ("top5", "pra jogar no ônibus", lambda i: b_top5(i, "jogos pra jogar no ônibus",
         ["Passagem", "Troca Cor", "Pega Tudo", "Trampolim", "Memória"], f5(8))),
        ("conhece", "sem baixar nada", lambda i: b_conhece(i, "30 jogos sem baixar nada 🙌",
         ["Pula Corda", "Boliche", "Gravidade"])),
        ("30jogos", "30 jogos 3", lambda i: b_30jogos(i, "tem jogo pra todo tipo de gamer 🎮",
         ["pra testar teu cérebro 🧠", "pra quem tem dedo rápido ⚡", "pra jogar com os amigos 👥"],
         jogos[10:] + jogos[:10])),
        ("desafio", "Quebra Blocos", lambda i: b_desafio(i, "Quebra Blocos", "40 pontos", "só os brabos 🔥")),
        ("skins", "épicas e raras", lambda i: b_skins(i, "skins épicas e raras",
         [("ÉPICAS 💜", epic[3:], (176, 107, 255)), ("RARAS 💎", raro, SKY)], epic[:2])),
        ("ranking", "títulos", lambda i: b_ranking(i, "tem patente e título pra conquistar")),
        ("top5", "que ninguém passa do nível 5", lambda i: b_top5(i, "jogos que ninguém zera",
         ["Canhão", "Espelho", "Pula Corda", "Hélice", "Corte"], f5(10))),
        ("versus", "Bolhas x Pega Tudo", lambda i: b_versus(i, "Bolhas", "Pega Tudo", "qual tu jogaria agora?")),
    ]
    out = []
    for i, (fmt, tema, fn) in enumerate(itens, 1):
        if fn is None:  # desafio do recorde geral (modelo 7)
            fn = (lambda i: C.modelo_recorde()[1:])
        out.append((i, fmt, tema, fn))
    return out


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    linhas = []
    for i, fmt, tema, fn in catalogo():
        slides, leg = fn(i)
        assert len(slides) == 5, (i, tema, len(slides))
        pasta = os.path.join(OUT, f"{i:02d}_{fmt}_{g._slug(tema).strip('_')}")
        os.makedirs(pasta)
        for k, im in enumerate(slides, 1):
            im.convert("RGB").save(os.path.join(pasta, f"slide_{k:02d}.jpg"), quality=90)
        legenda = f"{leg}\n\n{FINAL[i % len(FINAL)]}\n\n{tags(i)}"
        with open(os.path.join(pasta, "legenda.txt"), "w") as fh:
            fh.write(legenda + "\n")
        linhas.append({"n": i, "dia_sugerido": i, "hora_sugerida": "15:00",
                       "pasta": os.path.basename(pasta), "formato": fmt, "tema": tema,
                       "legenda": legenda})
        print("ok:", os.path.basename(pasta), flush=True)
    with open(os.path.join(OUT, "legendas.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    with open(os.path.join(OUT, "LEIA-ME.txt"), "w") as fh:
        fh.write("30 carrosséis do KAVIX ARCADE (5 fotos cada, 1080x1350)\n\n"
                 "Cada pasta = 1 post. Suba as fotos na ordem (slide_01 a slide_05) e cole o\n"
                 "texto de legenda.txt.\n\n"
                 "Sugestão: 1 carrossel por dia às 15:00, entre os reels das 12:30 e das 17:00,\n"
                 "na ordem das pastas (01 = dia 1). Instagram e Facebook aceitam carrossel;\n"
                 "no TikTok use o modo 'foto' (carrossel de fotos).\n\n"
                 "legendas.csv tem todas as legendas numa planilha.\n"
                 "Antes de postar o desafio do recorde, confira no site se o 1º lugar ainda é 2.428 pontos.\n")
    if os.path.exists(ZIP):
        os.remove(ZIP)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_STORED) as z:
        for root, _, files in os.walk(OUT):
            for f in sorted(files):
                p = os.path.join(root, f)
                z.write(p, os.path.join("kavix_carrosseis_30", os.path.relpath(p, OUT)))
    print("zip:", ZIP, round(os.path.getsize(ZIP) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
