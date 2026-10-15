// Interface do Monitor de Preços (sem frameworks).
const $ = (s, el = document) => el.querySelector(s);
const brl = (n) => n == null ? "—" : n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const dateFmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
const shortDate = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" });
const fmtDate = (s) => s ? dateFmt.format(new Date(s)) : "—";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let products = [];
let openId = null;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "content-type": "application/json", ...opts.headers },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

function toast(msg, err = false) {
  const el = document.createElement("div");
  el.className = "toast" + (err ? " err" : "");
  el.textContent = msg;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 6000);
}

async function busy(btn, fn) {
  btn.disabled = true;
  try { return await fn(); } catch (e) { toast(e.message, true); } finally { btn.disabled = false; }
}

// ---------- Abas
function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== `tab-${name}`));
  ({ coupons: loadCoupons, alerts: loadAlerts, settings: loadSettings }[name] ?? (() => {}))();
  try { localStorage.setItem("tab", name); } catch {}
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ---------- Produtos
function sparkline(history) {
  const pts = history.slice(-60);
  if (pts.length < 2) return "";
  const prices = pts.map((p) => p.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const t0 = Date.parse(pts[0].t), t1 = Date.parse(pts.at(-1).t) || t0 + 1;
  const x = (t) => ((Date.parse(t) - t0) / Math.max(t1 - t0, 1)) * 296 + 2;
  const y = (p) => max === min ? 22 : 40 - ((p - min) / (max - min)) * 36;
  // Linha em degraus: o preço vale até a próxima leitura.
  let d = `M${x(pts[0].t)},${y(pts[0].price)}`;
  for (let i = 1; i < pts.length; i++) d += `H${x(pts[i].t)}V${y(pts[i].price)}`;
  return `<svg class="spark" viewBox="0 0 300 44" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" vector-effect="non-scaling-stroke"/></svg>`;
}

function productCard(p) {
  const s = p.stats;
  const v = s?.verdict;
  const reached = p.targetPrice && p.currentPrice && p.currentPrice <= p.targetPrice;
  return `<article class="card product" data-id="${p.id}">
    <div class="head">
      ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
      <div>
        <div class="name" title="${esc(p.name)}">${esc(p.name || p.url)}</div>
        <div class="store">${p.query ? "Mais barato agora: " : ""}${esc(p.storeName)}${p.active ? "" : " · pausado"}${p.available === false ? " · esgotado" : ""}</div>
        ${p.query && p.bestTitle ? `<div class="store" title="${esc(p.bestTitle)}">${esc(p.bestTitle.slice(0, 80))}</div>` : ""}
      </div>
    </div>
    <div class="price">${brl(p.currentPrice)}</div>
    <div class="row" style="gap:.4rem">
      ${reached ? `<span class="badge good">🎯 Alvo atingido</span>` : ""}
      ${v ? `<span class="badge ${v.level}">${esc(v.label)}</span>` : ""}
    </div>
    <div class="meta">
      <span>Alvo: ${brl(p.targetPrice)}</span>
      <span>Menor: ${brl(s?.min)}</span>
      <span>Quedas: ${s?.drops.length ?? 0}</span>
    </div>
    ${sparkline(p.history)}
    ${p.lastError ? `<div class="error">⚠️ ${esc(p.lastError)}</div>` : ""}
    <div class="store">Verificado: ${fmtDate(p.lastCheckedAt)}</div>
    <div class="actions">
      <button class="small primary" data-act="open">Histórico</button>
      <button class="small" data-act="check">↻ Verificar</button>
      <button class="small" data-act="coupons">🎟️ Cupons</button>
      ${p.url ? `<a class="btnlink" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Abrir loja ↗</a>` : ""}
    </div>
  </article>`;
}

function renderCompare() {
  const priced = products.filter((p) => p.currentPrice && p.active);
  if (priced.length < 2) { $("#compare").innerHTML = ""; return; }
  priced.sort((a, b) => a.currentPrice - b.currentPrice);
  $("#compare").innerHTML = `<div class="card"><h2>Comparação (mais barato primeiro)</h2>
    <div style="overflow-x:auto"><table class="table"><thead><tr><th>Produto</th><th>Loja</th><th class="num">Agora</th><th class="num">Menor histórico</th><th class="num">Alvo</th></tr></thead><tbody>
    ${priced.map((p, i) => `<tr><td>${esc((p.name || p.url).slice(0, 70))}</td><td>${esc(p.storeName)}</td>
      <td class="num ${i === 0 ? "best" : ""}">${brl(p.currentPrice)}${i === 0 ? " ★" : ""}</td><td class="num">${brl(p.stats?.min)}</td><td class="num">${brl(p.targetPrice)}</td></tr>`).join("")}
    </tbody></table></div></div>`;
}

function renderProducts() {
  const el = $("#products");
  el.innerHTML = products.length ? products.map(productCard).join("")
    : `<div class="empty">Nenhum produto ainda. Cole o link de um PS5 (ou qualquer produto) acima para começar.</div>`;
  renderCompare();
  const stores = [...new Set(products.map((p) => p.store))];
  $("#store-list").innerHTML = stores.map((s) => `<option value="${esc(s)}">`).join("");
  if (openId) renderDetail();
}

async function loadProducts() {
  products = await api("/api/products");
  renderProducts();
}

$("#products").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const id = btn.closest("[data-id]").dataset.id;
  const act = btn.dataset.act;
  if (act === "open") { openId = id; renderDetail(); $("#detail").showModal(); }
  if (act === "check") await busy(btn, async () => { upsert(await api(`/api/products/${id}/check`, { method: "POST" })); toast("Preço atualizado"); });
  if (act === "coupons") await busy(btn, async () => {
    const r = await api("/api/coupons/search", { method: "POST", body: { productId: id } });
    $("#coupon-filter").value = r.store.slug;
    showTab("coupons");
    reportCoupons(r);
  });
});

