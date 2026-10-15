// Busca de cupons: varre sites agregadores e a própria página do produto, descarta expirados
// e mantém votos "funcionou / não funcionou" para medir a validade real.
// Importante: nenhum site expõe se um cupom funciona de fato sem passar pelo checkout,
// por isso a validade é estimada (data de expiração + votos + quando foi visto pela última vez).
import { decodeEntities } from "./price.js";
import { newId } from "./db.js";

const STORES = {
  "amazon.com.br": ["amazon", "Amazon"],
  "mercadolivre.com.br": ["mercado-livre", "Mercado Livre"],
  "kabum.com.br": ["kabum", "KaBuM!"],
  "magazineluiza.com.br": ["magazine-luiza", "Magalu"],
  "magalu.com": ["magazine-luiza", "Magalu"],
  "casasbahia.com.br": ["casas-bahia", "Casas Bahia"],
  "pontofrio.com.br": ["ponto", "Ponto"],
  "extra.com.br": ["extra", "Extra"],
  "americanas.com.br": ["americanas", "Americanas"],
  "submarino.com.br": ["submarino", "Submarino"],
  "carrefour.com.br": ["carrefour", "Carrefour"],
  "fastshop.com.br": ["fast-shop", "Fast Shop"],
  "shopee.com.br": ["shopee", "Shopee"],
  "aliexpress.com": ["aliexpress", "AliExpress"],
  "playstation.com": ["playstation-store", "PlayStation Store"],
  "girafa.com.br": ["girafa", "Girafa"],
  "pichau.com.br": ["pichau", "Pichau"],
  "terabyteshop.com.br": ["terabyte", "Terabyte"],
};

/** "https://www.kabum.com.br/produto/123" -> { slug: "kabum", name: "KaBuM!", domain: "kabum.com.br" } */
export function storeFromUrl(url) {
  let host;
  try { host = new URL(url).hostname.toLowerCase().replace(/^www\./, ""); } catch { return null; }
  for (const [domain, [slug, name]] of Object.entries(STORES)) {
    if (host === domain || host.endsWith(`.${domain}`)) return { slug, name, domain };
  }
  const base = host.split(".").find((p) => p.length > 2 && !["www", "loja", "shop", "store"].includes(p)) ?? host;
  return { slug: base, name: base.charAt(0).toUpperCase() + base.slice(1), domain: host };
}

const STOPWORDS = new Set(["COPIAR", "CUPOM", "COUPON", "CODIGO", "CODE", "NULL", "TRUE", "FALSE", "UNDEFINED",
  "ATIVAR", "VERCUPOM", "PEGAR", "FRETE", "GRATIS", "DESCONTO", "OFERTA", "PROMO", "CLIQUE", "AQUI", "HTTPS", "HTTP"]);

export function isPlausibleCode(code) {
  if (!code) return false;
  const c = code.trim().toUpperCase();
  return /^[A-Z0-9][A-Z0-9_-]{3,24}$/.test(c) && /[A-Z]/.test(c) && !STOPWORDS.has(c) && !/^[A-F0-9]{16,}$/.test(c);
}

const DATE_PATTERNS = [
  /(?:expira|v[aá]lid[oa] at[eé]|validade|termina|vence)[^0-9<]{0,20}(\d{1,2})\/(\d{1,2})\/(\d{2,4})/gi,
  /"(?:expiresAt|expirationDate|endDate|validUntil|validThrough|expires_at|end_date)"\s*:\s*"(\d{4}-\d{2}-\d{2}[^"]*)"/gi,
];

/** Primeira data de validade encontrada no trecho. */
export function findExpiry(text) {
  let best = null;
  for (const re of DATE_PATTERNS) {
    for (const m of text.matchAll(re)) {
      let d;
      if (m.length === 2) d = new Date(m[1]);
      else {
        const year = m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3]);
        d = new Date(Date.UTC(year, Number(m[2]) - 1, Number(m[1]), 23, 59, 59));
      }
      if (!isNaN(d) && (!best || m.index < best.index)) best = { index: m.index, iso: d.toISOString() };
    }
  }
  return best?.iso ?? null;
}

const CODE_PATTERNS = [
  /"(?:code|couponCode|coupon_code|voucherCode|promoCode)"\s*:\s*"([^"]{4,25})"/g,
  /data-(?:code|coupon|coupon-code|clipboard-text|promo-code|voucher)\s*=\s*["']([^"']{4,25})["']/gi,
  /(?:[Cc]upom|[Cc][oó]digo|[Cc]oupon)[:\s]+<?(?:[^>]*>)?\s*([A-Z0-9][A-Z0-9_-]{3,24})\b/g,
];

function cleanText(s) {
  return decodeEntities(s.replace(/<[^>]+>/g, " ").replace(/\\u([0-9a-f]{4})/gi, (_, h) => String.fromCharCode(parseInt(h, 16))))
    .replace(/\s+/g, " ").trim();
}

