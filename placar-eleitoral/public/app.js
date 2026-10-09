// Placar público: recebe atualizações em tempo real via Server-Sent Events.

const ICONES = {
  facebook: '<svg viewBox="0 0 24 24" fill="#1877f2"><path d="M24 12a12 12 0 1 0-13.9 11.9v-8.4H7.1V12h3V9.4c0-3 1.8-4.7 4.5-4.7 1.3 0 2.7.2 2.7.2v3h-1.5c-1.5 0-2 .9-2 1.9V12h3.4l-.5 3.5h-2.9v8.4A12 12 0 0 0 24 12z"/></svg>',
  instagram: '<svg viewBox="0 0 24 24" fill="none" stroke="#e1306c" stroke-width="2.2"><rect x="2" y="2" width="20" height="20" rx="6"/><circle cx="12" cy="12" r="4.5"/><circle cx="17.6" cy="6.4" r="1" fill="#e1306c"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="#fff"><path d="M18.2 2h3.4l-7.4 8.5L23 22h-6.8l-5.3-7-6.1 7H1.4l7.9-9L1 2h7l4.8 6.4L18.2 2zm-1.2 18h1.9L7.1 3.9H5.1L17 20z"/></svg>',
  tiktok: '<svg viewBox="0 0 24 24" fill="#fff"><path d="M16.6 2h-3.4v13.4a2.9 2.9 0 1 1-2-2.8V9.1a6.4 6.4 0 1 0 5.4 6.3V8.6a8 8 0 0 0 4.6 1.5V6.7a4.6 4.6 0 0 1-4.6-4.7z"/></svg>',
  youtube: '<svg viewBox="0 0 24 24"><path fill="#ff0000" d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8z"/><path fill="#fff" d="M9.6 15.6 15.8 12 9.6 8.4z"/></svg>',
};
const NOMES = { facebook: "Facebook", instagram: "Instagram", x: "X", tiktok: "TikTok", youtube: "YouTube" };
const ORDEM = ["facebook", "instagram", "x", "tiktok", "youtube"];

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("pt-BR");
const fmtPct = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// Foto: tenta img/<nome>.png, depois .jpg e .webp; se nenhuma existir, mostra uma silhueta.
function silhueta(img) {
  const lula = !!img.closest(".lula");
  const [c1, c2] = lula ? ["#ff6b74", "#3d0006"] : ["#6dffaa", "#00210d"];
  const id = lula ? "sl" : "sf";
  img.outerHTML = `<svg class="avatar" viewBox="0 0 80 100" preserveAspectRatio="xMidYMax meet" role="img" aria-label="${esc(img.alt)} (foto não adicionada)">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}" stop-opacity=".9"/><stop offset="1" stop-color="${c2}" stop-opacity=".9"/></linearGradient></defs>
    <ellipse cx="40" cy="34" rx="15" ry="18" fill="url(#${id})"/>
    <path d="M33 50h14v8l17 6c8 3 12 10 13 20v16H3V84c1-10 5-17 13-20l17-6z" fill="url(#${id})"/></svg>`;
}
document.querySelectorAll(".retrato img").forEach((img) => {
  const fila = (img.dataset.fontes || "").split(",").filter(Boolean);
  const proxima = () => (fila.length ? (img.src = fila.shift()) : silhueta(img));
  img.addEventListener("error", proxima);
  img.addEventListener("load", () => img.closest(".retrato").classList.add("com-foto"));
  if (img.complete && img.naturalWidth) img.closest(".retrato").classList.add("com-foto");
  if (img.complete && !img.naturalWidth) proxima();
});

// Animação de contagem dos números.
const atuais = new Map();
function animar(el, alvo, formato = (n) => fmt.format(Math.round(n))) {
  const de = atuais.get(el) ?? 0;
  atuais.set(el, alvo);
  if (de === alvo) { el.textContent = formato(alvo); return; }
  const inicio = performance.now();
  const dur = 700;
  const passo = (t) => {
    const p = Math.min(1, (t - inicio) / dur);
    const e = 1 - Math.pow(1 - p, 3);
    el.textContent = formato(de + (alvo - de) * e);
    if (p < 1) requestAnimationFrame(passo);
  };
  requestAnimationFrame(passo);
}

function pulsar(id) {
  const el = $(id);
  el.classList.add("pulsou");
  setTimeout(() => el.classList.remove("pulsou"), 250);
}

