# 📉 Monitor de Preços

Ferramenta web para **monitorar preços de produtos**, ver o **histórico de quedas**, ser
**notificado quando o preço cair** e **buscar cupons** para a loja — por exemplo, para comprar
um PS5 pelo menor preço.

- Zero dependências: só precisa de **Node.js 20+**.
- Dados salvos em `data/db.json`.
- Funciona no PC, no celular (pelo navegador) e em qualquer servidor/VPS.

## Como usar

```bash
cd price-tracker
npm start            # ou: node server.js
# abra http://localhost:3000
```

1. Cole o link do produto (ex.: o PS5 na KaBuM!, Amazon, Magalu, Mercado Livre…).
2. Defina o **preço-alvo** (ex.: R$ 3.200) e, se quiser, a **queda mínima em %** para ser avisado.
3. Adicione o **mesmo produto em várias lojas**: a tabela "Comparação" mostra onde está mais barato.
4. Clique em **Histórico** para ver o gráfico, o menor preço já registrado, a média e todas as quedas.
5. Na aba **Cupons**, busque cupons da loja antes de comprar.

### Quando você é avisado

| Alerta | Quando dispara |
|---|---|
| 🎯 Preço-alvo atingido | o preço fica igual ou abaixo do seu alvo (e de novo se cair ainda mais) |
| 📉 Queda de preço | o preço cai pelo menos X% em relação à última leitura (padrão 3%) |
| 🏆 Menor preço histórico | o preço fica abaixo de tudo que já foi registrado |
| ✅ Voltou ao estoque | o produto estava esgotado e voltou |
| 🎟️ Cupom novo | apareceu um cupom novo para uma loja que você monitora |

O selo de cada produto diz se é uma boa hora: *Menor preço já registrado*, *Perto do menor preço*,
*Abaixo da média*, *Na média* ou *Acima da média — espere*.

### Notificações

- **Navegador:** clique em "Ativar notificações no navegador" (funciona com a aba aberta).
- **Celular (recomendado):** instale o app [ntfy](https://ntfy.sh) (Android/iOS), assine um tópico com
  nome difícil de adivinhar (ex.: `ps5-alerta-x8k2`) e coloque esse tópico em *Configurações*.
- **Telegram:** crie um bot com o @BotFather e informe o token e o seu chat id.
- **Webhook:** URL do Discord, Slack, n8n, Zapier etc.

Use "Enviar notificação de teste" em *Configurações* para conferir.

### Cupons — como a validade é tratada

Os cupons são coletados de sites agregadores (Cuponomia, Méliuz, Pelando — editáveis em
*Configurações*) e da própria página do produto. A ferramenta:

- descarta cupons com **data de validade vencida**;
- marca cupons que **sumiram das fontes há 7+ dias**;
- guarda votos **✓ Funcionou / ✗ Não funcionou** — cupons com mais falhas que acertos aparecem como
  "Provavelmente inválido" e os que funcionaram sobem para o topo.

Nenhum site permite confirmar que um cupom funciona sem passar pelo checkout, então teste antes de
finalizar a compra e vote — isso mantém a lista confiável.

## Colocar na internet

Defina uma senha antes de expor o app:

```bash
APP_PASSWORD=uma-senha-forte PORT=3000 node server.js
```

Com Docker:

```bash
docker build -t monitor-precos .
docker run -d --name monitor-precos -p 3000:3000 \
  -e APP_PASSWORD=uma-senha-forte -v $(pwd)/data:/app/data monitor-precos
```

Funciona em qualquer VPS, Railway, Render, Fly.io etc. (use um volume persistente para `data/`).
Coloque atrás de HTTPS (Caddy, Nginx ou o proxy da própria plataforma).

### Variáveis de ambiente

| Variável | Uso |
|---|---|
| `PORT` / `HOST` | porta e interface (padrão `3000` / `0.0.0.0`) |
| `APP_PASSWORD` | ativa login (usuário qualquer + esta senha) |
| `DATA_FILE` | caminho do banco JSON (padrão `data/db.json`) |
| `NTFY_TOPIC`, `NTFY_SERVER` | notificações ntfy (sobrepõem as configurações da tela) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | notificações no Telegram |
| `WEBHOOK_URL` | webhook genérico/Discord |

## Limitações e dicas

- **Lojas que bloqueiam robôs** (principalmente a Amazon) às vezes respondem com captcha. O produto
  mostra o aviso; tente de novo mais tarde ou use **"Registrar preço manualmente"** no histórico.
- Se uma loja não for reconhecida, use em *Avançado* uma **regex do preço**, ex.: `"price":\s*([\d.]+)`.
- A leitura do preço usa, nesta ordem: regex personalizada → dados estruturados (JSON-LD) → meta
  tags → regras para Amazon / Mercado Livre / KaBuM! → texto "R$" da página (ignorando parcelas).
- O intervalo mínimo de verificação é 5 minutos; o padrão de 60 minutos evita bloqueios.

## Testes

```bash
npm test
```
