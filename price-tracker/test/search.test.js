import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { extractListings, matchesQuery, queryTokens, classify, searchProduct, buildSearchUrl } from "../lib/search.js";
import { Store } from "../lib/db.js";
import { createApp } from "../server.js";

const AMAZON = `
<div data-component-type="s-search-result" data-asin="A1">
  <img class="s-image" src="https://m.media-amazon.com/ps5.jpg">
  <a class="a-link-normal" href="/Console-PlayStation-5-Slim/dp/B0CL1/ref=sr_1_1"><h2 class="a-size-mini"><span>Console PlayStation®5 Slim Digital</span></h2></a>
  <span class="a-price" data-a-size="xl"><span class="a-offscreen">R$ 3.399,00</span></span>
  <span class="a-price a-text-price"><span class="a-offscreen">R$ 3.999,00</span></span>
</div>
<div data-component-type="s-search-result" data-asin="A2">
  <a class="a-link-normal" href="/Controle-DualSense/dp/B0C2/ref=sr_1_2"><h2><span>Controle sem fio DualSense para PS5</span></h2></a>
  <span class="a-price"><span class="a-offscreen">R$ 399,00</span></span>
</div>`;

const MERCADOLIVRE = `
<li class="ui-search-layout__item"><div class="poly-card poly-card--list">
  <img class="poly-component__picture" src="https://http2.mlstatic.com/ps5.webp">
  <a href="https://produto.mercadolivre.com.br/MLB-1-ps5" class="poly-component__title">Sony Playstation 5 Slim 1tb Digital Cor Branco</a>
  <s class="andes-money-amount andes-money-amount--previous"><span class="andes-money-amount__fraction">4.299</span></s>
  <div class="poly-price__current"><span class="andes-money-amount"><span class="andes-money-amount__fraction">3.289</span><span class="andes-money-amount__cents">90</span></span></div>
</div></li>
<li class="ui-search-layout__item"><div class="poly-card poly-card--list">
  <a href="https://produto.mercadolivre.com.br/MLB-2-ps5-usado" class="poly-component__title">Playstation 5 Usado Com Caixa</a>
  <div class="poly-price__current"><span class="andes-money-amount__fraction">2.100</span></div>
</div></li>`;

const NEXT = `<script id="__NEXT_DATA__" type="application/json">${JSON.stringify({
  props: { pageProps: { data: { catalogServer: { data: [
    { name: "Console Sony PlayStation 5 Slim, SSD 1TB, Edição Digital", price: 3699.9, priceWithDiscount: 3329.91, link: "/produto/123/console-ps5", image: "https://img/ps5.jpg" },
    { name: "Capa Protetora para PS5 Slim", price: 89.9, link: "/produto/9/capa" },
    { name: "Console PS5 Slim Recondicionado", price: 2399, link: "/produto/7/ps5-recond" },
  ] } } } },
})}</script>`;

test("extrai anúncios da Amazon ignorando preço riscado", () => {
  const items = extractListings(AMAZON, "https://www.amazon.com.br/s?k=ps5");
  assert.equal(items.length, 2);
  assert.equal(items[0].price, 3399);
  assert.equal(items[0].title, "Console PlayStation®5 Slim Digital");
  assert.equal(items[0].url, "https://www.amazon.com.br/Console-PlayStation-5-Slim/dp/B0CL1/ref=sr_1_1");
});

test("extrai anúncios do Mercado Livre usando o preço atual", () => {
  const items = extractListings(MERCADOLIVRE, "https://lista.mercadolivre.com.br/ps5");
  assert.equal(items[0].price, 3289.9);
  assert.equal(items[0].url, "https://produto.mercadolivre.com.br/MLB-1-ps5");
  assert.equal(items[1].price, 2100);
});

test("extrai de JSON embutido (Next.js) com preço à vista", () => {
  const items = extractListings(NEXT, "https://www.kabum.com.br/busca/ps5");
  const ps5 = items.find((i) => i.title.startsWith("Console Sony"));
  assert.equal(ps5.price, 3329.91);
  assert.equal(ps5.url, "https://www.kabum.com.br/produto/123/console-ps5");
});