function upsert(p) {
  const i = products.findIndex((x) => x.id === p.id);
  if (i >= 0) products[i] = p; else products.push(p);
  renderProducts();
}

$("#add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const btn = form.querySelector("button[type=submit]");
  await busy(btn, async () => {
    btn.textContent = "Consultando loja…";
    try {
      const p = await api("/api/products", { method: "POST", body: Object.fromEntries(new FormData(form)) });
      upsert(p);
      form.reset();
      toast(p.lastError ? `Adicionado, mas: ${p.lastError}` : `Monitorando: ${brl(p.currentPrice)}`, Boolean(p.lastError));
    } finally { btn.textContent = "Adicionar"; }
  });
});

$("#check-all").addEventListener("click", (e) => busy(e.target, async () => {
  await api("/api/check-all", { method: "POST" });
  toast("Verificando todos os produtos… os cards atualizam sozinhos.");
}));

// ---------- Busca por nome
let lastSearch = null;

function offerRow(o, i) {
  return `<tr>
    <td class="num ${i === 0 ? "best" : ""}">${brl(o.price)}${i === 0 ? " ★" : ""}</td>
    <td>${esc(o.storeName)}</td>
    <td class="title-cell">${esc(o.title)}${o.reason ? ` <span class="badge warn">${esc(o.reason)}</span>` : ""}</td>
    <td class="nowrap"><a class="btnlink" href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">Abrir ↗</a>
      ${o.url && o.url !== o.searchUrl ? `<button class="small" data-track="${esc(o.url)}">Monitorar</button>` : ""}</td>
  </tr>`;
}

