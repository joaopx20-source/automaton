# Vídeos promocionais KAVIX

Vídeos curtos para divulgar o **KAVIX ARCADE** ([kavixbrasil.com.br](https://kavixbrasil.com.br/)),
que roda no celular e no computador, com a chamada **"Cadastre-se agora e ganhe itens exclusivos"**.

Estilo de post atual de TikTok/Reels:

- **jogabilidade real em tela cheia**, sempre em **2x** (11 dos mais de 20 jogos do site);
- **gancho** logo no primeiro segundo ("POV: você achou +20 jogos num site só 🎮",
  "duvido você passar de 30 pontos 😤", "e tu aí parado 💀");
- **legendas palavra por palavra** com contorno e destaque em verde-limão, com emojis;
- **etiquetas brancas** inclinadas com o nome de cada jogo;
- **perfil `@kavixbrasil`** com o mascote e **barra de progresso** no topo, como num post;
- **cortes rápidos com zoom** e trilha **trap/phonk** sintetizada;
- PC mostrado como **janela do navegador** (com kavixbrasil.com.br na barra);
- final em **cartão de vidro** com o botão no degradê roxo → ciano do site.

Arte, animações e música são geradas por código, então não há música nem imagem
de terceiros.

## Vídeos (`videos/`)

| Arquivo | Formato | Duração | Roteiro |
|---|---|---|---|
| `kavix_arcade_1080x1920.mp4` | 9:16 | 25s | "POV: você achou +20 jogos num site só 🎮" → cortes rápidos por todos os jogos → "celular ou PC? tu escolhe 😎" → final |
| `kavix_arcade_feed_1080x1350.mp4` | 4:5 | 25s | Mesmo roteiro, para o feed do Instagram/Facebook |
| `kavix_arcade_youtube_1920x1080.mp4` | 16:9 | 25s | Mesmo roteiro, horizontal |
| `kavix_plataformas_1080x1920.mp4` | 9:16 | 18s | "joga no celular 📱" → "ou no PC 💻" → "sem baixar nada 🙌" → montagem → final |
| `kavix_plataformas_youtube_1920x1080.mp4` | 16:9 | 18s | Mesmo roteiro, horizontal |
| `kavix_desafio_1080x1920.mp4` | 9:16 | 12s | "teus amigos já tão jogando..." → "e tu aí parado 💀" → "bora? 👀" → final |
| `kavix_itens_1080x1920.mp4` | 9:16 | 12s | "cadastro novo = itens exclusivos 🎁" → "+20 jogos pra jogar" → final |
| `kavix_destaque_<jogo>_1080x1920.mp4` | 9:16 | 13,5s | Um por jogo: gancho de desafio → jogo em tela cheia → "e no PC também" → final (11 vídeos) |

Onde postar: 9:16 → Reels, TikTok, Shorts e Stories · 4:5 → feed · 16:9 → YouTube e Facebook.

## Legendas prontas

**Arcade**
> POV: você achou +20 jogos num site só 🎮
> roda no celular e no PC, direto no navegador 📱💻
> cria tua conta e ganha itens exclusivos 🎁 👉 kavixbrasil.com.br
> #kavix #kavixarcade #jogos #gamer #fyp #viral

**Destaque de um jogo** (troque o nome)
> duvido tu passar de 30 pontos no Espinhos 😤 comenta teu recorde 👇
> joga agora no celular ou no PC 👉 kavixbrasil.com.br
> #kavix #desafio #jogos #fyp

**Plataformas**
> celular ou PC? tu escolhe 😎 sem baixar nada.
> 👉 kavixbrasil.com.br · cadastro novo ganha itens exclusivos 🎁
> #kavix #jogosnonavegador #gamer #fyp

**Desafio**
> teus amigos já tão jogando e tu aí parado 💀
> marca quem vai perder pra ti 👇 kavixbrasil.com.br
> #kavix #desafio #jogos #fyp

**Itens exclusivos**
> cadastro novo = itens exclusivos 🎁 só pra quem cria conta agora
> 👉 kavixbrasil.com.br
> #kavix #itensexclusivos #gamer #fyp

## Adicionar ou trocar gravações

### 1. Gravar

O ideal é gravar a tela do PC com o jogo aberto no navegador, como nas
gravações atuais. Grave bastante tempo de cada jogo (30s ou mais), porque os
vídeos usam trechos diferentes de cada gravação.

**Gravação automática do modo bot** (`https://kavix-arcade.web.app/auto.html`):
o bot joga sozinho e o script aperta **N** para pular de jogo em jogo.

```bash
NODE_PATH="$(npm root -g)" node promo/kavix/gravar_auto.cjs 24 25   # 24 jogos, 25s cada
```

- Grava duas vezes: como **celular** (tela em pé 540x1170, toque e user agent
  de iPhone) e como **PC** (1920x1080), em `gameplay/celular.mp4` e `gameplay/pc.mp4`.
- No Linux com `Xvfb` e `ffmpeg`, o navegador roda em tela cheia numa tela
  virtual e o ffmpeg grava em H.264 30fps de alta qualidade, sem abas nem
  barra de endereço. Sem isso, usa a gravação do Playwright (.webm, qualidade menor).
- O `.json` ao lado guarda o **nome de cada jogo** (lido da página) e o segundo
  em que ele começa. O gerador **soma** esses jogos aos de `jogos.json`, pulando
  os que já têm gravação manual. Os vídeos arcade e de destaque passam a incluir
  todos eles, sem precisar preparar nada.
- Para rodar no ambiente do Claude, libere `kavix-arcade.web.app` na rede do
  ambiente, junto com os domínios que o jogo carrega (por exemplo,
  `*.firebaseapp.com`, `*.googleapis.com` e `*.gstatic.com`).

### 2. Preparar

```bash
python3 promo/kavix/preparar_gravacoes.py "Espinhos=minha_gravacao1.mp4" "Cobrinha=gravacao2.mp4" ...
```

Para cada gravação, o script acha a área do jogo e corta o trecho de jogo
ativo, sem a abertura escura e sem a tela de "fim de jogo". Depois gera
`gameplay/jogos/<jogo>_celular.mp4` e `<jogo>_pc.mp4` e atualiza
`gameplay/jogos.json`. Passe **todas** as gravações de uma vez, porque o
`jogos.json` é reescrito a cada execução.

### 3. Gerar

```bash
python3 promo/kavix/gerar_videos.py                 # todos
python3 promo/kavix/gerar_videos.py arcade desafio  # só alguns
KAVIX_SPEED=1 python3 promo/kavix/gerar_videos.py   # jogo em velocidade normal
```

Precisa de `python3`, `pillow`, `numpy`, `ffmpeg` e a fonte Noto Color Emoji.
Os textos de cada vídeo ficam nas funções `spec_*` de `gerar_videos.py`
(ganchos dos destaques em `HOOKS`). A quantidade de jogos anunciada fica em
`TOTAL_JOGOS` e o @ do perfil em `HANDLE`.