function tempoRelativo(iso) {
  if (!iso) return "nunca";
  const s = Math.round((Date.now() - new Date(iso)) / 1000);
  if (s < 5) return "agora";
  if (s < 60) return `há ${s}s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

let anterior = null;
let ultimo = null;
function render(d) {
  ultimo = d;
  const { totais } = d;
  if (anterior) {
    if (totais.lula > anterior.lula) pulsar("card-lula");
    if (totais.flavio > anterior.flavio) pulsar("card-flavio");
  }
  anterior = totais;

  animar($("votos-lula"), totais.lula);
  animar($("votos-flavio"), totais.flavio);
  animar($("pct-lula"), totais.pctLula, (n) => fmtPct.format(n));
  animar($("pct-flavio"), totais.pctFlavio, (n) => fmtPct.format(n));
  animar($("total-comentarios"), totais.total);
  $("ignorados").textContent = fmt.format(totais.ignorados);

  const pl = totais.total ? totais.pctLula : 50;
  const pf = totais.total ? totais.pctFlavio : 50;
  $("barra-lula").style.width = `${pl}%`;
  $("barra-flavio").style.width = `${pf}%`;
  $("barra-lula-txt").textContent = pl >= 8 ? `${fmtPct.format(pl)}%` : "";
  $("barra-flavio-txt").textContent = pf >= 8 ? `${fmtPct.format(pf)}%` : "";
  const dif = totais.lula - totais.flavio;
  $("diferenca").textContent = totais.total === 0 ? "Aguardando votos" : dif === 0 ? "Empate" :
    `${dif > 0 ? "Lula" : "Flávio"} lidera por ${fmt.format(Math.abs(dif))} voto${Math.abs(dif) === 1 ? "" : "s"}`;

  // Por rede
  const redes = ORDEM.filter((r) => d.porRede[r] || r !== "youtube");
  $("redes").innerHTML = redes.map((r) => {
    const v = d.porRede[r] || { lula: 0, flavio: 0, postagens: 0 };
    const t = v.lula + v.flavio;
    const l = t ? (v.lula / t) * 100 : 0;
    return `<div class="rede">
      <div class="nome">${ICONES[r]} ${NOMES[r]}</div>
      <div class="nums"><span class="l"><b>${fmt.format(v.lula)}</b>${t ? ` · ${fmtPct.format(l)}%` : ""}</span><span class="f">${t ? `${fmtPct.format(100 - l)}% · ` : ""}<b>${fmt.format(v.flavio)}</b></span></div>
      <div class="mini-barra"><i class="l" style="width:${t ? l : 0}%"></i><i class="f" style="width:${t ? 100 - l : 0}%"></i></div>
      <div class="qtd">${v.postagens} postage${v.postagens === 1 ? "m" : "ns"} · ${fmt.format(t)} votos</div>
    </div>`;
  }).join("");

  // Postagens
  $("postagens").innerHTML = d.postagens.length ? d.postagens.map((p) => `
    <li>
      <span class="icone-rede" title="${NOMES[p.rede]}">${ICONES[p.rede]}</span>
      <span class="info">
        <a class="titulo" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.titulo || p.url)}</a>
        <span class="meta">${p.demo ? "simulação" : p.erro ? "⚠ aguardando dados" : `sincronizado ${tempoRelativo(p.ultimaSync)}`}</span>
      </span>
      <span class="placar"><span class="l">${fmt.format(p.votos.lula)}</span> × <span class="f">${fmt.format(p.votos.flavio)}</span></span>
    </li>`).join("") : `<li class="vazio">Nenhuma postagem ainda. Adicione links no&nbsp;<a href="/admin">painel</a>.</li>`;

  // Feed
  $("feed").innerHTML = d.feed.length ? d.feed.slice(0, 25).map((f) => `
    <li>
      <span class="tag ${f.voto}">${f.voto === "lula" ? "13" : "22"}</span>
      <span class="icone-rede" title="${NOMES[f.rede]}">${ICONES[f.rede]}</span>
      <span class="txt" title="${esc(f.texto)}">${esc(f.texto)}</span>
      <span class="quando">${tempoRelativo(f.em)}</span>
    </li>`).join("") : `<li class="vazio">Aguardando comentários…</li>`;

  $("atualizado").textContent = new Date(d.atualizadoEm).toLocaleTimeString("pt-BR");
}

// No Firebase Hosting o placar vem direto do Firestore (documento placar/resumo), em tempo real.
const VAZIO = { totais: { lula: 0, flavio: 0, ignorados: 0, total: 0, pctLula: 0, pctFlavio: 0 }, porRede: {}, postagens: [], feed: [] };
function carregarScript(src) {
  return new Promise((ok, falha) => {
    const s = document.createElement("script");
    s.src = src; s.onload = ok; s.onerror = falha;
    document.head.appendChild(s);
  });
}
async function conectarFirebase(aoVivo) {
  let config;
  try {
    const r = await fetch("/__/firebase/init.json");
    if (!r.ok) return false;
    config = await r.json();
  } catch { return false; }
  const versao = "10.14.1";
  await carregarScript(`https://www.gstatic.com/firebasejs/${versao}/firebase-app-compat.js`);
  await carregarScript(`https://www.gstatic.com/firebasejs/${versao}/firebase-firestore-compat.js`);
  firebase.initializeApp(config);
  firebase.firestore().doc("placar/resumo").onSnapshot(
    (s) => { aoVivo.classList.remove("desconectado"); render({ ...VAZIO, atualizadoEm: new Date().toISOString(), ...(s.data() || {}) }); },
    () => aoVivo.classList.add("desconectado"),
  );
  return true;
}

// Conexão em tempo real (reconecta sozinha; cai para polling se SSE não existir).
async function conectar() {
  const aoVivo = document.querySelector(".ao-vivo");
  if (await conectarFirebase(aoVivo)) return;
  if (!("EventSource" in window)) {
    const buscar = () => fetch("/api/placar").then((r) => r.json()).then(render).catch(() => {});
    buscar();
    setInterval(buscar, 5000);
    return;
  }
  const es = new EventSource("/api/eventos");
  es.addEventListener("placar", (e) => { aoVivo.classList.remove("desconectado"); render(JSON.parse(e.data)); });
  es.onerror = () => aoVivo.classList.add("desconectado");
}
conectar();
// Atualiza os "há X min" mesmo sem votos novos.
setInterval(() => ultimo && render(ultimo), 30000);

// Testar um comentário
$("form-testar").addEventListener("submit", async (e) => {
  e.preventDefault();
  const texto = $("texto-teste").value.trim();
  if (!texto) return;
  const r = await fetch("/api/testar", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ texto }) }).then((x) => x.json());
  $("resultado-teste").innerHTML = r.voto
    ? `Conta <span class="${r.voto}">1 voto para ${r.voto === "lula" ? "Lula (13)" : "Flávio (22)"}</span> — ${esc(r.termos.join(", "))}`
    : `Não conta voto: ${esc(r.motivo)}${r.termos.length ? ` — ${esc(r.termos.join(", "))}` : ""}`;
});
