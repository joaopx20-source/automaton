import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { Store } from "../lib/db.js";
import { createApp } from "../server.js";

function page(price) {
  return `<script type="application/ld+json">{"@type":"Product","name":"PlayStation 5","offers":{"@type":"Offer","price":${price},"availability":"InStock"}}</script>`;
}

async function startApp(fetchPageImpl, opts = {}) {
  const store = new Store(null);
  store.settings.couponSources = ["https://cupons.test/{slug}"];
  const app = createApp({ store, fetchPageImpl, ...opts });
  const server = http.createServer(app.handler);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const call = async (path, method = "GET", body, headers = {}) => {
    const res = await fetch(base + path, { method, headers: { "content-type": "application/json", ...headers }, body: body && JSON.stringify(body) });
    return { status: res.status, data: await res.json().catch(() => null) };
  };
  return { store, app, server, call, close: () => new Promise((r) => server.close(r)) };
}

test("fluxo completo: adicionar, cair preço, notificar, buscar cupons", async () => {
  let price = 3999;
  const fetchPageImpl = async (url) => {
    if (url.startsWith("https://cupons.test/")) return `<div>15% OFF consoles <span data-code="CONSOLE15"></span></div>`;
    return page(price);
  };
  const { store, call, close } = await startApp(fetchPageImpl);
  try {
    const add = await call("/api/products", "POST", { url: "https://www.kabum.com.br/produto/ps5", targetPrice: "3500" });
    assert.equal(add.status, 200);
    assert.equal(add.data.currentPrice, 3999);
    assert.equal(add.data.name, "PlayStation 5");
    assert.equal(add.data.store, "kabum");

    price = 3799; // queda de 5% (> 3% padrão)
    let r = await call(`/api/products/${add.data.id}/check`, "POST");
    assert.equal(r.data.currentPrice, 3799);
    assert.equal(store.notifications[0].kind, "drop");

    price = 3449; // abaixo do alvo
    r = await call(`/api/products/${add.data.id}/check`, "POST");
    assert.equal(store.notifications[0].kind, "target");
    assert.equal(r.data.stats.min, 3449);
    assert.equal(r.data.stats.drops.length, 2);

    // Mesmo preço de novo: não deve notificar outra vez.
    await call(`/api/products/${add.data.id}/check`, "POST");
    assert.equal(store.notifications.length, 2);

    // Preço manual
    r = await call(`/api/products/${add.data.id}/prices`, "POST", { price: "3399,90" });
    assert.equal(r.data.currentPrice, 3399.9);

    const s = await call("/api/coupons/search", "POST", { productId: add.data.id });
    assert.equal(s.data.added, 1);
    const coupons = await call("/api/coupons?store=kabum");
    assert.equal(coupons.data[0].code, "CONSOLE15");
    const vote = await call(`/api/coupons/${coupons.data[0].id}/vote`, "POST", { worked: true });
    assert.equal(vote.data.status.level, "good");
  } finally {
    await close();
  }
});

test("erros de loja ficam registrados no produto", async () => {
  const { call, close } = await startApp(async () => { throw new Error("A loja bloqueou a consulta automática (captcha)."); });
  try {
    const r = await call("/api/products", "POST", { url: "https://www.amazon.com.br/dp/X" });
    assert.equal(r.status, 200);
    assert.match(r.data.lastError, /captcha/);
    const bad = await call("/api/products", "POST", { url: "nao-e-url" });
    assert.equal(bad.status, 400);
  } finally {
    await close();
  }
});

test("senha opcional protege a API", async () => {
  const { call, close } = await startApp(async () => page(1), { password: "segredo" });
  try {
    assert.equal((await call("/api/products")).status, 401);
    const auth = { authorization: "Basic " + Buffer.from("eu:segredo").toString("base64") };
    assert.equal((await call("/api/products", "GET", undefined, auth)).status, 200);
  } finally {
    await close();
  }
});
