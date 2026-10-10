// Coletor 24h: roda no seu computador (de graça), lê os comentários nas APIs das redes
// e atualiza o placar no Firebase. Substitui a coleta pelo painel aberto no navegador.
//
//   cd placar-eleitoral/coletor
//   npm install
//   copie .env.example para .env e preencha
//   npm start
//
// Os IDs dos comentários já contados ficam em coletor/dados/<postagem>.txt, então
// posts com centenas de milhares de comentários não gastam leituras do Firebase.

import { readFileSync, existsSync, mkdirSync, appendFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const PASTA_DADOS = join(AQUI, "dados");

function carregarEnv(arquivo) {
  if (!existsSync(arquivo)) return;
  for (const linha of readFileSync(arquivo, "utf8").split(/\r?\n/)) {
    const m = linha.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}
carregarEnv(join(AQUI, ".env"));
// A cota grátis do YouTube é de 10 mil páginas por dia: 6 páginas por minuto cabem nela.
process.env.YOUTUBE_PAGINAS_POR_SYNC ||= "6";

const { initializeApp } = await import("firebase/app");
const { getAuth, signInWithEmailAndPassword } = await import("firebase/auth");
const { getFirestore, doc, collection, getDocs, onSnapshot, runTransaction, setDoc } = await import("firebase/firestore");
const { CONECTORES, credenciaisConfiguradas } = await import("../lib/connectors/index.js");
const { aplicarComentarios, distribuirEmPedacos, montarResumo, chaveSegura, TAMANHO_FEED, MAX_POR_PEDACO } = await import("../lib/contagem.js");

const nomePedaco = (i) => String(i).padStart(4, "0");
const agoraTxt = () => new Date().toLocaleTimeString("pt-BR");

/** Monta o coletor sobre um Firestore já autenticado como admin. */
export function criarColetor(db, { conectores = CONECTORES, credenciais = credenciaisConfiguradas, pasta = PASTA_DADOS, log = console.log } = {}) {
  const RESUMO = doc(db, "placar", "resumo");
  const COLETOR = doc(db, "placar", "coletor");
  const POSTAGENS = collection(db, "postagens");
  const caches = new Map(); // postagem -> Set de chaves já contadas
  mkdirSync(pasta, { recursive: true });

  /** Chaves já contadas: arquivo local + pedaços no Firestore (contagens feitas pelo painel). */
  async function cache(id) {
    if (caches.has(id)) return caches.get(id);
    const vistos = new Set();
    const arquivo = join(pasta, `${id}.txt`);
    if (existsSync(arquivo)) for (const l of readFileSync(arquivo, "utf8").split("\n")) if (l) vistos.add(l);
    const antes = vistos.size;
    for (const d of (await getDocs(collection(POSTAGENS, id, "vistos"))).docs) {
      for (const k of Object.keys(d.data().ids || {})) vistos.add(k);
    }
    if (vistos.size > antes) appendFileSync(arquivo, [...vistos].slice(antes).join("\n") + "\n");
    caches.set(id, vistos);
    return vistos;
  }

  async function registrarErro(id, erro) {
    const ref = doc(POSTAGENS, id);
    const mensagem = erro ? String(erro.message || erro) : null;
    await runTransaction(db, async (t) => {
      const s = await t.get(ref);
      if (!s.exists() || s.data().erro === mensagem) return;
      const r = await t.get(RESUMO);
      const resumo = r.exists() ? r.data() : { postagens: [], feed: [] };
      const mudanca = { erro: mensagem, ultimaSync: new Date().toISOString() };
      t.update(ref, mudanca);
      t.set(RESUMO, montarResumo(resumo.postagens.map((p) => (p.id === id ? { ...p, ...mudanca } : p)), resumo.feed));
    });
  }

  /** Lê uma postagem na rede e grava os votos novos. Devolve quantos votos entraram. */
  async function sincronizar(id, post) {
    const vistos = await cache(id);
    let resultado;
    try {
      resultado = await conectores[post.rede]({ id, ...post });
    } catch (e) {
      await registrarErro(id, e);
      log(`[${agoraTxt()}] ${post.rede} ${post.titulo || id}: ${e.message}`);
      return 0;
    }
    const { comentarios, estado } = resultado;
    const novosComentarios = comentarios.filter((c) => !vistos.has(chaveSegura(c.id)));
    const novoEstado = { ...(post.estado || {}), ...(estado || {}) };
    const estadoMudou = JSON.stringify(novoEstado) !== JSON.stringify(post.estado || {});
    if (!novosComentarios.length && !estadoMudou && !post.erro) return 0;

    const ref = doc(POSTAGENS, id);
    const res = await runTransaction(db, async (t) => {
      const s = await t.get(ref);
      if (!s.exists()) return null; // removida no painel
      const atual = s.data();
      const n = atual.pedacos || 0;
      const ultimo = n ? await t.get(doc(ref, "vistos", nomePedaco(n - 1))) : null;
      const r = await t.get(RESUMO);
      const resumo = r.exists() ? r.data() : { postagens: [], feed: [] };

      const res = aplicarComentarios({ vistos, autores: new Set(), votos: atual.votos, rede: atual.rede, postagemId: id }, novosComentarios);
      // Só o último pedaço importa para saber onde cabem as novas chaves.
      const tamanhos = Array.from({ length: n }, (_, i) => ({
        id: nomePedaco(i),
        tamanho: i < n - 1 ? MAX_POR_PEDACO : Object.keys((ultimo?.exists() && ultimo.data().ids) || {}).length,
      }));
      const grupos = distribuirEmPedacos(tamanhos, res.novasChaves);
      for (const g of grupos) t.set(doc(ref, "vistos", g.id), { ids: Object.fromEntries(g.entradas) }, { merge: true });

      const mudanca = { votos: res.votos, erro: null, ultimaSync: new Date().toISOString() };
      t.update(ref, { ...mudanca, estado: novoEstado, pedacos: Math.max(n, ...grupos.map((g) => Number(g.id) + 1)) });
      t.set(RESUMO, montarResumo(
        resumo.postagens.map((p) => (p.id === id ? { ...p, ...mudanca } : p)),
        [...res.feedNovo, ...resumo.feed].slice(0, TAMANHO_FEED),
      ));
      return res;
    });
    if (!res) return 0;

    // Só depois de gravado no Firebase entra no arquivo local.
    if (res.novasChaves.length) {
      for (const [k] of res.novasChaves) vistos.add(k);
      appendFileSync(join(pasta, `${id}.txt`), res.novasChaves.map(([k]) => k).join("\n") + "\n");
    }
    if (res.novos || res.novasChaves.length) {
      log(`[${agoraTxt()}] ${post.rede} ${post.titulo || id}: ${res.novasChaves.length} comentário(s) lido(s), +${res.novos} voto(s) · total ${res.votos.lula} × ${res.votos.flavio}`);
    }
    return res.novos;
  }

  const postagens = new Map();
  let pararOuvir = null;
  function ouvirPostagens() {
    return new Promise((pronto) => {
      pararOuvir = onSnapshot(POSTAGENS, (snap) => {
        for (const m of snap.docChanges()) {
          if (m.type === "removed") { postagens.delete(m.doc.id); caches.delete(m.doc.id); }
          else postagens.set(m.doc.id, m.doc.data());
        }
        pronto();
      });
    });
  }

  let rodando = false;
  async function ciclo() {
    if (rodando) return;
    rodando = true;
    try {
      const cred = credenciais();
      await setDoc(COLETOR, { ativoEm: new Date().toISOString(), redes: Object.keys(cred).filter((r) => cred[r]) });
      for (const [id, post] of postagens) {
        if (cred[post.rede] && conectores[post.rede]) await sincronizar(id, post);
      }
    } catch (e) {
      log(`[${agoraTxt()}] Erro no ciclo: ${e.message}`);
    } finally {
      rodando = false;
    }
  }

  return { ouvirPostagens, ciclo, sincronizar, parar: () => pararOuvir?.(), postagens };
}

async function principal() {
  const site = process.env.SITE || "https://placar-das-redes-d045b.web.app";
  const config = process.env.FIREBASE_CONFIG_ARQUIVO
    ? JSON.parse(readFileSync(process.env.FIREBASE_CONFIG_ARQUIVO, "utf8"))
    : await fetch(`${site}/__/firebase/init.json`).then((r) => {
      if (!r.ok) throw new Error(`Não consegui ler a configuração do Firebase em ${site} (HTTP ${r.status}).`);
      return r.json();
    });
  if (!process.env.ADMIN_SENHA) throw new Error("Defina ADMIN_SENHA no arquivo coletor/.env (a mesma senha do painel).");

  const app = initializeApp(config);
  await signInWithEmailAndPassword(getAuth(app), process.env.ADMIN_EMAIL || "admin@placar-das-redes.app", process.env.ADMIN_SENHA)
    .catch(() => { throw new Error("Senha do painel incorreta (ADMIN_SENHA no .env)."); });
  const coletor = criarColetor(getFirestore(app));

  const cred = credenciaisConfiguradas();
  const ativas = Object.keys(cred).filter((r) => cred[r]);
  const intervalo = Math.max(30, Number(process.env.INTERVALO_SEGUNDOS || 60));
  console.log(`\n  Coletor do Placar das Redes ligado (${config.projectId})`);
  console.log(`  Redes com chave: ${ativas.length ? ativas.join(", ") : "nenhuma (preencha o .env)"}`);
  console.log(`  Lendo a cada ${intervalo}s. Deixe esta janela aberta; Ctrl+C para parar.\n`);

  await coletor.ouvirPostagens();
  if (process.argv.includes("--uma-vez")) {
    await coletor.ciclo();
    coletor.parar();
    process.exit(0);
  }
  await coletor.ciclo();
  setInterval(coletor.ciclo, intervalo * 1000);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  principal().catch((e) => {
    console.error(`\n  Erro: ${e.message}\n`);
    process.exit(1);
  });
}
