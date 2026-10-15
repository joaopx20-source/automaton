// Canais de notificação: navegador (SSE), ntfy (push no celular), Telegram e webhook (Discord/Slack/genérico).

export function createNotifier(store, { fetchImpl = fetch } = {}) {
  const clients = new Set();

  const cfg = () => {
    const s = store.settings;
    return {
      ntfyServer: process.env.NTFY_SERVER || s.ntfyServer || "https://ntfy.sh",
      ntfyTopic: process.env.NTFY_TOPIC || s.ntfyTopic,
      telegramBotToken: process.env.TELEGRAM_BOT_TOKEN || s.telegramBotToken,
      telegramChatId: process.env.TELEGRAM_CHAT_ID || s.telegramChatId,
      webhookUrl: process.env.WEBHOOK_URL || s.webhookUrl,
    };
  };

  function broadcast(event, data) {
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const res of clients) res.write(payload);
  }

  async function send({ title, message, url, productId, kind = "info" }) {
    const c = cfg();
    const results = { browser: clients.size };
    const jobs = [];
    if (c.ntfyTopic) {
      jobs.push(["ntfy", fetchImpl(`${c.ntfyServer.replace(/\/$/, "")}/${encodeURIComponent(c.ntfyTopic)}`, {
        method: "POST",
        body: message,
        // Cabeçalhos HTTP só aceitam latin1: o título vai sem acentos problemáticos via RFC 2047.
        headers: { Title: `=?UTF-8?B?${Buffer.from(title).toString("base64")}?=`, Tags: "moneybag", ...(url ? { Click: url } : {}) },
      })]);
    }
    if (c.telegramBotToken && c.telegramChatId) {
      jobs.push(["telegram", fetchImpl(`https://api.telegram.org/bot${c.telegramBotToken}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ chat_id: c.telegramChatId, text: `${title}\n${message}${url ? `\n${url}` : ""}` }),
      })]);
    }
    if (c.webhookUrl) {
      const text = `**${title}**\n${message}${url ? `\n${url}` : ""}`;
      jobs.push(["webhook", fetchImpl(c.webhookUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content: text, text, title, message, url }),
      })]);
    }
    for (const [name, p] of jobs) {
      try {
        const r = await p;
        results[name] = r.ok ? "ok" : `HTTP ${r.status}`;
      } catch (e) {
        results[name] = `erro: ${e.message}`;
      }
    }
    store.logNotification({ title, message, url, productId, kind, channels: results });
    broadcast("notification", { title, message, url, productId, kind });
    return results;
  }

  return { clients, broadcast, send };
}
