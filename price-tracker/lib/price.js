// Extração de preço/título/imagem de páginas de produto (sem dependências).
// Ordem de confiança: regex do usuário > JSON-LD > meta tags > regras por loja > heurística "R$".

const MAX_PRICE = 10_000_000;

/** Converte "R$ 3.799,90", "3799.90", "3,799.90", 3799.9 em número. */
export function parsePrice(input) {
  if (typeof input === "number") return Number.isFinite(input) && input > 0 ? round2(input) : null;
  if (input == null) return null;
  let s = String(input).replace(/\s|&nbsp;| /g, "").replace(/[^\d.,]/g, "");
  if (!s || !/\d/.test(s)) return null;
  const lastComma = s.lastIndexOf(",");
  const lastDot = s.lastIndexOf(".");
  if (lastComma >= 0 && lastDot >= 0) {
    // O último separador é o decimal.
    if (lastComma > lastDot) s = s.replace(/\./g, "").replace(",", ".");
    else s = s.replace(/,/g, "");
  } else if (lastComma >= 0) {
    const decimals = s.length - lastComma - 1;
    // "3799,9" / "3799,90" -> decimal; "3,799" / "1,299,000" -> milhar.
    s = decimals <= 2 && s.split(",").length === 2 ? s.replace(",", ".") : s.replace(/,/g, "");
  } else if (lastDot >= 0) {
    const decimals = s.length - lastDot - 1;
    const groups = s.split(".");
    // "3.799" e "1.299.000" são milhares no padrão brasileiro; "3799.9" é decimal.
    if (decimals === 3 && groups.slice(1).every((g) => g.length === 3)) s = s.replace(/\./g, "");
    else if (groups.length > 2) s = groups.slice(0, -1).join("") + "." + groups.at(-1);
  }
  const n = Number(s);
  return Number.isFinite(n) && n > 0 && n < MAX_PRICE ? round2(n) : null;
}

const round2 = (n) => Math.round(n * 100) / 100;

export function decodeEntities(s) {
  return String(s ?? "")
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&")
    .trim();
}

export function parseAttrs(tag) {
  const attrs = {};
  const re = /([\w:-]+)\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))/g;
  let m;
  while ((m = re.exec(tag))) attrs[m[1].toLowerCase()] = decodeEntities(m[3] ?? m[4] ?? m[5] ?? "");
  return attrs;
}

/** Retorna o content da primeira <meta> cujo property/name/itemprop é um dos nomes. */
export function getMeta(html, names) {
  const wanted = names.map((n) => n.toLowerCase());
  for (const m of html.matchAll(/<meta\b[^>]*>/gi)) {
    const a = parseAttrs(m[0]);
    const key = (a.property || a.name || a.itemprop || "").toLowerCase();
    if (wanted.includes(key) && a.content) return a.content;
  }
  return null;
}

function* walkJson(node) {
  if (Array.isArray(node)) for (const n of node) yield* walkJson(n);
  else if (node && typeof node === "object") {
    yield node;
    for (const v of Object.values(node)) if (v && typeof v === "object") yield* walkJson(v);
  }
}

const hasType = (node, type) => {
  const t = node["@type"];
  return Array.isArray(t) ? t.includes(type) : t === type;
};

