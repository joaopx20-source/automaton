#!/usr/bin/env node
// Monitor de Preços — servidor web sem dependências externas.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { Store, DEFAULT_SETTINGS, newId } from "./lib/db.js";
import { fetchPage } from "./lib/fetcher.js";
import { createNotifier } from "./lib/notify.js";
import { createMonitor, createProduct, recordPrice, serialize } from "./lib/monitor.js";
import { storeFromUrl, searchCoupons, couponStatus, isPlausibleCode } from "./lib/coupons.js";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(ROOT, "public");
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json" };

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export function createApp({ store, fetchPageImpl = fetchPage, password = process.env.APP_PASSWORD } = {}) {
  const notifier = createNotifier(store);
  const monitor = createMonitor({ store, notifier, fetchPage: fetchPageImpl });

  const routes = [];
  const route = (method, pattern, handler) => {
    const keys = [];
    const re = new RegExp("^" + pattern.replace(/:(\w+)/g, (_, k) => (keys.push(k), "([^/]+)")) + "$");
    routes.push({ method, re, keys, handler });
  };

  const findProduct = (id) => {
    const p = store.product(id);
    if (!p) throw new HttpError(404, "Produto não encontrado");
    return p;
  };
  const toNumber = (v, field) => {
    if (v === "" || v == null) return null;
    const n = Number(String(v).replace(",", "."));
    if (!Number.isFinite(n) || n < 0) throw new HttpError(400, `Valor inválido em ${field}`);
    return n;
  };

  // ---- Produtos
  route("GET", "/api/products", () => store.products.map(serialize));
  route("POST", "/api/products", async ({ body }) => {
    if (!body.url) throw new HttpError(400, "Informe a URL do produto");
    let p;
    try {
      p = createProduct(store, { ...body, targetPrice: toNumber(body.targetPrice, "preço-alvo"), dropPercent: toNumber(body.dropPercent, "queda %") });
    } catch (e) {
      throw e instanceof HttpError ? e : new HttpError(400, "URL inválida");
    }
    await monitor.check(p, { notify: false });
    return serialize(p);
  });
  route("GET", "/api/products/:id", ({ params }) => serialize(findProduct(params.id)));
  route("PATCH", "/api/products/:id", ({ params, body }) => {
    const p = findProduct(params.id);
    if ("name" in body) p.name = String(body.name).slice(0, 200) || p.name;
    if ("targetPrice" in body) p.targetPrice = toNumber(body.targetPrice, "preço-alvo");
    if ("dropPercent" in body) p.dropPercent = toNumber(body.dropPercent, "queda %");
    if ("customRegex" in body) p.customRegex = body.customRegex || null;
    if ("active" in body) p.active = Boolean(body.active);
    store.save();
    return serialize(p);
  });
  route("DELETE", "/api/products/:id", ({ params }) => {
    const p = findProduct(params.id);
    store.data.products = store.products.filter((x) => x !== p);
    store.save();
    return { ok: true };
  });
  route("POST", "/api/products/:id/check", async ({ params }) => serialize(await monitor.check(findProduct(params.id))));
  route("POST", "/api/products/:id/prices", async ({ params, body }) => {
    const p = findProduct(params.id);
    const price = toNumber(body.price, "preço");
    if (!price) throw new HttpError(400, "Informe o preço");
    const events = recordPrice(store, p, { price, available: true, source: "manual" });
    for (const e of events) await notifier.send({ ...e, url: p.url, productId: p.id });
    return serialize(p);
  });
  route("POST", "/api/check-all", () => {
    monitor.checkAll().catch(console.error);
    return { started: true };
  });

  // ---- Cupons
  route("GET", "/api/coupons", ({ query }) => {
    const storeSlug = query.get("store");
    const showExpired = query.get("expired") === "1";
    return store.coupons
      .filter((c) => !storeSlug || c.store === storeSlug)
      .map((c) => ({ ...c, status: couponStatus(c) }))
      .filter((c) => showExpired || c.status.label !== "Expirado")
      .sort((a, b) => (b.worked - b.failed) - (a.worked - a.failed) || Date.parse(b.lastSeenAt) - Date.parse(a.lastSeenAt));
  });
  route("POST", "/api/coupons/search", async ({ body }) => {
    let info;
    if (body.productId) info = storeFromUrl(findProduct(body.productId).url);
    else if (body.url) info = storeFromUrl(body.url);
    else if (body.store) info = { slug: String(body.store).toLowerCase().trim().replace(/\s+/g, "-"), name: body.store, domain: "" };
    if (!info) throw new HttpError(400, "Informe uma loja ou URL");
    const productHtml = body.productId ? monitor.lastHtml.get(body.productId) : undefined;
    return { store: info, ...(await searchCoupons(store, info, { fetchPage: fetchPageImpl, productHtml })) };
  });
  route("POST", "/api/coupons", ({ body }) => {
    const code = String(body.code ?? "").trim().toUpperCase();
    if (!code || code.length > 40) throw new HttpError(400, "Código inválido");
    const info = body.url ? storeFromUrl(body.url) : { slug: String(body.store ?? "").toLowerCase().trim().replace(/\s+/g, "-"), name: body.store };
    if (!info?.slug) throw new HttpError(400, "Informe a loja");
    const now = new Date().toISOString();
    const c = { id: newId(), store: info.slug, storeName: info.name || info.slug, code, description: String(body.description ?? "").slice(0, 300),
      expiresAt: body.expiresAt ? new Date(body.expiresAt + "T23:59:59").toISOString() : null, source: "manual",
      foundAt: now, lastSeenAt: now, worked: 0, failed: 0, manual: true, plausible: isPlausibleCode(code) };
    store.coupons.push(c);
    store.save();
    return { ...c, status: couponStatus(c) };
  });
  route("POST", "/api/coupons/:id/vote", ({ params, body }) => {
    const c = store.coupons.find((x) => x.id === params.id);
    if (!c) throw new HttpError(404, "Cupom não encontrado");
    if (body.worked) c.worked++; else c.failed++;
    c.lastVoteAt = new Date().toISOString();
    store.save();
    return { ...c, status: couponStatus(c) };
  });
  route("DELETE", "/api/coupons/:id", ({ params }) => {
    store.data.coupons = store.coupons.filter((c) => c.id !== params.id);
    store.save();
    return { ok: true };
  });

  // ---- Configurações e notificações
  const SECRET_KEYS = ["telegramBotToken"];
  route("GET", "/api/settings", () => {
    const s = { ...store.settings };
    for (const k of SECRET_KEYS) if (s[k]) s[k] = "••••" + s[k].slice(-4);
    return s;
  });
  route("PUT", "/api/settings", ({ body }) => {
    for (const k of Object.keys(DEFAULT_SETTINGS)) {
      if (!(k in body)) continue;
      if (SECRET_KEYS.includes(k) && String(body[k]).startsWith("••••")) continue;
      if (k === "couponSources") {
        store.settings[k] = [body[k]].flat().map(String).map((s) => s.trim()).filter((s) => /^https?:\/\//.test(s));
      } else if (typeof DEFAULT_SETTINGS[k] === "number") {
        store.settings[k] = toNumber(body[k], k) ?? DEFAULT_SETTINGS[k];
      } else {
        store.settings[k] = String(body[k]).trim();
      }
    }
    store.save();
    monitor.start();
    return { ok: true };
  });
  route("POST", "/api/notify/test", () => notifier.send({ kind: "test", title: "🔔 Teste do Monitor de Preços", message: "Se você recebeu isto, as notificações estão funcionando." }));
  route("GET", "/api/notifications", () => store.notifications.slice(0, 100));

  async function readBody(req) {
    const chunks = [];
    let size = 0;
    for await (const c of req) {
      size += c.length;
      if (size > 1_000_000) throw new HttpError(413, "Corpo muito grande");
      chunks.push(c);
    }
    if (!chunks.length) return {};
    try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); } catch { throw new HttpError(400, "JSON inválido"); }
  }

  function authorized(req) {
    if (!password) return true;
    const [scheme, encoded] = (req.headers.authorization ?? "").split(" ");
    if (scheme !== "Basic" || !encoded) return false;
    const pass = Buffer.from(encoded, "base64").toString().split(":").slice(1).join(":");
    const a = crypto.createHash("sha256").update(pass).digest();
    const b = crypto.createHash("sha256").update(password).digest();
    return crypto.timingSafeEqual(a, b);
  }

  function serveStatic(res, pathname) {
    const file = path.normalize(path.join(PUBLIC, pathname === "/" ? "index.html" : pathname));
    if (!file.startsWith(PUBLIC) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404).end("Não encontrado");
      return;
    }
    res.writeHead(200, { "content-type": MIME[path.extname(file)] ?? "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  }

  const handler = async (req, res) => {
    res.setHeader("x-content-type-options", "nosniff");
    if (!authorized(req)) {
      res.writeHead(401, { "www-authenticate": 'Basic realm="Monitor de Precos"' }).end("Senha necessária");
      return;
    }
    const url = new URL(req.url, "http://local");
    if (url.pathname === "/api/events") {
      res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
      res.write("retry: 5000\n\n");
      notifier.clients.add(res);
      const ping = setInterval(() => res.write(": ping\n\n"), 25_000);
      req.on("close", () => { clearInterval(ping); notifier.clients.delete(res); });
      return;
    }
    if (!url.pathname.startsWith("/api/")) return serveStatic(res, url.pathname);

    try {
      for (const r of routes) {
        const m = r.method === req.method && url.pathname.match(r.re);
        if (!m) continue;
        const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
        const body = ["POST", "PUT", "PATCH"].includes(req.method) ? await readBody(req) : {};
        const out = await r.handler({ params, body, query: url.searchParams });
        res.writeHead(200, { "content-type": "application/json; charset=utf-8" }).end(JSON.stringify(out));
        return;
      }
      throw new HttpError(404, "Rota não encontrada");
    } catch (e) {
      if (!e.status) console.error(e);
      res.writeHead(e.status ?? 500, { "content-type": "application/json; charset=utf-8" })
        .end(JSON.stringify({ error: e.status ? e.message : "Erro interno" }));
    }
  };

  return { handler, monitor, notifier };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const store = new Store(process.env.DATA_FILE || path.join(ROOT, "data", "db.json"));
  const { handler, monitor } = createApp({ store });
  const port = Number(process.env.PORT) || 3000;
  const host = process.env.HOST || "0.0.0.0";
  http.createServer(handler).listen(port, host, () => {
    console.log(`Monitor de Preços rodando em http://localhost:${port}`);
    if (!process.env.APP_PASSWORD) console.log("Dica: defina APP_PASSWORD para proteger o acesso pela internet.");
  });
  monitor.start();
  const shutdown = () => { store.flush(); process.exit(0); };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}
