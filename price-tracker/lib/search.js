// Busca por nome em várias lojas ao mesmo tempo e devolve as ofertas da mais barata para a mais cara.
// As páginas de busca mudam com frequência: a extração tenta, nesta ordem, dados estruturados
// (JSON-LD), JSON embutido (Next.js etc.) e regras de HTML para Amazon e Mercado Livre.
import { parsePrice, decodeEntities, extractJsonLd } from "./price.js";
import { storeFromUrl } from "./coupons.js";

export function normalize(s) {
  return String(s ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ").trim();
}

// Apelidos comuns, para "ps5" casar com "PlayStation 5" e vice-versa.
const ALIASES = [
  [/\bplaystation ?(\d)\b/g, "ps$1"],
  [/\bps(\d)\b/g, "playstation $1"],
  [/\biphone ?(\d+)/g, "iphone$1"],
  [/\bxbox series ?([xs])\b/g, "xbox series$1"],
];

function searchableTitle(title) {
  const n = normalize(title);
  return ALIASES.reduce((acc, [re, rep]) => acc + " " + (n.match(re) ?? []).map((m) => m.replace(re, rep)).join(" "), n);
}

export function queryTokens(query) {
  return normalize(query).split(" ").filter((t) => t.length >= 2 || /\d/.test(t));
}

export function matchesQuery(title, tokens) {
  const words = ` ${searchableTitle(title)} `;
  // Cada termo precisa aparecer como início de palavra ("slim" casa "slim", "5" não casa "150").
  return tokens.every((t) => (/^\d+$/.test(t) ? words.includes(` ${t} `) : words.includes(` ${t}`)));
}

const ACCESSORY = /\b(capa|case|capinha|pelicula|skin|adesivo|suporte|base|dock|cabo|carregador|fonte|controle|joystick|dualsense|headset|fone|volante|bolsa|estojo|cooler|ventilador|grip|protetor|kit|jogo|game|midia|cartao|gift ?card|para|p|compativel|compat)\b/;
const USED = /\b(usado|usada|seminovo|seminova|recondicionado|recondicionada|vitrine|open ?box|reembalado|mostruario|com defeito|leia)\b/;

/** Classifica o anúncio: acessório (provável) e usado/recondicionado. */
export function classify(title, tokens) {
  const n = normalize(title);
  const accessoryHits = (n.match(new RegExp(ACCESSORY.source, "g")) ?? []).filter((w) => !tokens.includes(w));
  return {
    // "Console PS5 + jogo" é console; "Controle para PS5" é acessório.
    accessory: accessoryHits.length > 0 && !/\b(console|aparelho|notebook|smartphone|celular|televisao|smart tv)\b/.test(n),
    used: USED.test(n) && !tokens.some((t) => USED.test(t)),
  };
}

function absolutize(href, base) {
  if (!href || typeof href !== "string") return null;
  try { return new URL(decodeEntities(href), base).href; } catch { return null; }
}

function priceOf(v) {
  if (v == null) return null;
  if (typeof v === "object") return priceOf(v.value ?? v.amount ?? v.current ?? v.price ?? v.final ?? v.best);
  return parsePrice(v);
}

const PRICE_KEYS = ["priceWithDiscount", "pixPrice", "bestPrice", "salePrice", "finalPrice", "currentPrice", "price", "lowPrice", "minPrice", "preco", "valor"];
const TITLE_KEYS = ["name", "title", "productName", "nome", "titulo"];
const URL_KEYS = ["url", "link", "permalink", "href", "productUrl", "canonicalUrl", "path"];
const IMAGE_KEYS = ["image", "thumbnail", "imageUrl", "img", "picture", "photo"];

function* walk(node, depth = 0) {
  if (depth > 40 || !node || typeof node !== "object") return;
  if (Array.isArray(node)) { for (const n of node) yield* walk(n, depth + 1); return; }
  yield node;
  for (const v of Object.values(node)) if (v && typeof v === "object") yield* walk(v, depth + 1);
}

function itemFromObject(o, base) {
  const title = TITLE_KEYS.map((k) => o[k]).find((v) => typeof v === "string" && v.length >= 6 && v.length <= 300);
  if (!title) return null;
  let price = null;
  for (const k of PRICE_KEYS) if ((price = priceOf(o[k]))) break;
  if (!price && o.offers) price = priceOf([o.offers].flat()[0]);
  if (!price) return null;
  const href = URL_KEYS.map((k) => o[k]).find((v) => typeof v === "string" && /^(https?:\/\/|\/)/.test(v));
  let image = IMAGE_KEYS.map((k) => o[k]).find(Boolean);
  if (Array.isArray(image)) image = image[0];
  if (image && typeof image === "object") image = image.url ?? image.src;
  return { title: decodeEntities(title), price, url: absolutize(href, base), image: typeof image === "string" ? absolutize(image, base) : null };
}

function fromStructured(html, base) {
  const docs = [...extractJsonLd(html)];
  for (const m of html.matchAll(/<script[^>]*(?:id="__NEXT_DATA__"|type="application\/json")[^>]*>([\s\S]*?)<\/script>/gi)) {
    try { docs.push(JSON.parse(m[1])); } catch { /* ignora JSON inválido */ }
  }
  const items = [];
  for (const doc of docs) for (const o of walk(doc)) {
    const item = itemFromObject(o, base);
    if (item) items.push(item);
  }
  return items;
}

function stripTags(s) {
  return decodeEntities(s.replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}

const HTML_RULES = [
  {
    test: (host) => host.includes("amazon."),
    extract(html, base) {
      return html.split(/data-component-type="s-search-result"/).slice(1).map((chunk) => {
        const title = chunk.match(/<h2[^>]*>([\s\S]*?)<\/h2>/i)?.[1];
        const price = chunk.match(/class="a-price"[^>]*>\s*<span class="a-offscreen">([^<]+)</i)?.[1];
        const href = chunk.match(/<a[^>]*href="(\/[^"]*\/dp\/[^"]+)"/i)?.[1];
        const image = chunk.match(/<img[^>]*class="s-image"[^>]*src="([^"]+)"/i)?.[1];
        return title && price ? { title: stripTags(title), price: parsePrice(price), url: absolutize(href, base), image } : null;
      });
    },
  },
  {
    test: (host) => host.includes("mercadolivre.") || host.includes("mercadolibre."),
    extract(html, base) {
      return html.split(/class="(?:poly-card|ui-search-result__wrapper|andes-card ui-search-result)/).slice(1).map((chunk) => {
        const a = chunk.match(/<a[^>]*href="([^"]+)"[^>]*class="[^"]*(?:poly-component__title|ui-search-link|ui-search-item__group__element)[^"]*"[^>]*>([\s\S]*?)<\/a>/i)
          ?? chunk.match(/<a[^>]*class="[^"]*(?:poly-component__title|ui-search-link)[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/i);
        const title = a?.[2] ?? chunk.match(/class="[^"]*(?:poly-component__title|ui-search-item__title)[^"]*"[^>]*>([\s\S]*?)<\//i)?.[1];
        // Remove o preço riscado (<s>…</s>) antes de pegar o preço atual.
        const clean = chunk.replace(/<s\b[\s\S]*?<\/s>/gi, "");
        const frac = clean.match(/andes-money-amount__fraction[^>]*>([\d.]+)</i)?.[1];
        const cents = clean.match(/andes-money-amount__fraction[^>]*>[\d.]+<\/span>\s*(?:<[^>]+>\s*)*?<span[^>]*andes-money-amount__cents[^>]*>(\d{2})</i)?.[1];
        const image = chunk.match(/<img[^>]*(?:data-src|src)="(https:[^"]+)"/i)?.[1];
        return title && frac ? { title: stripTags(title), price: parsePrice(`${frac},${cents ?? "00"}`), url: absolutize(a?.[1], base), image } : null;
      });
    },
  },
];