function renderSearch(r) {
  const el = $("#search-results");
  const failed = r.sources.filter((s) => s.error);
  const sourcesLine = r.sources.map((s) => `${esc(s.source)}: ${s.error ? "✗" : s.count}`).join(" · ");
  if (!r.best) {
    el.innerHTML = `<div class="card"><h2>Nenhuma oferta encontrada para "${esc(r.query)}"</h2>
      <p class="hint">${failed.length ? `${failed.length} de ${r.sources.length} lojas não responderam (podem ter bloqueado a consulta).` : "Tente um termo mais simples."}</p>
      <p class="hint">${sourcesLine}</p>
      ${r.hidden.length ? `<details><summary>${r.hidden.length} anúncio(s) escondido(s) pelos filtros</summary><div class="scroll"><table class="table"><tbody>${r.hidden.map(offerRow).join("")}</tbody></table></div></details>` : ""}</div>`;
    return;
  }
  const b = r.best;
  el.innerHTML = `<div class="card best-offer">
      <div class="k">Menor preço encontrado para "${esc(r.query)}"</div>
      <div class="head">
        ${b.image ? `<img src="${esc(b.image)}" alt="" referrerpolicy="no-referrer">` : ""}
        <div>
          <div class="price">${brl(b.price)}</div>
          <div class="name">${esc(b.title)}</div>
          <div class="store">${esc(b.storeName)}${r.median ? ` · preço típico ${brl(r.median)} (${Math.round((1 - b.price / r.median) * 100)}% abaixo)` : ""}</div>
        </div>
      </div>
      <div class="actions">
        <a class="btnlink primary" href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">Ver na loja ↗</a>
        <button class="small" data-coupons="${esc(b.url)}">🎟️ Cupons: ${esc(b.storeName)}</button>
      </div>
      <form id="watch-search" class="row watch">
        <label>Avise-me quando a busca achar por menos de (R$)<input name="targetPrice" inputmode="decimal" placeholder="${Math.floor(b.price * 0.95)}"></label>
        <button type="submit">🔔 Monitorar esta busca</button>
      </form>
    </div>
    <div class="card">
      <h2>${r.results.length} oferta(s), da mais barata para a mais cara</h2>
      <div class="scroll"><table class="table offers"><thead><tr><th class="num">Preço</th><th>Loja</th><th>Anúncio</th><th></th></tr></thead>
      <tbody>${r.results.map(offerRow).join("")}</tbody></table></div>
      ${r.hidden.length ? `<details><summary>${r.hidden.length} anúncio(s) escondido(s): acessórios, usados ou preço suspeito</summary>
        <div class="scroll"><table class="table offers"><tbody>${r.hidden.map(offerRow).join("")}</tbody></table></div></details>` : ""}
      <p class="hint">Lojas consultadas — ${sourcesLine}${failed.length ? ` · ✗ = não respondeu ou bloqueou a consulta` : ""}</p>
    </div>`;

  $("#watch-search").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData($("#search-form"));
    await busy(e.submitter, async () => {
      const p = await api("/api/products", { method: "POST", body: {
        query: r.query, targetPrice: new FormData(e.target).get("targetPrice"), minPrice: f.get("minPrice"), maxPrice: f.get("maxPrice") } });
      upsert(p);
      toast(`Monitorando a busca "${r.query}" em todas as lojas.`);
    });
  };
}

$("#search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { query: f.get("query"), minPrice: f.get("minPrice"), maxPrice: f.get("maxPrice"),
    includeUsed: f.has("includeUsed"), includeAccessories: f.has("includeAccessories") };
  const btn = e.submitter;
  await busy(btn, async () => {
    btn.textContent = "Buscando nas lojas…";
    $("#search-results").innerHTML = `<div class="card hint">Consultando Mercado Livre, KaBuM!, Amazon, Magalu e outras… pode levar até 20 segundos.</div>`;
    try {
      lastSearch = await api("/api/search", { method: "POST", body });
      renderSearch(lastSearch);
    } catch (err) {
      $("#search-results").innerHTML = "";
      throw err;
    } finally { btn.textContent = "Buscar em todas as lojas"; }
  });
});

$("#search-results").addEventListener("click", async (e) => {
  const track = e.target.closest("button[data-track]");
  const coupons = e.target.closest("button[data-coupons]");
  if (track) await busy(track, async () => {
    const p = await api("/api/products", { method: "POST", body: { url: track.dataset.track } });
    upsert(p);
    toast(`Monitorando: ${p.name ?? "produto"} (${brl(p.currentPrice)})`);
  });
  if (coupons) await busy(coupons, async () => {
    const r = await api("/api/coupons/search", { method: "POST", body: { url: coupons.dataset.coupons } });
    $("#coupon-filter").value = r.store.slug;
    showTab("coupons");
    reportCoupons(r);
  });
});