export function extractJsonLd(html) {
  const out = [];
  for (const m of html.matchAll(/<script[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    try { out.push(JSON.parse(m[1].trim())); } catch { /* JSON-LD inválido: ignora */ }
  }
  return out;
}

function priceFromOffer(offer) {
  if (!offer || typeof offer !== "object") return null;
  const candidates = [offer.price, offer.lowPrice, offer.priceSpecification?.price,
    ...(Array.isArray(offer.priceSpecification) ? offer.priceSpecification.map((p) => p.price) : [])];
  for (const c of candidates) {
    const p = parsePrice(c);
    if (p) return p;
  }
  return null;
}

function availabilityOf(value) {
  if (!value) return null;
  const v = String(value).toLowerCase();
  if (/outofstock|soldout|discontinued/.test(v)) return false;
  if (/instock|preorder|limitedavailability|onlineonly/.test(v)) return true;
  return null;
}

function fromJsonLd(html) {
  for (const doc of extractJsonLd(html)) {
    for (const node of walkJson(doc)) {
      if (!hasType(node, "Product") && !hasType(node, "ProductGroup")) continue;
      const offers = [node.offers].flat().filter(Boolean)
        .flatMap((o) => (hasType(o, "AggregateOffer") && o.offers ? [o, ...[o.offers].flat()] : [o]));
      let best = null;
      for (const o of offers) {
        const price = priceFromOffer(o);
        if (!price) continue;
        const available = availabilityOf(o.availability);
        // Prefere ofertas disponíveis; entre elas, a mais barata.
        const better = !best || (available !== false && best.available === false) ||
          ((available !== false) === (best.available !== false) && price < best.price);
        if (better) best = { price, available };
      }
      if (best) {
        const image = Array.isArray(node.image) ? node.image[0] : node.image?.url ?? node.image;
        return { ...best, title: node.name ? decodeEntities(node.name) : null, image: typeof image === "string" ? image : null };
      }
    }
  }
  return null;
}

// Regras específicas para lojas populares no Brasil (o HTML muda com frequência — são "melhor esforço").
const SITE_RULES = [
  {
    name: "amazon",
    test: (host) => host.includes("amazon."),
    extract(html) {
      const block = html.match(/id="(?:corePrice_feature_div|corePriceDisplay_desktop_feature_div|apex_desktop)"[\s\S]{0,4000}/i)?.[0] ?? html;
      const m = block.match(/class="a-offscreen"[^>]*>\s*([^<]+)</i);
      if (m) return parsePrice(m[1]);
      const whole = block.match(/class="a-price-whole"[^>]*>([\d.]+)/i);
      const frac = block.match(/class="a-price-fraction"[^>]*>(\d{2})/i);
      return whole ? parsePrice(`${whole[1]},${frac?.[1] ?? "00"}`) : null;
    },
  },
  {
    name: "mercadolivre",
    test: (host) => host.includes("mercadolivre.") || host.includes("mercadolibre."),
    extract(html) {
      const meta = html.match(/<meta[^>]*itemprop="price"[^>]*content="([\d.]+)"/i);
      if (meta) return parsePrice(Number(meta[1]));
      const m = html.match(/ui-pdp-price__second-line[\s\S]{0,600}?andes-money-amount__fraction[^>]*>([\d.]+)<\/span>(?:[\s\S]{0,200}?andes-money-amount__cents[^>]*>(\d{2})<)?/i);
      return m ? parsePrice(`${m[1]},${m[2] ?? "00"}`) : null;
    },
  },
  {
    name: "kabum",
    test: (host) => host.includes("kabum."),
    extract(html) {
      const m = html.match(/"priceWithDiscount"\s*:\s*([\d.]+)/) ?? html.match(/"price"\s*:\s*([\d.]+)/);
      return m ? parsePrice(Number(m[1])) : null;
    },
  },
];

const INSTALLMENT_BEFORE = /(\d+\s*x\s*(de)?\s*|parcela[s]?\s*(de)?\s*|em at[eé]\s*)$/i;

function fromHeuristic(html) {
  const text = html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ").replace(/&nbsp;| /g, " ").replace(/\s+/g, " ");
  for (const m of text.matchAll(/R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)/g)) {
    const before = text.slice(Math.max(0, m.index - 25), m.index);
    if (INSTALLMENT_BEFORE.test(before.trimEnd() + " ") || INSTALLMENT_BEFORE.test(before)) continue;
    const p = parsePrice(m[1]);
    if (p && p >= 1) return p;
  }
  return null;
}

/**
 * Extrai dados do produto de um HTML.
 * @returns {{price:number|null,title:string|null,image:string|null,available:boolean|null,source:string|null}}
 */
export function extractProduct(html, url = "", { customRegex } = {}) {
  let host = "";
  try { host = new URL(url).hostname.toLowerCase(); } catch { /* url opcional */ }

  const ld = fromJsonLd(html);
  const title = ld?.title || getMeta(html, ["og:title", "twitter:title"]) ||
    decodeEntities(html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? "") || null;
  const image = ld?.image || getMeta(html, ["og:image", "twitter:image"]) || null;
  const availMeta = availabilityOf(getMeta(html, ["product:availability", "og:availability", "availability"]));
  let available = ld?.available ?? availMeta;
  if (available == null && /esgotado|indispon[ií]vel|sem estoque|currently unavailable/i.test(html.slice(0, 400_000))) {
    // Sinal fraco: só usamos se nenhum dado estruturado disse o contrário.
    available = /avise-me|produto esgotado|"availability"\s*:\s*"[^"]*outofstock/i.test(html) ? false : null;
  }

  const result = (price, source) => ({ price, title, image, available, source });

  if (customRegex) {
    try {
      const m = html.match(new RegExp(customRegex, "i"));
      const p = parsePrice(m?.[1] ?? m?.[0]);
      if (p) return result(p, "regex");
    } catch { /* regex inválida: segue para as outras fontes */ }
  }
  if (ld?.price) return result(ld.price, "json-ld");

  const meta = parsePrice(getMeta(html, ["product:price:amount", "og:price:amount", "price", "twitter:data1"]));
  if (meta) return result(meta, "meta");

  for (const rule of SITE_RULES) {
    if (!rule.test(host)) continue;
    const p = rule.extract(html);
    if (p) return result(p, rule.name);
  }

  const h = fromHeuristic(html);
  return result(h, h ? "heuristica" : null);
}
