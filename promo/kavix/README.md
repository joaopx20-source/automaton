# Vídeos promocionais KAVIX

Vídeos curtos para divulgar o **KAVIX ARCADE** ([kavixbrasil.com.br](https://kavixbrasil.com.br/)),
que roda no celular e no computador, com a chamada **"Cadastre-se agora e ganhe itens exclusivos"**.

Eles usam a **jogabilidade real** dos jogos gravados (11 dos mais de 20 jogos do site), a partir das gravações de tela
em `gameplay/`, sempre em **velocidade 2x**. O jogo aparece dentro de um
celular (só a área do jogo, em pé) e dentro de um monitor (o navegador inteiro,
com a barra de endereço). Arte, animações e trilha sonora são geradas por
código, então não há música nem imagem de terceiros.

O visual segue o tema do site: fundo azul-marinho escuro, botão em degradê
roxo → ciano (como "Jogar de novo"), etiquetas em pílula (como "FIM DE JOGO" e
"+XP no passe"), o mascote de coroa e a tela final no formato do cartão
"Fim de jogo". As cores ficam nas constantes `BG`, `CARD`, `VIOLET`, `SKY`
etc., no topo de `gerar_videos.py`.

## Vídeos (`videos/`)

### Com jogabilidade real

| Arquivo | Formato | Duração | Roteiro |
|---|---|---|---|
| `kavix_arcade_1080x1920.mp4` | 9:16 | ~40s | "+20 jogos num só lugar!" → passa por **todos os jogos gravados** (celular e PC) → celular + PC → baú → CTA |
| `kavix_arcade_feed_1080x1080.mp4` | 1:1 | ~40s | Mesmo roteiro, quadrado |
| `kavix_arcade_youtube_1920x1080.mp4` | 16:9 | ~40s | Mesmo roteiro, horizontal |
| `kavix_gameplay_1080x1920.mp4` | 9:16 | 22s | "Veja o KAVIX em ação!" → Espinhos no celular → Quebra Blocos no PC → os dois juntos → baú → CTA |
| `kavix_gameplay_feed_1080x1080.mp4` | 1:1 | 22s | Mesmo roteiro, quadrado |
| `kavix_gameplay_youtube_1920x1080.mp4` | 16:9 | 22s | Mesmo roteiro, horizontal |
| `kavix_destaque_<jogo>_1080x1920.mp4` | 9:16 | 15s | Um vídeo por jogo: nome → jogo no celular → "também no PC" → CTA (11 vídeos) |

Os destaques existem para: Espinhos, Passagem, Quebra Blocos, Três Pistas,
Pega Tudo, Órbita, Reflexo, Troca Cor, Empilha, Cobrinha e Memória.

### Com arte animada (e trecho de jogo real na cena "celular e PC")

| Arquivo | Formato | Duração | Roteiro |
|---|---|---|---|
| `kavix_hype_1080x1920.mp4` | 9:16 | 16s | "Preparado?" → 3-2-1 → logo → celular e PC → baú → CTA |
| `kavix_hype_feed_1080x1080.mp4` | 1:1 | 16s | Versão quadrada |
| `kavix_hype_youtube_1920x1080.mp4` | 16:9 | 16s | Versão horizontal |
| `kavix_plataformas_1080x1920.mp4` | 9:16 | 15s | "Um jogo. Duas telas." → celular ou computador → CTA |
| `kavix_itens_1080x1920.mp4` | 9:16 | 16s | "Atenção, jogador!" → baú → cartas de itens exclusivos → CTA |
| `kavix_desafio_1080x1920.mp4` | 9:16 | 10s | "Seus amigos já tão jogando... E você?" → CTA |

Onde postar: 9:16 → Reels, TikTok, Shorts e Stories · 1:1 → feed do Instagram
e do Facebook · 16:9 → YouTube, Facebook e site.

## Legendas prontas

**Arcade / gameplay**
> 🎮 Mais de 20 jogos num só lugar! Espinhos, Quebra Blocos, Cobrinha, Memória e muito mais.
> Jogue no celular ou no PC 📱💻
> Cadastre-se agora e ganhe itens exclusivos 🎁 👉 kavixbrasil.com.br
> #kavix #kavixarcade #games #jogosonline #gamerbrasil #mobilegames

**Destaque de um jogo** (troque o nome)
> Quantos pontos você faz no Quebra Blocos? 🧱🔥
> Jogue no celular ou no PC 👉 kavixbrasil.com.br
> Cadastro novo ganha itens exclusivos 🎁
> #kavix #kavixarcade #desafio #games #gamerbrasil

**Hype**
> 🎮 Chegou a hora! O KAVIX já está disponível no celular e no PC.
> Cadastre-se agora e ganhe itens exclusivos 🎁
> 👉 kavixbrasil.com.br
> #kavix #games #jogosonline #gamerbrasil #mobilegames #pcgamer

**Itens exclusivos**
> 🎁 Presente pra você! Itens exclusivos só pra quem se cadastrar no KAVIX.
> Garanta os seus 👉 kavixbrasil.com.br
> #kavix #itensexclusivos #gamerbrasil #games

**Desafio**
> Seus amigos já tão jogando... e você? 👀
> Bora pro KAVIX! Cadastro com itens exclusivos 👉 kavixbrasil.com.br
> #kavix #bora #games #gamerbrasil

## Adicionar ou trocar gravações

### 1. Gravar

O ideal é gravar a tela do PC com o jogo aberto no navegador, como nas
gravações atuais. Grave bastante tempo de cada jogo (30s ou mais), porque os
vídeos usam trechos diferentes de cada gravação.

Outra opção é a gravação automática do modo bot
(`https://kavix-arcade.web.app/auto.html`), que pula de jogo em jogo com a tecla N:

```bash
NODE_PATH="$(npm root -g)" node promo/kavix/gravar_auto.cjs 20 20   # 20 modos, 20s cada
```

Ela grava como iPhone e como PC em `gameplay/celular.webm` e `gameplay/pc.webm`,
com os tempos de cada modo em `.json`. O gerador usa esses arquivos quando não
existe `gameplay/jogos.json`.

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

Precisa de `python3`, `pillow`, `numpy` e `ffmpeg`. Os textos de cada vídeo
ficam nas funções `spec_*` de `gerar_videos.py`. A quantidade de jogos
mostrada no vídeo arcade fica em `TOTAL_JOGOS`.