// ---------- Detalhe + gráfico
const CH = { W: 800, H: 280, L: 70, R: 16, T: 16, B: 28 };
// Largura real do diálogo, para o SVG não distorcer o texto em telas pequenas.
const chartWidth = () => Math.max(280, Math.min(860, innerWidth - 32) - 34);

/** Escalas do gráfico com marcas "redondas" no eixo Y (ex.: 3.400, 3.600…). */
function chartScale(p) {
  const { W, H, L, R, T, B } = CH;
  const pts = p.history;
  const prices = pts.map((h) => h.price).concat(p.targetPrice ? [p.targetPrice] : []);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const raw = (hi - lo) / 4 || hi * 0.05;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((v) => v >= raw);
  const min = Math.max(0, Math.floor(lo / step) * step - (lo % step === 0 ? step : 0));
  const max = Math.ceil(hi / step) * step + (hi % step === 0 ? step : 0);
  const ticks = [];
  for (let v = min; v <= max + step / 2; v += step) ticks.push(v);
  const t0 = Date.parse(pts[0].t);
  const t1 = Math.max(Date.now(), t0 + 3_600_000);
  return {
    pts, t0, t1, ticks,
    x: (t) => L + ((t - t0) / (t1 - t0)) * (W - L - R),
    y: (v) => T + (1 - (v - min) / (max - min)) * (H - T - B),
  };
}

