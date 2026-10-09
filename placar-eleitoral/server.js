import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { extname, join, normalize, dirname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { Store } from "./lib/store.js";
import { classificar } from "./lib/classifier.js";
import { analisarLink, resolverLinkCurto, REDES } from "./lib/links.js";
import { CONECTORES, credenciaisConfiguradas } from "./lib/connectors/index.js";
import { iniciarDemo } from "./lib/demo.js";

const RAIZ = dirname(fileURLToPath(import.meta.url));

// Carrega .env simples (CHAVE=valor) se existir, sem dependências externas.
const arquivoEnv = join(RAIZ, ".env");
if (existsSync(arquivoEnv)) {
  for (const linha of readFileSync(arquivoEnv, "utf8").split(/\r?\n/)) {
    const m = linha.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

const PORTA = Number(process.env.PORT || 3000);
const INTERVALO = Math.max(10, Number(process.env.SYNC_INTERVAL_SECONDS || 30)) * 1000;
const DEMO = process.env.DEMO === "1";
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || randomBytes(9).toString("base64url");

const store = new Store(join(RAIZ, "data", DEMO ? "demo.json" : "placar.json"), {
  umVotoPorPessoa: process.env.ONE_VOTE_PER_USER === "1",
});

// ---------------- Sincronização periódica ----------------
const sincronizando = new Set();

async function sincronizar(post) {
  if (post.demo || sincronizando.has(post.id)) return;
  const conector = CONECTORES[post.rede];
  if (!conector) return;
  sincronizando.add(post.id);
  try {
    const { comentarios, estado } = await conector(post);
    const novos = store.registrarComentarios(post, comentarios, estado);
    if (novos) console.log(`[${post.rede}] ${post.id}: +${novos} voto(s)`);
  } catch (e) {
    store.registrarErro(post, e);
    if (!e.semCredencial) console.warn(`[${post.rede}] ${post.id}: ${e.message}`);
  } finally {
    sincronizando.delete(post.id);
  }
}

async function cicloSincronizacao() {
  const cred = credenciaisConfiguradas();
  for (const post of store.db.postagens) {
    if (cred[post.rede]) await sincronizar(post);
  }
}
setInterval(cicloSincronizacao, INTERVALO);
setTimeout(cicloSincronizacao, 2000);
if (DEMO) iniciarDemo(store);

// ---------------- Tempo real (Server-Sent Events) ----------------
const clientes = new Set();
let envioAgendado = null;
function payloadPlacar() {
  return { ...store.resumo(), credenciais: credenciaisConfiguradas(), intervalo: INTERVALO / 1000, demo: DEMO };
}
store.on("mudou", () => {
  if (envioAgendado) return;
  envioAgendado = setTimeout(() => {
    envioAgendado = null;
    const dados = `event: placar\ndata: ${JSON.stringify(payloadPlacar())}\n\n`;
    for (const res of clientes) res.write(dados);
  }, 300);
});
setInterval(() => { for (const res of clientes) res.write(": ping\n\n"); }, 25000);

// ---------------- HTTP ----------------
const TIPOS = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  ".ico": "image/x-icon", ".json": "application/json",
};

function json(res, status, corpo) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  res.end(JSON.stringify(corpo));
}

async function lerCorpo(req) {
  let tam = 0;
  const partes = [];
  for await (const p of req) {
    tam += p.length;
    if (tam > 5_000_000) throw new Error("Corpo da requisição muito grande (máx. 5 MB).");
    partes.push(p);
  }
  const txt = Buffer.concat(partes).toString("utf8");
  return txt ? JSON.parse(txt) : {};
}

function autorizado(req) {
  const enviado = Buffer.from(String(req.headers["x-admin-token"] || ""));
  const esperado = Buffer.from(ADMIN_TOKEN);
  return enviado.length === esperado.length && timingSafeEqual(enviado, esperado);
}

async function api(req, res, caminho) {
  const metodo = req.method;

  if (metodo === "GET" && caminho === "/api/placar") return json(res, 200, payloadPlacar());

  if (metodo === "GET" && caminho === "/api/eventos") {
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
    res.write(`event: placar\ndata: ${JSON.stringify(payloadPlacar())}\n\n`);
    clientes.add(res);
    req.on("close", () => clientes.delete(res));
    return;
  }

  if (metodo === "POST" && caminho === "/api/testar") {
    const { texto } = await lerCorpo(req);
    return json(res, 200, classificar(texto));
  }

  // ----- Rotas administrativas -----
  if (!autorizado(req)) return json(res, 401, { erro: "Token de administrador inválido." });

  if (metodo === "GET" && caminho === "/api/admin/verificar") return json(res, 200, { ok: true });

  if (metodo === "POST" && caminho === "/api/postagens") {
    const { url, titulo, idApi } = await lerCorpo(req);
    let info = analisarLink(url);
    if (!info.idPostagem && info.curto) {
      try { info = { ...analisarLink(await resolverLinkCurto(info.url)), url: info.url }; } catch { /* mantém sem ID */ }
    }
    const post = store.adicionarPostagem({ ...info, titulo, idApi });
    if (credenciaisConfiguradas()[post.rede]) sincronizar(post);
    return json(res, 201, { postagem: post.id, rede: REDES[post.rede], idPostagem: post.idPostagem });
  }

  let m = caminho.match(/^\/api\/postagens\/([\w-]+)(\/[a-z]+)?$/);
  if (m) {
    const post = store.postagem(m[1]);
    if (!post) return json(res, 404, { erro: "Postagem não encontrada." });
    const acao = m[2];
    if (metodo === "DELETE" && !acao) {
      store.removerPostagem(post.id);
      return json(res, 200, { ok: true });
    }
    if (metodo === "POST" && acao === "/sincronizar") {
      await sincronizar(post);
      return json(res, post.erro ? 502 : 200, { ok: !post.erro, erro: post.erro, votos: post.votos });
    }
    if (metodo === "POST" && acao === "/comentarios") {
      const { texto } = await lerCorpo(req);
      return json(res, 200, { ...store.importarTexto(post, texto), votos: post.votos });
    }
  }

  return json(res, 404, { erro: "Rota não encontrada." });
}

const servidor = createServer(async (req, res) => {
  const { pathname } = new URL(req.url, "http://localhost");
  try {
    if (pathname.startsWith("/api/")) return await api(req, res, pathname);

    const arquivo = pathname === "/" ? "index.html" : pathname === "/admin" ? "admin.html" : pathname.slice(1);
    const completo = normalize(join(RAIZ, "public", arquivo));
    if (!completo.startsWith(join(RAIZ, "public") + sep)) return json(res, 403, { erro: "Proibido" });
    const conteudo = await readFile(completo);
    res.writeHead(200, { "content-type": TIPOS[extname(completo)] || "application/octet-stream" });
    res.end(conteudo);
  } catch (e) {
    if (e.code === "ENOENT" || e.code === "EISDIR") return json(res, 404, { erro: "Não encontrado" });
    json(res, 400, { erro: e.message });
  }
});

servidor.listen(PORTA, () => {
  console.log(`\n  Placar no ar:   http://localhost:${PORTA}`);
  console.log(`  Painel admin:   http://localhost:${PORTA}/admin`);
  console.log(`  Token admin:    ${ADMIN_TOKEN}${process.env.ADMIN_TOKEN ? " (de ADMIN_TOKEN)" : " (gerado agora; defina ADMIN_TOKEN para fixar)"}`);
  console.log(`  Sincronização:  a cada ${INTERVALO / 1000}s${DEMO ? "  |  MODO DEMO (comentários simulados)" : ""}\n`);
});

for (const sinal of ["SIGINT", "SIGTERM"]) {
  process.on(sinal, () => {
    store.salvarAgora();
    process.exit(0);
  });
}
