# Postagem da campanha 2 do KAVIX ARCADE (mais 100 reels, foco em conversão)

Instruções para quem for agendar os posts (Codex ou uma pessoa).

## O que tem aqui

| Arquivo | O que é |
|---|---|
| `videos/NNN_<formato>_<assunto>.mp4` | Os 100 vídeos, 1080x1920 (9:16), de 15 a 27 segundos, com som |
| `plano_postagem.json` | Um item por post: vídeo, data e hora, legendas de cada rede e link de download |
| `plano_postagem.csv` | O mesmo conteúdo em planilha |

Campos de cada post (`plano_postagem.json`):

- `n`: número do post (1 a 100); também é o prefixo do nome do vídeo.
- `dia_campanha` (1 a 25), `hora`; `data` e `data_hora` ficam vazios até definir o início.
- `data`, `hora`, `data_hora`: quando publicar, **horário de Brasília**
  (`America/Sao_Paulo`, UTC−3). Ex.: `2026-10-12T09:00:00-03:00`.
- `arquivo`: caminho do vídeo nesta pasta.
- `url_download`: link direto para baixar o vídeo.
- `legenda_instagram_facebook`, `legenda_tiktok`: texto completo do post, já com hashtags.
- `titulo_youtube` (até 100 caracteres) e `descricao_youtube`.

## Calendário (separado da campanha 1, para usar depois)

- **4 posts por dia**, nos mesmos horários da campanha 1: **09:00, 12:30, 17:00 e
  20:30** (Brasília).
- O calendário está organizado por **dia da campanha** (`dia_campanha` = 1 a 25),
  **sem datas fixas**. Antes de agendar, escolha o dia de início e preencha as datas:

  ```bash
  python3 promo/kavix/campanha2.py plano 2026-12-01   # troque pela data de início
  ```

  Isso preenche `data` e `data_hora` em `plano_postagem.json`/`.csv`. Sem rodar o
  comando: data do post = data de início + (`dia_campanha` − 1) dias, no `hora` indicado.
- O **mesmo vídeo** vai para as **4 redes no mesmo horário**: Instagram (Reels),
  Facebook (Reels), TikTok e YouTube (Shorts).
- A ordem já intercala os 7 formatos; não reordene.

## Como baixar os vídeos

Clonar só esta branch (traz tudo de uma vez):

```bash
git clone --depth 1 --branch claude/kavix-promotional-videos-e6f1vd \
  https://github.com/joaopx20-source/automaton.git
cd automaton/promo/kavix/campanha2
```

Ou baixar um a um pelo campo `url_download` do JSON.

## Como agendar em cada rede (ferramentas oficiais, sem Buffer)

Contas: Instagram **@kavixarcade**, a Página do Facebook ligada a ele, o TikTok e o
canal do YouTube do KAVIX ARCADE.

1. **Instagram + Facebook: Meta Business Suite** (business.facebook.com → Planejador
   → Criar Reel). Marque Instagram e Facebook no mesmo Reel, envie o vídeo, cole
   `legenda_instagram_facebook` e agende para `data_hora`.
   Limite: até **29 dias** à frente.
2. **TikTok: TikTok Studio** (tiktok.com/tiktokstudio/upload). Envie o vídeo, cole
   `legenda_tiktok`, ative "Agendar" e escolha `data_hora`.
   Limite: até **10 dias** à frente. Agende em lotes: os posts dos próximos 10
   dias agora (até 40 posts) e o resto quando a data entrar na janela.
3. **YouTube Shorts: YouTube Studio** (studio.youtube.com → Criar → Enviar vídeos).
   Título = `titulo_youtube`, descrição = `descricao_youtube`, "Não é conteúdo para
   crianças", Visibilidade → **Programar** → `data_hora`.
   Atenção ao limite diário de envios do YouTube. Se aparecer "limite de
   carregamento diário atingido", pare e continue no dia seguinte do ponto onde parou.

## Regras

- Publique **exatamente** o vídeo e o texto do plano; não troque legendas nem hashtags.
- Confira o fuso: o horário é de **Brasília**. Se a ferramenta estiver em outro fuso,
  converta.
- Antes de agendar, veja se o post já não está agendado (evita duplicar).
- Registre o andamento num arquivo `postados.csv` (`n,rede,status,data_hora,link`),
  para retomar de onde parou se algo travar.
- Se uma rede recusar um vídeo, anote o erro e siga para o próximo; não mude o vídeo.

## Resumo dos formatos

desafio (30), pergunta (15), meme (15), skin_do_dia (15), tutorial (10),
duelo_skins (10), tier_list (5).