function chartSvg(p) {
  const pts = p.history;
  if (pts.length < 1) return `<div class="empty">Sem histórico ainda.</div>`;
  const { W, H, L, R, T, B } = CH;
  const { t0, t1, x, y, ticks } = chartScale(p);

  let d = `M${x(t0)},${y(pts[0].price)}`;
  for (let i = 1; i < pts.length; i++) d += `H${x(Date.parse(pts[i].t))}V${y(pts[i].price)}`;
  d += `H${x(t1)}`;
  const area = `${d}V${H - B}H${x(t0)}Z`;

  const grid = ticks;
  const xTicks = Array.from({ length: 5 }, (_, i) => t0 + ((t1 - t0) * i) / 4);
  const s = p.stats;
  const minPt = pts.findLast((h) => h.price === s.min);

  return `<div class="chart-wrap">
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Histórico de preço de ${esc(p.name)}">
      <g class="grid">${grid.map((v) => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`).join("")}</g>
      <g class="axis">
        ${grid.map((v) => `<text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${brl(v).replace(/,00$/, "")}</text>`).join("")}
        ${xTicks.map((t, i) => `<text x="${x(t)}" y="${H - 8}" text-anchor="${i === 0 ? "start" : i === 4 ? "end" : "middle"}">${shortDate.format(t)}</text>`).join("")}
      </g>
      <path class="area" d="${area}"/>
      ${p.targetPrice ? `<line class="target" x1="${L}" x2="${W - R}" y1="${y(p.targetPrice)}" y2="${y(p.targetPrice)}"/>
        <text class="target-label" x="${W - R - 4}" y="${y(p.targetPrice) - 6}" text-anchor="end">Alvo ${brl(p.targetPrice)}</text>` : ""}
      <path class="line" d="${d}" vector-effect="non-scaling-stroke"/>
      ${minPt ? `<circle class="min-dot" cx="${x(Date.parse(minPt.t))}" cy="${y(minPt.price)}" r="5"/>
        <text class="min-label" x="${x(Date.parse(minPt.t)) + (x(Date.parse(minPt.t)) > W * 0.7 ? -8 : 8)}" y="${y(minPt.price) + 18}" text-anchor="${x(Date.parse(minPt.t)) > W * 0.7 ? "end" : "start"}">Menor ${brl(minPt.price)}</text>` : ""}
      <line class="cross" y1="${T}" y2="${H - B}" visibility="hidden"/>
      <circle class="hover-dot" r="5" visibility="hidden"/>
      <rect class="hit" x="${L}" y="0" width="${W - L - R}" height="${H}" fill="transparent"/>
    </svg>
    <div class="tooltip" hidden></div>
  </div>`;
}

function bindChart(p) {
  const svg = $("#d-body .chart");
  if (!svg) return;
  const tip = $("#d-body .tooltip"), cross = svg.querySelector(".cross"), dot = svg.querySelector(".hover-dot");
  const { W, H, L, R } = CH;
  const { pts, t0, t1, y } = chartScale(p);

  const move = (ev) => {
    const r = svg.getBoundingClientRect();
    const vx = ((ev.clientX - r.left) / r.width) * W;
    const t = t0 + ((Math.min(Math.max(vx, L), W - R) - L) / (W - L - R)) * (t1 - t0);
    const pt = pts.findLast((h) => Date.parse(h.t) <= t) ?? pts[0];
    const vy = y(pt.price);
    cross.setAttribute("x1", vx); cross.setAttribute("x2", vx);
    dot.setAttribute("cx", vx); dot.setAttribute("cy", vy);
    cross.setAttribute("visibility", "visible"); dot.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.innerHTML = `<b>${brl(pt.price)}</b>${fmtDate(pt.t)}${pt.available === false ? " · esgotado" : ""}`;
    const px = (vx / W) * r.width, py = (vy / H) * r.height;
    tip.style.left = Math.min(px + 12, r.width - tip.offsetWidth - 4) + "px";
    tip.style.top = Math.max(py - tip.offsetHeight - 10, 0) + "px";
  };
  const leave = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
  svg.addEventListener("pointermove", move);
  svg.addEventListener("pointerdown", move);
  svg.addEventListener("pointerleave", leave);
}

function renderDetail() {
  CH.W = chartWidth();
  const p = products.find((x) => x.id === openId);
  if (!p) { $("#detail").close(); return; }
  const s = p.stats;
  $("#d-title").textContent = p.name || p.url;
  const stat = (k, v) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`;
  $("#d-body").innerHTML = `
    <div class="store">${esc(p.storeName)} · <a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">abrir na loja</a> · fonte do preço: ${esc(p.history.at(-1)?.source ?? "—")}</div>
    ${s ? `<div class="stats">
      ${stat("Agora", brl(s.current))}
      ${stat("Menor já visto", `${brl(s.min)}<div class="k">${fmtDate(s.minAt)}</div>`)}
      ${stat("Maior", brl(s.max))}
      ${stat("Média", brl(s.avg))}
      ${stat("Acima do menor", `${s.aboveMinPercent}%`)}
      ${stat("Variação 30 dias", s.change30d > 0 ? `−${s.change30d}%` : s.change30d < 0 ? `+${-s.change30d}%` : "0%")}
    </div><span class="badge ${s.verdict.level}">${esc(s.verdict.label)}</span>` : ""}
    <h2 style="margin-top:1rem">Histórico de preço</h2>
    ${chartSvg(p)}
    <h2 style="margin-top:1rem">Quedas de preço</h2>
    ${s?.drops.length ? `<div style="overflow-x:auto"><table class="table"><thead><tr><th>Quando</th><th class="num">De</th><th class="num">Para</th><th class="num">Queda</th></tr></thead><tbody>
      ${s.drops.slice(0, 30).map((d) => `<tr><td>${fmtDate(d.at)}</td><td class="num">${brl(d.from)}</td><td class="num">${brl(d.to)}</td><td class="num">−${d.percent}%</td></tr>`).join("")}
      </tbody></table></div>` : `<p class="hint">Nenhuma queda registrada ainda.</p>`}
    <details style="margin-top:1rem"><summary>Todas as leituras (${p.history.length})</summary>
      <div style="overflow-x:auto;max-height:240px"><table class="table"><thead><tr><th>Data</th><th class="num">Preço</th><th>Fonte</th></tr></thead><tbody>
      ${p.history.slice().reverse().map((h) => `<tr><td>${fmtDate(h.t)}</td><td class="num">${brl(h.price)}</td><td>${esc(h.source)}</td></tr>`).join("")}
      </tbody></table></div></details>
    <form id="d-edit" class="row" style="margin-top:1rem">
      <label>Preço-alvo (R$)<input name="targetPrice" inputmode="decimal" value="${p.targetPrice ?? ""}"></label>
      <label>Queda mínima (%)<input name="dropPercent" inputmode="decimal" value="${p.dropPercent ?? ""}" placeholder="padrão"></label>
      <label class="grow">Nome<input name="name" value="${esc(p.name ?? "")}"></label>
      <button type="submit">Salvar</button>
    </form>
    <form id="d-manual" class="row">
      <label class="grow">Registrar preço manualmente (se a loja bloquear a consulta)<input name="price" inputmode="decimal" placeholder="3499,90"></label>
      <button type="submit">Registrar</button>
    </form>
    <div class="row">
      <button type="button" id="d-toggle">${p.active ? "⏸ Pausar monitoramento" : "▶ Retomar monitoramento"}</button>
      <button type="button" id="d-delete" class="ghost" style="color:var(--bad)">Excluir produto</button>
    </div>`;
  bindChart(p);

  $("#d-edit").onsubmit = async (e) => {
    e.preventDefault();
    await busy(e.submitter, async () => { upsert(await api(`/api/products/${p.id}`, { method: "PATCH", body: Object.fromEntries(new FormData(e.target)) })); toast("Salvo"); });
  };
  $("#d-manual").onsubmit = async (e) => {
    e.preventDefault();
    await busy(e.submitter, async () => { upsert(await api(`/api/products/${p.id}/prices`, { method: "POST", body: Object.fromEntries(new FormData(e.target)) })); toast("Preço registrado"); });
  };
  $("#d-toggle").onclick = (e) => busy(e.target, async () => upsert(await api(`/api/products/${p.id}`, { method: "PATCH", body: { active: !p.active } })));
  $("#d-delete").onclick = async () => {
    if (!confirm("Excluir este produto e todo o histórico?")) return;
    await api(`/api/products/${p.id}`, { method: "DELETE" });
    openId = null;
    $("#detail").close();
    await loadProducts();
  };
}
$("#d-close").addEventListener("click", () => $("#detail").close());
$("#detail").addEventListener("close", () => (openId = null));

