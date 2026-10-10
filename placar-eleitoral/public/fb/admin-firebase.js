// Painel no plano gratuito do Firebase (Spark): sem Cloud Functions.
// O próprio painel faz o trabalho do servidor: grava no Firestore (com login do admin)
// e, enquanto estiver aberto, lê os comentários nas APIs que aceitam chamadas do navegador
// (YouTube, Facebook e Instagram). X e TikTok ficam com importação manual.
//
// Os arquivos de ./lib/ são copiados de lib/ no deploy (veja firebase.json).

const V = "10.14.1";
const { initializeApp } = await import(`https://www.gstatic.com/firebasejs/${V}/firebase-app.js`);
const { getAuth, signInWithEmailAndPassword, signOut } = await import(`https://www.gstatic.com/firebasejs/${V}/firebase-auth.js`);
const {
  getFirestore, doc, collection, getDoc, getDocs, runTransaction, onSnapshot, deleteDoc, writeBatch,
} = await import(`https://www.gstatic.com/firebasejs/${V}/firebase-firestore.js`);

// Os conectores leem as chaves de process.env; no navegador elas vêm do localStorage deste computador.
const CHAVES = ["YOUTUBE_API_KEY", "FACEBOOK_PAGE_TOKEN", "FACEBOOK_PAGE_ID", "INSTAGRAM_TOKEN", "INSTAGRAM_BUSINESS_ID"];
globalThis.process = { env: {} };
export function carregarChaves() {
  for (const k of CHAVES) {
    let v = "";
    try { v = localStorage.getItem(`placar-chave-${k}`) || ""; } catch {}
    if (v) process.env[k] = v; else delete process.env[k];
  }
  return { ...process.env };
}
export function salvarChaves(valores) {
  for (const k of CHAVES) {
    try {
      if (valores[k]) localStorage.setItem(`placar-chave-${k}`, valores[k].trim());
      else localStorage.removeItem(`placar-chave-${k}`);
    } catch {}
  }
  carregarChaves();
}
carregarChaves();

const { classificar } = await import("./lib/classifier.js");
const { analisarLink, REDES } = await import("./lib/links.js");
const { CONECTORES, credenciaisConfiguradas } = await import("./lib/connectors/index.js");
const { aplicarComentarios, distribuirEmPedacos, montarResumo, postagemPublica, TAMANHO_FEED } = await import("./lib/contagem.js");

const config = await fetch("/__/firebase/init.json").then((r) => r.json());
const app = initializeApp(config);
const auth = getAuth(app);
const db = getFirestore(app);
const RESUMO = doc(db, "placar", "resumo");
const POSTAGENS = collection(db, "postagens");
export const EMAIL_ADMIN = "admin@placar-das-redes.app";
export const INTERVALO_SEGUNDOS = 120;

// Só estas redes aceitam chamadas direto do navegador.
const REDES_NO_NAVEGADOR = ["youtube", "facebook", "instagram"];
function credenciais() {
  const c = credenciaisConfiguradas();
  for (const r of Object.keys(c)) if (!REDES_NO_NAVEGADOR.includes(r)) c[r] = false;
  return c;
}

const lerResumo = async (t) => {
  const s = await t.get(RESUMO);
  return s.exists() ? s.data() : { postagens: [], feed: [] };
};
const nomePedaco = (i) => String(i).padStart(4, "0");

// ---------------- Operações (as mesmas das Cloud Functions) ----------------

async function adicionarPostagem(info) {
  return runTransaction(db, async (t) => {
    const r = await lerResumo(t);
    if (r.postagens.some((p) => p.url === info.url)) throw new Error("Essa postagem já está no placar.");
    const ref = doc(POSTAGENS);
    const post = {
      url: info.url, rede: info.rede, idPostagem: info.idPostagem || null, idApi: info.idApi || null,
      titulo: info.titulo || "", criadoEm: new Date().toISOString(), ultimaSync: null, erro: null,
      votos: { lula: 0, flavio: 0, ignorados: 0 }, estado: {}, pedacos: 0,
    };
    t.set(ref, post);
    t.set(RESUMO, montarResumo([...r.postagens, postagemPublica(ref.id, post)], r.feed));
    return { id: ref.id, ...post };
  });
}

