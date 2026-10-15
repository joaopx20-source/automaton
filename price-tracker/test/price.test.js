import { test } from "node:test";
import assert from "node:assert/strict";
import { parsePrice, extractProduct } from "../lib/price.js";
import { analyze } from "../lib/stats.js";
import { parseCoupons, storeFromUrl, couponStatus } from "../lib/coupons.js";

test("parsePrice entende formatos brasileiros e internacionais", () => {
  assert.equal(parsePrice("R$ 3.799,90"), 3799.9);
  assert.equal(parsePrice("R$&nbsp;4.299"), 4299);
  assert.equal(parsePrice("3799.90"), 3799.9);
  assert.equal(parsePrice("3,799.90"), 3799.9);
  assert.equal(parsePrice("3799,9"), 3799.9);
  assert.equal(parsePrice("1.299.000,00"), 1299000);
  assert.equal(parsePrice(3499), 3499);
  assert.equal(parsePrice("grátis"), null);
  assert.equal(parsePrice("0"), null);
});

test("extrai do JSON-LD preferindo a oferta disponível mais barata", () => {
  const html = `<html><head><title>x</title>
  <script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Product","name":"Console PlayStation&#174; 5 Slim",
    "image":["https://img/ps5.jpg"],"offers":[
      {"@type":"Offer","price":"3299.00","availability":"https://schema.org/OutOfStock"},
      {"@type":"Offer","price":"3599.90","availability":"https://schema.org/InStock"},
      {"@type":"Offer","price":"3499.90","availability":"https://schema.org/InStock"}]}]}</script></head></html>`;
  const r = extractProduct(html, "https://www.magazineluiza.com.br/ps5/p/1");
  assert.equal(r.price, 3499.9);
  assert.equal(r.available, true);
  assert.equal(r.source, "json-ld");
  assert.equal(r.title, "Console PlayStation® 5 Slim");
  assert.equal(r.image, "https://img/ps5.jpg");
});

test("usa meta tags quando não há JSON-LD", () => {
  const html = `<meta content="3.899,00" property="product:price:amount"><meta property="og:title" content="PS5 Pro">`;
  const r = extractProduct(html, "https://loja.exemplo.com/ps5");
  assert.equal(r.price, 3899);
  assert.equal(r.title, "PS5 Pro");
});

test("regra da Amazon", () => {
  const html = `<div id="corePrice_feature_div"><span class="a-price"><span class="a-offscreen">R$ 3.749,00</span></span></div>`;
  assert.equal(extractProduct(html, "https://www.amazon.com.br/dp/B0X").price, 3749);
});

test("regra do Mercado Livre", () => {
  const html = `<div class="ui-pdp-price__second-line"><span class="andes-money-amount__fraction">3.599</span><span class="andes-money-amount__cents">90</span></div>`;
  assert.equal(extractProduct(html, "https://produto.mercadolivre.com.br/MLB-1").price, 3599.9);
});

test("heurística ignora valores de parcela", () => {
  const html = `<p>ou 10x de R$ 379,90 sem juros</p><p>Por R$ 3.799,00 no Pix</p>`;
  assert.equal(extractProduct(html, "https://x.com").price, 3799);
});

test("regex personalizada tem prioridade", () => {
  const html = `<span data-pix="3.199,00"></span><meta property="product:price:amount" content="3499">`;
  assert.equal(extractProduct(html, "https://x.com", { customRegex: 'data-pix="([^"]+)"' }).price, 3199);
});

test("analyze calcula mínimo, quedas e veredito", () => {
  const now = Date.parse("2026-10-15T12:00:00Z");
  const h = [
    { t: "2026-09-01T00:00:00Z", price: 3999 },
    { t: "2026-09-10T00:00:00Z", price: 3799 },
    { t: "2026-09-20T00:00:00Z", price: 4199 },
    { t: "2026-10-10T00:00:00Z", price: 3499 },
  ];
  const s = analyze(h, now);
  assert.equal(s.min, 3499);
  assert.equal(s.max, 4199);
  assert.equal(s.drops.length, 2);
  assert.equal(s.drops[0].to, 3499);
  assert.equal(s.verdict.label, "Menor preço já registrado");
  assert.ok(s.change30d > 0);
});

test("parseCoupons encontra códigos e descarta expirados", () => {
  const now = Date.parse("2026-10-15T00:00:00Z");
  const html = `
    <div class="c"><h3>10% OFF em consoles</h3><button data-clipboard-text="GAMER10">Copiar</button><span>Válido até 31/10/2026</span></div>
    <div class="c"><h3>R$ 200 OFF</h3><button data-code="VELHO200">Copiar</button><span>Expira em 01/01/2026</span></div>
    <script>{"couponCode":"PS5FRETE","title":"Frete grátis"}</script>
    <button data-code="COPIAR">x</button>`;
  const list = parseCoupons(html, { source: "teste", now });
  const codes = list.map((c) => c.code).sort();
  assert.deepEqual(codes, ["GAMER10", "PS5FRETE"]);
  const g = list.find((c) => c.code === "GAMER10");
  assert.match(g.description, /10% OFF/);
  assert.equal(g.expiresAt.slice(0, 10), "2026-10-31");
});

test("storeFromUrl e couponStatus", () => {
  assert.equal(storeFromUrl("https://www.kabum.com.br/produto/1").slug, "kabum");
  assert.equal(storeFromUrl("https://produto.mercadolivre.com.br/MLB-1").slug, "mercado-livre");
  const base = { worked: 0, failed: 0, lastSeenAt: new Date().toISOString(), expiresAt: null };
  assert.equal(couponStatus({ ...base, failed: 3 }).level, "bad");
  assert.equal(couponStatus({ ...base, worked: 2 }).level, "good");
});
