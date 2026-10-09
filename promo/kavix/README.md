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

## Como gerar de novo / editar

Precisa de `python3`, `pillow`, `numpy` e `ffmpeg`.

```bash
python3 promo/kavix/gerar_videos.py              # gera todos
python3 promo/kavix/gerar_videos.py desafio      # gera só um
```

Os textos de cada vídeo ficam nas funções `spec_*` de `gerar_videos.py`. Para
trocar uma frase, edite a string e rode de novo. A URL fica na constante `URL`.