test("termos, apelidos e classificação", () => {
  const t = queryTokens("PS5 Slim");
  assert.deepEqual(t, ["ps5", "slim"]);
  assert.ok(matchesQuery("Sony Playstation 5 Slim 1tb", t));
  assert.ok(!matchesQuery("Playstation 4 Slim", t));
  assert.ok(!matchesQuery("iPhone 150", queryTokens("iphone 15")));
  assert.equal(classify("Controle DualSense para PS5", t).accessory, true);
  assert.equal(classify("Console PS5 Slim + Jogo EA FC 25", t).accessory, false);
  assert.equal(classify("PS5 Slim recondicionado", t).used, true);
  assert.equal(buildSearchUrl("https://x.com/{q-dash}?q={q}", "PS5 Slim"), "https://x.com/ps5-slim?q=PS5%20Slim");
});

test("searchProduct junta as lojas e devolve o menor preço válido", async () => {
  const pages = { amazon: AMAZON, mercadolivre: MERCADOLIVRE, kabum: NEXT };
  const fetchPage = async (url) => {
    const key = Object.keys(pages).find((k) => url.includes(k));
    if (!key) throw new Error("HTTP 403");
    return pages[key];
  };
  const r = await searchProduct("ps5 slim", {
    sources: ["https://www.amazon.com.br/s?k={q}", "https://lista.mercadolivre.com.br/{q-dash}", "https://www.kabum.com.br/busca/{q-dash}", "https://bloqueada.com/{q}"],
    fetchPage,
  });
  assert.equal(r.best.price, 3289.9);
  assert.equal(r.best.storeName, "Mercado Livre");
  assert.deepEqual(r.results.map((i) => i.price), [3289.9, 3329.91, 3399]);
  const reasons = Object.fromEntries(r.hidden.map((h) => [h.price, h.reason]));
  assert.equal(reasons[399], undefined); // "Controle … para PS5" nem contém "slim": fora da busca
  assert.equal(reasons[89.9], "acessório");
  assert.equal(reasons[2399], "usado/recondicionado");
  assert.equal(r.sources.find((s) => s.url.includes("bloqueada")).error, "HTTP 403");

  const withUsed = await searchProduct("ps5 slim", { sources: ["https://www.kabum.com.br/busca/{q-dash}"], fetchPage, includeUsed: true });
  assert.equal(withUsed.best.price, 2399);
});

test("API: buscar e monitorar a busca avisa quando o menor preço cai", async () => {
  let kabumPrice = 3329.91;
  const fetchPage = async (url) => url.includes("kabum")
    ? NEXT.replace("3329.91", String(kabumPrice))
    : url.includes("amazon") ? AMAZON : (() => { throw new Error("HTTP 403"); })();
  const store = new Store(null);
  store.settings.searchSources = ["https://www.amazon.com.br/s?k={q}", "https://www.kabum.com.br/busca/{q-dash}"];
  const { handler } = createApp({ store, fetchPageImpl: fetchPage });
  const server = http.createServer(handler);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const post = (path, body) => fetch(base + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
  try {
    const r = await post("/api/search", { query: "PS5 Slim" });
    assert.equal(r.best.price, 3329.91);
    assert.equal(r.best.storeName, "KaBuM!");

    const p = await post("/api/products", { query: "PS5 Slim", targetPrice: "3000" });
    assert.equal(p.currentPrice, 3329.91);
    assert.equal(p.storeName, "KaBuM!");
    assert.equal(p.url, "https://www.kabum.com.br/produto/123/console-ps5");

    kabumPrice = 2999; // abaixo do alvo
    const checked = await post(`/api/products/${p.id}/check`, {});
    assert.equal(checked.currentPrice, 2999);
    assert.equal(store.notifications[0].kind, "target");
    assert.match(store.notifications[0].message, /KaBuM!/);
  } finally {
    await new Promise((r) => server.close(r));
  }
});
