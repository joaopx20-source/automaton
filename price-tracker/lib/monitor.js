// Verificação periódica de preços e regras de alerta.
import { extractProduct } from "./price.js";
import { analyze } from "./stats.js";
import { storeFromUrl, searchCoupons } from "./coupons.js";
import { newId } from "./db.js";

const HOUR = 3_600_000;
export const brl = (n) => n == null ? "—" : n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export function createProduct(store, { url, name, targetPrice, dropPercent, customRegex }) {
  const parsed = new URL(url); // lança se inválida
  if (!/^https?:$/.test(parsed.protocol)) throw new Error("URL precisa começar com http(s)://");
  const info = storeFromUrl(url);
  const p = {
    id: newId(), url, name: name || null, image: null,
    store: info.slug, storeName: info.name,
    targetPrice: targetPrice ? Number(targetPrice) : null,
    dropPercent: dropPercent === "" || dropPercent == null ? null : Number(dropPercent),
    customRegex: customRegex || null,
    active: true, createdAt: new Date().toISOString(),
    currentPrice: null, available: null, lastCheckedAt: null, lastError: null, history: [],
  };
  store.products.push(p);
  store.save();
  return p;
}

/** Registra um preço e devolve os eventos de alerta disparados. */
export function recordPrice(store, p, { price, available = null, source = "manual" }, now = new Date()) {
  const prev = p.currentPrice;
  const prevAvailable = p.available;
  const prevMin = p.history.length ? Math.min(...p.history.map((h) => h.price)) : null;
  const last = p.history.at(-1);

  // Só grava novo ponto quando muda, ou a cada 12h para o gráfico ficar contínuo.
  if (!last || last.price !== price || now - Date.parse(last.t) > 12 * HOUR || last.available !== available) {
    p.history.push({ t: now.toISOString(), price, available, source });
  }
  p.currentPrice = price;
  p.available = available;
  p.lastCheckedAt = now.toISOString();
  p.lastError = null;

  const events = [];
  const name = p.name || "Produto";
  const dropPct = prev ? ((prev - price) / prev) * 100 : 0;
  const threshold = p.dropPercent ?? store.settings.defaultDropPercent ?? 0;

  if (p.targetPrice && price <= p.targetPrice && (prev == null || prev > p.targetPrice || price < prev)) {
    events.push({ kind: "target", title: `🎯 Preço-alvo atingido: ${name}`,
      message: `Agora ${brl(price)} (alvo ${brl(p.targetPrice)})${prev ? ` — antes ${brl(prev)}` : ""} em ${p.storeName}.` });
  } else if (prev && price < prev && dropPct >= threshold) {
    events.push({ kind: "drop", title: `📉 Preço caiu ${dropPct.toFixed(1)}%: ${name}`,
      message: `${brl(prev)} → ${brl(price)} em ${p.storeName}.` });
  }
  if (prevMin != null && price < prevMin && p.history.length > 2 && !events.length) {
    events.push({ kind: "low", title: `🏆 Menor preço histórico: ${name}`, message: `${brl(price)} em ${p.storeName} (anterior ${brl(prevMin)}).` });
  }
  if (prevAvailable === false && available === true) {
    events.push({ kind: "stock", title: `✅ Voltou ao estoque: ${name}`, message: `${brl(price)} em ${p.storeName}.` });
  }
  store.save();
  return events;
}

export function createMonitor({ store, notifier, fetchPage }) {
  const running = new Set();
  const lastHtml = new Map(); // HTML da última consulta, para achar cupons na página (não persistido)
  let priceTimer, couponTimer;

  async function check(p, { notify = true } = {}) {
    if (running.has(p.id)) return p;
    running.add(p.id);
    try {
      const html = await fetchPage(p.url);
      const data = extractProduct(html, p.url, { customRegex: p.customRegex });
      if (!p.name && data.title) p.name = data.title.slice(0, 140);
      if (!p.image && data.image) p.image = data.image;
      if (!data.price) throw new Error("Não encontrei o preço na página. Informe uma regex personalizada ou registre manualmente.");
      const events = recordPrice(store, p, { price: data.price, available: data.available, source: data.source });
      if (notify) for (const e of events) await notifier.send({ ...e, url: p.url, productId: p.id });
      lastHtml.set(p.id, html);
    } catch (e) {
      p.lastError = e.name === "TimeoutError" ? "Tempo esgotado ao acessar a loja" : e.message;
      p.lastCheckedAt = new Date().toISOString();
      store.save();
    } finally {
      running.delete(p.id);
      notifier.broadcast("product", serialize(p));
    }
    return p;
  }

  async function checkAll() {
    const list = store.products.filter((p) => p.active);
    // Concorrência 2 + pausa curta para não sobrecarregar as lojas.
    for (let i = 0; i < list.length; i += 2) {
      await Promise.all(list.slice(i, i + 2).map((p) => check(p)));
      await new Promise((r) => setTimeout(r, 1500 + Math.random() * 1500));
    }
  }

  async function refreshCoupons() {
    const seen = new Map();
    for (const p of store.products.filter((x) => x.active)) {
      if (!seen.has(p.store)) seen.set(p.store, p);
    }
    for (const p of seen.values()) {
      const before = store.coupons.filter((c) => c.store === p.store).length;
      await searchCoupons(store, storeFromUrl(p.url), { fetchPage, productHtml: lastHtml.get(p.id) });
      const added = store.coupons.filter((c) => c.store === p.store).length - before;
      if (added > 0) {
        await notifier.send({ kind: "coupon", title: `🎟️ ${added} cupom(ns) novo(s) para ${p.storeName}`,
          message: `Veja na aba Cupons antes de comprar ${p.name ?? "seu produto"}.`, productId: p.id });
      }
    }
  }

  function start() {
    stop();
    const minutes = Math.max(5, Number(store.settings.checkIntervalMinutes) || 60);
    const hours = Math.max(1, Number(store.settings.couponIntervalHours) || 6);
    priceTimer = setInterval(() => checkAll().catch(console.error), minutes * 60_000);
    couponTimer = setInterval(() => refreshCoupons().catch(console.error), hours * HOUR);
    setTimeout(() => checkAll().then(refreshCoupons).catch(console.error), 3000);
  }

  function stop() { clearInterval(priceTimer); clearInterval(couponTimer); }

  return { check, checkAll, refreshCoupons, start, stop, lastHtml };
}

export function serialize(p) {
  return { ...p, stats: analyze(p.history) };
}