// ---------- Cupons
function reportCoupons(r) {
  const fails = r.report.filter((x) => x.error).length;
  $("#coupon-report").textContent = `${r.store.name}: ${r.total} cupom(ns) encontrado(s), ${r.added} novo(s).` +
    (fails ? ` ${fails} fonte(s) não responderam.` : "");
  loadCoupons();
}

async function loadCoupons() {
  const store = $("#coupon-filter").value;
  const list = await api(`/api/coupons?store=${encodeURIComponent(store)}&expired=${$("#coupon-expired").checked ? 1 : 0}`);
  const all = await api("/api/coupons?expired=1");
  const stores = [...new Map(all.map((c) => [c.store, c.storeName])).entries()];
  $("#coupon-filter").innerHTML = `<option value="">Todas</option>` +
    stores.map(([s, n]) => `<option value="${esc(s)}" ${s === store ? "selected" : ""}>${esc(n)}</option>`).join("");
  $("#coupons").innerHTML = list.length ? list.map((c) => `<div class="coupon" data-id="${c.id}">
      <button class="ghost" data-act="copy" title="Copiar"><code>${esc(c.code)}</code></button>
      <div class="info">
        <div>${esc(c.description || "Sem descrição")}</div>
        <small>${esc(c.storeName)} · ${c.expiresAt ? `válido até ${new Date(c.expiresAt).toLocaleDateString("pt-BR")}` : "sem data de validade"} · fonte: ${esc(c.source)} · visto ${fmtDate(c.lastSeenAt)}</small>
      </div>
      <span class="badge ${c.status.level}">${esc(c.status.label)}</span>
      <div class="actions">
        <button class="small" data-act="yes" title="Funcionou">✓ Funcionou</button>
        <button class="small" data-act="no" title="Não funcionou">✗ Não</button>
        <button class="small ghost" data-act="del" title="Remover">🗑</button>
      </div>
    </div>`).join("") : `<div class="empty">Nenhum cupom${store ? " para esta loja" : ""}. Faça uma busca acima.</div>`;
}