async function removerPostagem(id) {
  const ref = doc(POSTAGENS, id);
  const s = await getDoc(ref);
  if (!s.exists()) return false;
  await runTransaction(db, async (t) => {
    const r = await lerResumo(t);
    t.set(RESUMO, montarResumo(r.postagens.filter((p) => p.id !== id), r.feed.filter((f) => f.postagem !== id)));
  });
  const lote = writeBatch(db);
  for (const d of (await getDocs(collection(ref, "vistos"))).docs) lote.delete(d.ref);
  await lote.commit();
  await deleteDoc(ref);
  return true;
}

async function registrarErro(id, erro) {
  const ref = doc(POSTAGENS, id);
  const mensagem = erro ? String(erro.message || erro) : null;
  await runTransaction(db, async (t) => {
    const s = await t.get(ref);
    if (!s.exists() || s.data().erro === mensagem) return; // nada mudou: não gasta escrita
    const r = await lerResumo(t);
    const mudanca = { erro: mensagem, ultimaSync: new Date().toISOString() };
    t.update(ref, mudanca);
    t.set(RESUMO, montarResumo(r.postagens.map((p) => (p.id === id ? { ...p, ...mudanca } : p)), r.feed));
  });
}

async function registrarComentarios(id, comentarios, estado) {
  const ref = doc(POSTAGENS, id);
  return runTransaction(db, async (t) => {
    const s = await t.get(ref);
    if (!s.exists()) throw new Error("Postagem não encontrada.");
    const post = s.data();
    const n = post.pedacos || 0;
    const pedacos = await Promise.all(Array.from({ length: n }, (_, i) => t.get(doc(ref, "vistos", nomePedaco(i)))));
    const r = await lerResumo(t);

    const vistos = new Set();
    const autores = new Set();
    for (const d of pedacos) {
      const dados = d.exists() ? d.data() : {};
      for (const k of Object.keys(dados.ids || {})) vistos.add(k);
      for (const a of Object.keys(dados.autores || {})) autores.add(a);
    }
    const res = aplicarComentarios({ vistos, autores, votos: post.votos, rede: post.rede, postagemId: id }, comentarios);
    const novoEstado = estado ? { ...(post.estado || {}), ...estado } : post.estado || {};
    const estadoMudou = JSON.stringify(novoEstado) !== JSON.stringify(post.estado || {});
    // Nada novo (nem votos, nem ponto de leitura): não gasta escrita.
    if (!res.novasChaves.length && !post.erro && !estadoMudou) return { novos: 0, votos: post.votos };

    const tamanhos = pedacos.map((d, i) => ({ id: nomePedaco(i), tamanho: Object.keys((d.exists() && d.data().ids) || {}).length }));
    const grupos = distribuirEmPedacos(tamanhos, res.novasChaves);
    for (const g of grupos) t.set(doc(ref, "vistos", g.id), { ids: Object.fromEntries(g.entradas) }, { merge: true });
    const totalPedacos = Math.max(n, ...grupos.map((g) => Number(g.id) + 1));

    const mudanca = { votos: res.votos, erro: null, ultimaSync: new Date().toISOString() };
    t.update(ref, { ...mudanca, pedacos: totalPedacos, estado: novoEstado });
    const postagens = r.postagens.map((p) => (p.id === id ? { ...p, ...mudanca } : p));
    t.set(RESUMO, montarResumo(postagens, [...res.feedNovo, ...r.feed].slice(0, TAMANHO_FEED)));
    return { novos: res.novos, votos: res.votos };
  });
}

async function sincronizar(id) {
  const s = await getDoc(doc(POSTAGENS, id));
  if (!s.exists()) return { erro: "Postagem não encontrada." };
  const post = { id, ...s.data() };
  if (!credenciais()[post.rede]) {
    const erro = REDES_NO_NAVEGADOR.includes(post.rede)
      ? "Chave desta rede não configurada neste computador. Use a importação manual ou preencha as chaves no painel."
      : `${REDES[post.rede]} não permite leitura pelo navegador. Use a importação manual.`;
    await registrarErro(id, erro);
    return { erro };
  }
  try {
    const { comentarios, estado } = await CONECTORES[post.rede](post);
    return await registrarComentarios(id, comentarios, estado);
  } catch (e) {
    await registrarErro(id, e);
    return { erro: e.message };
  }
}

