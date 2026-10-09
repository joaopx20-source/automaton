# Vídeos promocionais KAVIX

Vídeos curtos para divulgar o **KAVIX** ([kavixbrasil.com.br](https://kavixbrasil.com.br/)),
que roda no celular e no computador, com a chamada **"Cadastre-se agora e ganhe itens exclusivos"**.

Tudo (arte, animação e trilha sonora) é gerado por código. Não há imagens nem
músicas de terceiros, então não tem risco de direitos autorais.

## Vídeos (`videos/`)

| Arquivo | Formato | Duração | Onde postar | Roteiro |
|---|---|---|---|---|
| `kavix_hype_1080x1920.mp4` | 9:16 | 16s | Reels, TikTok, Shorts, Stories | "Preparado?" → 3-2-1 → logo → celular e PC → baú de itens → CTA |
| `kavix_plataformas_1080x1920.mp4` | 9:16 | 15s | Reels, TikTok, Shorts | "Um jogo. Duas telas." → celular ou computador → "Cadastro novo = itens exclusivos" → CTA |
| `kavix_itens_1080x1920.mp4` | 9:16 | 16s | Reels, TikTok, anúncios | "Atenção, jogador!" → baú abrindo → cartas de itens exclusivos → CTA |
| `kavix_desafio_1080x1920.mp4` | 9:16 | 10s | Stories, anúncio rápido | "Seus amigos já tão jogando... E você?" → logo → CTA |
| `kavix_hype_feed_1080x1080.mp4` | 1:1 | 16s | Feed Instagram/Facebook | Versão quadrada do vídeo hype |
| `kavix_hype_youtube_1920x1080.mp4` | 16:9 | 16s | YouTube, Facebook, site | Versão horizontal do vídeo hype |

## Legendas prontas

**Hype**
> 🎮 Chegou a hora! O KAVIX já está disponível no celular e no PC.
> Cadastre-se agora e ganhe itens exclusivos 🎁
> 👉 kavixbrasil.com.br
> #kavix #games #jogosonline #gamerbrasil #mobilegames #pcgamer

**Plataformas**
> 📱💻 Celular ou computador? Você escolhe!
> Crie sua conta no KAVIX e ganhe itens exclusivos.
> 👉 kavixbrasil.com.br
> #kavix #jogos #gamer #jogonocelular #pcgaming

**Itens exclusivos**
> 🎁 Presente pra você! Itens exclusivos só pra quem se cadastrar no KAVIX.
> Garanta os seus 👉 kavixbrasil.com.br
> #kavix #itensexclusivos #gamerbrasil #games

**Desafio**
> Seus amigos já tão jogando... e você? 👀
> Bora pro KAVIX! Cadastro com itens exclusivos 👉 kavixbrasil.com.br
> #kavix #bora #games #gamerbrasil

## Vídeos com gameplay real (celular e PC)

O gerador coloca gravações reais do jogo **dentro da tela do celular e do
monitor**. Quando elas existem:

- surgem 3 vídeos novos: `kavix_gameplay_1080x1920.mp4` (9:16),
  `kavix_gameplay_feed_1080x1080.mp4` (1:1) e
  `kavix_gameplay_youtube_1920x1080.mp4` (16:9), com 22s cada. O roteiro é:
  "Veja o KAVIX em ação!" → jogo no celular → jogo no computador → os dois
  lado a lado → baú de itens exclusivos → "Cadastre-se agora";
- os vídeos *hype* e *plataformas* trocam a arte desenhada pelo jogo de verdade;
- aparece o selo **GAMEPLAY REAL** no canto.

### 1. Conseguir as gravações (escolha uma opção)

**A) Gravar você mesmo (melhor qualidade).**
- Celular: use o gravador de tela do Android ou do iPhone enquanto joga.
  Grave em pé (vertical) por 20 a 60 segundos, mostrando as melhores partes.
- PC: use o OBS Studio, a Barra de Jogo do Windows (`Win + Alt + R`) ou outro
  gravador, em 1920x1080.

**B) Gravação automática do site** (precisa do Node + Playwright):

```bash
NODE_PATH="$(npm root -g)" node promo/kavix/gravar_gameplay.cjs 30
# para abrir o navegador e você mesmo jogar enquanto grava:
KAVIX_HEADED=1 NODE_PATH="$(npm root -g)" node promo/kavix/gravar_gameplay.cjs 60
```

O script abre o site como um iPhone e depois como um PC 1920x1080. Ele tenta
clicar em "Jogar" e salva `gameplay/celular.webm` e `gameplay/pc.webm`. Sem
`KAVIX_HEADED=1`, as interações são cliques genéricos. Se o jogo pedir login
ou tiver controles específicos, a opção A rende um vídeo melhor.

### 2. Colocar os arquivos na pasta

```
promo/kavix/gameplay/celular.mp4   (ou .webm/.mov — gravação do celular)
promo/kavix/gameplay/pc.mp4        (ou .webm/.mov — gravação do computador)
```

### 3. Gerar

```bash
python3 promo/kavix/gerar_videos.py
```

As gravações são cortadas e encaixadas automaticamente e tocam em loop se
forem curtas. O som delas é descartado e entra a trilha do vídeo.

## Como gerar de novo / editar

Precisa de `python3`, `pillow`, `numpy` e `ffmpeg`.

```bash
python3 promo/kavix/gerar_videos.py              # gera todos
python3 promo/kavix/gerar_videos.py desafio      # gera só um
```

Os textos de cada vídeo ficam nas funções `spec_*` de `gerar_videos.py`. Para
trocar uma frase, edite a string e rode de novo. A URL fica na constante `URL`.