$("#coupons").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const id = btn.closest("[data-id]").dataset.id;
  const act = btn.dataset.act;
  if (act === "copy") {
    const code = btn.textContent.trim();
    try { await navigator.clipboard.writeText(code); toast(`Copiado: ${code}`); } catch { toast(code); }
    return;
  }
  await busy(btn, async () => {
    if (act === "del") await api(`/api/coupons/${id}`, { method: "DELETE" });
    else await api(`/api/coupons/${id}/vote`, { method: "POST", body: { worked: act === "yes" } });
    loadCoupons();
  });
});
$("#coupon-filter").addEventListener("change", loadCoupons);
$("#coupon-expired").addEventListener("change", loadCoupons);
$("#coupon-search").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = new FormData(e.target).get("q").trim();
  await busy(e.submitter, async () => {
    $("#coupon-report").textContent = "Buscando…";
    const r = await api("/api/coupons/search", { method: "POST", body: /^https?:\/\//.test(q) ? { url: q } : { store: q } });
    $("#coupon-filter").value = r.store.slug;
    reportCoupons(r);
  });
});
$("#coupon-add").addEventListener("submit", async (e) => {
  e.preventDefault();
  await busy(e.submitter, async () => {
    await api("/api/coupons", { method: "POST", body: Object.fromEntries(new FormData(e.target)) });
    e.target.reset();
    loadCoupons();
  });
});

// ---------- Alertas
async function loadAlerts() {
  const list = await api("/api/notifications");
  $("#alerts").innerHTML = list.length ? list.map((n) => `<div class="alert">
      <time>${fmtDate(n.at)}</time>
      <div><b>${esc(n.title)}</b></div>
      <div>${esc(n.message)}</div>
      ${n.url ? `<a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">abrir</a>` : ""}
      <div class="store">Enviado: ${Object.entries(n.channels ?? {}).map(([k, v]) => `${esc(k)}=${esc(v)}`).join(" · ")}</div>
    </div>`).join("") : `<div class="empty">Nenhum alerta ainda. Você será avisado quando o preço cair.</div>`;
}

// ---------- Configurações
async function loadSettings() {
  const s = await api("/api/settings");
  const f = $("#settings-form");
  for (const [k, v] of Object.entries(s)) if (f.elements[k]) f.elements[k].value = Array.isArray(v) ? v.join("\n") : v ?? "";
}
$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  body.couponSources = body.couponSources.split("\n");
  body.searchSources = body.searchSources.split("\n");
  await busy(e.submitter, async () => { await api("/api/settings", { method: "PUT", body }); $("#settings-msg").textContent = "Salvo."; loadSettings(); });
});
$("#test-notify").addEventListener("click", (e) => busy(e.target, async () => {
  const r = await api("/api/notify/test", { method: "POST" });
  $("#settings-msg").textContent = "Resultado: " + Object.entries(r).map(([k, v]) => `${k}=${v}`).join(" · ");
}));

// ---------- Notificações em tempo real
const notifBtn = $("#notif-btn");
if ("Notification" in window && Notification.permission === "default") notifBtn.hidden = false;
notifBtn.addEventListener("click", async () => {
  const r = await Notification.requestPermission();
  notifBtn.hidden = r !== "default";
  if (r === "granted") toast("Notificações ativadas (com esta aba aberta).");
});

const events = new EventSource("/api/events");
events.addEventListener("product", (e) => upsert(JSON.parse(e.data)));
events.addEventListener("notification", (e) => {
  const n = JSON.parse(e.data);
  toast(`${n.title} — ${n.message}`);
  if ("Notification" in window && Notification.permission === "granted") {
    const notif = new Notification(n.title, { body: n.message, tag: n.productId || n.kind });
    if (n.url) notif.onclick = () => window.open(n.url, "_blank", "noopener");
  }
  if (!$("#tab-alerts").hidden) loadAlerts();
});

loadProducts().catch((e) => toast(e.message, true));
try { const t = localStorage.getItem("tab"); if (t && t !== "products") showTab(t); } catch {}