async function linhasParaComentarios(texto) {
  const ocorrencias = {};
  const linhas = String(texto ?? "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const saida = [];
  for (const linha of linhas) {
    const bytes = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(linha));
    const h = [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
    ocorrencias[h] = (ocorrencias[h] || 0) + 1;
    saida.push({ id: `manual:${h}:${ocorrencias[h]}`, texto: linha, autor: null });
  }
  return saida;
}

// ---------------- Coleta automática enquanto o painel está aberto ----------------

// Se o coletor 24h (pasta coletor/) estiver rodando, ele cuida da leitura e o painel não coleta.
export const COLETOR = doc(db, "placar", "coletor");
export async function coletorAtivo() {
  try {
    const s = await getDoc(COLETOR);
    return s.exists() && Date.now() - Date.parse(s.data().ativoEm) < 5 * 60 * 1000;
  } catch { return false; }
}

let coletando = false;
async function ciclo() {
  if (coletando || !auth.currentUser) return;
  coletando = true;
  try {
    const status = document.getElementById("status-coleta");
    if (await coletorAtivo()) {
      if (status) status.textContent = "Coletor 24h ligado: ele está lendo as redes; este painel não precisa ficar aberto.";
      return;
    }
    if (status) status.textContent = "Coleta pelo painel ativa (enquanto esta página estiver aberta).";
    const cred = credenciais();
    const posts = await getDocs(POSTAGENS);
    for (const d of posts.docs) if (cred[d.data().rede]) await sincronizar(d.id);
  } finally {
    coletando = false;
  }
}
export function iniciarColeta() {
  setTimeout(ciclo, 3000);
  setInterval(ciclo, INTERVALO_SEGUNDOS * 1000);
}

// ---------------- Mesma interface do servidor: api(caminho, opcoes) ----------------

export async function api(caminho, opcoes = {}) {
  const metodo = opcoes.method || "GET";
  const corpo = opcoes.body ? JSON.parse(opcoes.body) : {};
  const naoAutorizado = () => Object.assign(new Error("Senha inválida."), { status: 401 });

  if (metodo === "POST" && caminho === "/api/testar") return classificar(corpo.texto);
  if (caminho === "/api/admin/verificar") {
    if (!corpo.senha) throw naoAutorizado();
    try { await signInWithEmailAndPassword(auth, EMAIL_ADMIN, corpo.senha); } catch { throw naoAutorizado(); }
    return { ok: true };
  }
  if (!auth.currentUser) throw naoAutorizado();

  if (metodo === "POST" && caminho === "/api/postagens") {
    const info = analisarLink(corpo.url);
    const post = await adicionarPostagem({ ...info, titulo: corpo.titulo, idApi: corpo.idApi });
    if (credenciais()[post.rede]) sincronizar(post.id);
    return { postagem: post.id, rede: REDES[post.rede], idPostagem: post.idPostagem };
  }
  const m = caminho.match(/^\/api\/postagens\/([\w-]+)(\/[a-z]+)?$/);
  if (m) {
    const [, id, acao] = m;
    if (metodo === "DELETE" && !acao) {
      if (!(await removerPostagem(id))) throw new Error("Postagem não encontrada.");
      return { ok: true };
    }
    if (metodo === "POST" && acao === "/sincronizar") {
      const r = await sincronizar(id);
      if (r.erro) throw new Error(r.erro);
      return { ok: true, ...r };
    }
    if (metodo === "POST" && acao === "/comentarios") {
      const comentarios = await linhasParaComentarios(corpo.texto);
      return { lidos: comentarios.length, ...(await registrarComentarios(id, comentarios)) };
    }
  }
  throw new Error("Ação não reconhecida.");
}

/** Placar ao vivo para o painel (sem ficar consultando a cada poucos segundos). */
export function ouvir(render) {
  return onSnapshot(RESUMO, (s) => {
    render({
      ...montarResumo([], []),
      ...(s.exists() ? s.data() : {}),
      credenciais: credenciais(),
      intervalo: INTERVALO_SEGUNDOS,
    });
  });
}

export async function sair() {
  await signOut(auth);
}