/** Extrai a lista de anúncios de uma página de busca. */
export function extractListings(html, base) {
  let host = "";
  try { host = new URL(base).hostname; } catch { /* base opcional */ }
  const items = [];
  for (const rule of HTML_RULES) if (rule.test(host)) items.push(...rule.extract(html, base).filter(Boolean));
  items.push(...fromStructured(html, base));
  const seen = new Set();
  return items.filter((i) => {
    if (!i.price || !i.title) return false;
    const key = normalize(i.title) + "|" + i.price;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function buildSearchUrl(template, query) {
  const dash = normalize(query).replace(/ /g, "-");
  return template.replaceAll("{q-dash}", encodeURIComponent(dash)).replaceAll("{q}", encodeURIComponent(query.trim()));
}

const median = (arr) => {
  const s = [...arr].sort((a, b) => a - b);
  return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null;
};

/**
 * Busca o produto em todas as fontes e devolve as ofertas ordenadas pelo preço.
 * Por padrão esconde acessórios, usados e preços muito abaixo do normal (geralmente anúncios errados).
 */
export async function searchProduct(query, { sources, fetchPage, minPrice, maxPrice, includeUsed = false, includeAccessories = false, timeoutMs = 20_000 }) {
  const tokens = queryTokens(query);
  if (!tokens.length) throw new Error("Digite o nome do produto");

  const report = await Promise.all(sources.map(async (tpl) => {
    const url = buildSearchUrl(tpl, query);
    const store = storeFromUrl(url);
    try {
      const html = await fetchPage(url, { timeoutMs });
      const items = extractListings(html, url).map((i) => ({ ...i, url: i.url ?? url, store: store.slug, storeName: store.name, searchUrl: url }));
      return { source: store.name, url, items };
    } catch (e) {
      return { source: store.name, url, items: [], error: e.name === "TimeoutError" ? "tempo esgotado" : e.message };
    }
  }));

  const all = report.flatMap((r) => r.items).filter((i) => matchesQuery(i.title, tokens))
    .map((i) => ({ ...i, ...classify(i.title, tokens) }));

  const main = all.filter((i) => (includeAccessories || !i.accessory) && (includeUsed || !i.used));
  // Preço muito abaixo da mediana costuma ser acessório, peça ou anúncio enganoso.
  const med = median(main.map((i) => i.price));
  const floor = minPrice ?? (med && main.length >= 4 ? med * 0.4 : 0);

  const results = [], hidden = [];
  for (const i of all) {
    let reason = null;
    if (!includeAccessories && i.accessory) reason = "acessório";
    else if (!includeUsed && i.used) reason = "usado/recondicionado";
    else if (i.price < floor) reason = minPrice ? "abaixo do preço mínimo" : "preço suspeito (muito abaixo da média)";
    else if (maxPrice && i.price > maxPrice) reason = "acima do preço máximo";
    (reason ? hidden : results).push(reason ? { ...i, reason } : i);
  }
  results.sort((a, b) => a.price - b.price);
  hidden.sort((a, b) => a.price - b.price);

  return {
    query,
    best: results[0] ?? null,
    median: med,
    results: results.slice(0, 60),
    hidden: hidden.slice(0, 60),
    sources: report.map(({ source, url, items, error }) => ({ source, url, count: items.length, error })),
    searchedAt: new Date().toISOString(),
  };
}