const OFFER_RE = /(\d{1,2}\s?%\s*(?:off|de desconto)?[^.|<{}"]{0,60})|(R\$\s*\d[\d.,]*\s*(?:off|de desconto)[^.|<{}"]{0,60})|(frete gr[aá]tis[^.|<{}"]{0,60})/i;

function plain(html) {
  return cleanText(html.replace(/^[^<]*>/, "").replace(/<[^>]*$/, "").replace(/[{}"]|\b\w+(?=\s*:)/g, " "))
    .replace(/\b(copiar|ver cupom|pegar cupom)\b/gi, "").replace(/\s+/g, " ").trim();
}

/** Descrição do cupom: a frase de oferta mais próxima do código (antes ou depois dele). */
function describe(before, after) {
  const prev = [...before.matchAll(new RegExp(OFFER_RE.source, "gi"))].at(-1);
  const next = after.match(OFFER_RE);
  const distPrev = prev ? before.length - (prev.index + prev[0].length) : Infinity;
  const distNext = next ? next.index : Infinity;
  if (prev || next) return plain(distNext < distPrev ? next[0] : prev[0]).slice(0, 140);
  return (plain(before).slice(-100) || plain(after).slice(0, 100)).trim();
}

/** Extrai cupons de um HTML qualquer. */
export function parseCoupons(html, { source = "", now = Date.now() } = {}) {
  // 1) Localiza todos os códigos; 2) cada cupom "possui" o trecho entre o código anterior e o próximo.
  const hits = [];
  for (const re of CODE_PATTERNS) {
    for (const m of html.matchAll(re)) {
      const code = m[1].trim().toUpperCase();
      if (isPlausibleCode(code)) hits.push({ code, index: m.index, end: m.index + m[0].length });
    }
  }
  hits.sort((x, y) => x.index - y.index);
  const found = new Map();
  hits.forEach((h, i) => {
    if (found.has(h.code)) return;
    const prevEnd = i > 0 ? hits[i - 1].end : 0;
    const nextStart = i + 1 < hits.length ? hits[i + 1].index : html.length;
    const before = html.slice(Math.max(prevEnd, h.index - 400), h.index);
    const after = html.slice(h.end, Math.min(nextStart, h.end + 400));
    // A validade costuma vir depois do código (antes dele, pertence ao cupom anterior).
    const expiresAt = findExpiry(after);
    if (expiresAt && Date.parse(expiresAt) < now) return; // expirado
    found.set(h.code, { code: h.code, description: describe(before, after), expiresAt, source });
  });
  return [...found.values()];
}

/** Mescla cupons encontrados no banco, preservando votos e datas. */
export function mergeCoupons(store, storeInfo, found) {
  const now = new Date().toISOString();
  let added = 0;
  for (const c of found) {
    const existing = store.coupons.find((x) => x.store === storeInfo.slug && x.code === c.code);
    if (existing) {
      existing.lastSeenAt = now;
      existing.expiresAt = c.expiresAt ?? existing.expiresAt;
      if (!existing.description && c.description) existing.description = c.description;
    } else {
      store.coupons.push({
        id: newId(), store: storeInfo.slug, storeName: storeInfo.name, code: c.code,
        description: c.description, expiresAt: c.expiresAt, source: c.source,
        foundAt: now, lastSeenAt: now, worked: 0, failed: 0, manual: false,
      });
      added++;
    }
  }
  store.save();
  return added;
}

/** Status calculado de um cupom. */
export function couponStatus(c, now = Date.now()) {
  if (c.expiresAt && Date.parse(c.expiresAt) < now) return { level: "bad", label: "Expirado" };
  if (c.failed >= 2 && c.failed > c.worked) return { level: "bad", label: "Provavelmente inválido" };
  if (c.worked > c.failed) return { level: "good", label: `Funcionou (${c.worked}✓ / ${c.failed}✗)` };
  const stale = !c.manual && now - Date.parse(c.lastSeenAt) > 7 * 86_400_000;
  if (stale) return { level: "warn", label: "Não aparece há 7+ dias" };
  return { level: "neutral", label: c.expiresAt ? "Válido (pela data)" : "Não verificado" };
}

/** Busca cupons em todas as fontes configuradas (+ página do produto, se informada). */
export async function searchCoupons(store, storeInfo, { fetchPage, productHtml } = {}) {
  const report = [];
  const found = [];
  if (productHtml) {
    const onPage = parseCoupons(productHtml, { source: "página do produto" });
    found.push(...onPage);
    report.push({ source: "página do produto", count: onPage.length });
  }
  for (const tpl of store.settings.couponSources) {
    const url = tpl.replaceAll("{slug}", storeInfo.slug).replaceAll("{domain}", storeInfo.domain);
    try {
      const html = await fetchPage(url);
      const list = parseCoupons(html, { source: new URL(url).hostname.replace(/^www\./, "") });
      found.push(...list);
      report.push({ source: url, count: list.length });
    } catch (e) {
      report.push({ source: url, error: e.message });
    }
  }
  const added = mergeCoupons(store, storeInfo, found);
  return { added, total: found.length, report };
}
