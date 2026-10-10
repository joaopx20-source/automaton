// Cloud Functions do Placar das Redes.
//  - api:        rotas /api/* usadas pelo painel (a Hosting redireciona /api/** para cá)
//  - sincronizar: roda a cada minuto e lê os comentários nas APIs das redes
// O placar público lê o documento placar/resumo direto do Firestore, em tempo real.

import { onRequest } from "firebase-functions/v2/https";
import { onSchedule } from "firebase-functions/v2/scheduler";
import { setGlobalOptions, logger } from "firebase-functions/v2";
import { initializeApp } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";
import { timingSafeEqual } from "node:crypto";

import { classificar } from "./lib/classifier.js";
import { analisarLink, resolverLinkCurto, REDES } from "./lib/links.js";
import { CONECTORES, credenciaisConfiguradas } from "./lib/connectors/index.js";
import {
  aplicarComentarios, distribuirEmPedacos, montarResumo, postagemPublica, linhasParaComentarios, TAMANHO_FEED,
} from "./lib/contagem.js";

setGlobalOptions({ region: "southamerica-east1", maxInstances: 3 });
initializeApp();
const db = getFirestore();
const RESUMO = db.doc("placar/resumo");
const POSTAGENS = db.collection("postagens");
const INTERVALO_SEGUNDOS = 60;

const umVotoPorPessoa = () => process.env.ONE_VOTE_PER_USER === "1";
const lerResumo = async (t) => {
  const s = await t.get(RESUMO);
  return s.exists ? s.data() : { postagens: [], feed: [] };
};

// ---------------- Operações no Firestore ----------------

async function adicionarPostagem(info) {
  return db.runTransaction(async (t) => {
    const r = await lerResumo(t);
    if (r.postagens.some((p) => p.url === info.url)) throw new Error("Essa postagem já está no placar.");
    const ref = POSTAGENS.doc();
    const post = {
      url: info.url, rede: info.rede, idPostagem: info.idPostagem || null, idApi: info.idApi || null,
      titulo: info.titulo || "", criadoEm: new Date().toISOString(), ultimaSync: null, erro: null,
      votos: { lula: 0, flavio: 0, ignorados: 0 }, estado: {},
    };
    t.set(ref, post);
    t.set(RESUMO, montarResumo([...r.postagens, postagemPublica(ref.id, post)], r.feed));
    return { id: ref.id, ...post };
  });
}

async function removerPostagem(id) {
  const ref = POSTAGENS.doc(id);
  const existe = await db.runTransaction(async (t) => {
    const s = await t.get(ref);
    if (!s.exists) return false;
    const r = await lerResumo(t);
    t.set(RESUMO, montarResumo(r.postagens.filter((p) => p.id !== id), r.feed.filter((f) => f.postagem !== id)));
    return true;
  });
  if (existe) await db.recursiveDelete(ref);
  return existe;
}

async function registrarErro(id, erro) {
  const ref = POSTAGENS.doc(id);
  await db.runTransaction(async (t) => {
    const s = await t.get(ref);
    if (!s.exists) return;
    const r = await lerResumo(t);
    const mudanca = { erro: erro ? String(erro.message || erro) : null, ultimaSync: new Date().toISOString() };
    t.update(ref, mudanca);
    t.set(RESUMO, montarResumo(r.postagens.map((p) => (p.id === id ? { ...p, ...mudanca } : p)), r.feed));
  });
}

/** Conta os comentários novos de uma postagem numa transação (sem duplicar votos). */
async function registrarComentarios(id, comentarios, estado) {
  const ref = POSTAGENS.doc(id);
  const pedacosRef = ref.collection("vistos");
  return db.runTransaction(async (t) => {
    const s = await t.get(ref);
    if (!s.exists) throw new Error("Postagem não encontrada.");
    const post = s.data();
    const pedacos = (await t.get(pedacosRef)).docs; // já vem ordenado pelo ID (0000, 0001…)
    const r = await lerResumo(t);

    const vistos = new Set();
    const autores = new Set();
    for (const d of pedacos) {
      for (const k of Object.keys(d.get("ids") || {})) vistos.add(k);
      for (const a of Object.keys(d.get("autores") || {})) autores.add(a);
    }

    const res = aplicarComentarios(
      { vistos, autores, votos: post.votos, rede: post.rede, postagemId: id },
      comentarios,
      { umVotoPorPessoa: umVotoPorPessoa() },
    );

    const tamanhos = pedacos.map((d) => ({ id: d.id, tamanho: Object.keys(d.get("ids") || {}).length }));
    const grupos = distribuirEmPedacos(tamanhos, res.novasChaves);
    grupos.forEach((g, i) => {
      const dados = { ids: Object.fromEntries(g.entradas) };
      // Autores novos vão junto do primeiro pedaço escrito.
      if (i === 0 && res.novosAutores.length) dados.autores = Object.fromEntries(res.novosAutores.map((a) => [a, 1]));
      t.set(pedacosRef.doc(g.id), dados, { merge: true });
    });
    if (!grupos.length && res.novosAutores.length) {
      t.set(pedacosRef.doc(tamanhos.at(-1)?.id ?? "0000"), { autores: Object.fromEntries(res.novosAutores.map((a) => [a, 1])) }, { merge: true });
    }

    const mudanca = { votos: res.votos, erro: null, ultimaSync: new Date().toISOString() };
    t.update(ref, estado ? { ...mudanca, estado: { ...(post.estado || {}), ...estado } } : mudanca);
    const postagens = r.postagens.map((p) => (p.id === id ? { ...p, ...mudanca } : p));
    t.set(RESUMO, montarResumo(postagens, [...res.feedNovo, ...r.feed].slice(0, TAMANHO_FEED)));
    return { novos: res.novos, votos: res.votos };
  });
}

async function sincronizar(id) {
  const s = await POSTAGENS.doc(id).get();
  if (!s.exists) return { erro: "Postagem não encontrada." };
  const post = { id, ...s.data() };
  const conector = CONECTORES[post.rede];
  try {
    const { comentarios, estado } = await conector(post);
    const r = await registrarComentarios(id, comentarios, estado);
    if (r.novos) logger.info(`[${post.rede}] ${id}: +${r.novos} voto(s)`);
    return r;
  } catch (e) {
    await registrarErro(id, e);
    if (!e.semCredencial) logger.warn(`[${post.rede}] ${id}: ${e.message}`);
    return { erro: e.message };
  }
}

// ---------------- Sincronização agendada ----------------

export const sincronizarComentarios = onSchedule({ schedule: "every 1 minutes", timeoutSeconds: 300, maxInstances: 1 }, async () => {
  const cred = credenciaisConfiguradas();
  const posts = await POSTAGENS.select("rede").get();
  for (const d of posts.docs) {
    if (cred[d.get("rede")]) await sincronizar(d.id);
  }
});

// ---------------- API do painel ----------------

function autorizado(req) {
  const esperado = Buffer.from(process.env.ADMIN_TOKEN || "");
  const enviado = Buffer.from(String(req.get("x-admin-token") || ""));
  return esperado.length > 0 && enviado.length === esperado.length && timingSafeEqual(enviado, esperado);
}

export const api = onRequest({ timeoutSeconds: 120 }, async (req, res) => {
  res.set("cache-control", "no-store");
  const caminho = req.path.replace(/\/+$/, "");
  const corpo = typeof req.body === "object" && req.body ? req.body : {};
  try {
    if (req.method === "GET" && caminho === "/api/placar") {
      const s = await RESUMO.get();
      return res.json({ ...montarResumo([], []), ...(s.exists ? s.data() : {}), credenciais: credenciaisConfiguradas(), intervalo: INTERVALO_SEGUNDOS });
    }
    if (req.method === "POST" && caminho === "/api/testar") return res.json(classificar(corpo.texto));

    if (!autorizado(req)) return res.status(401).json({ erro: "Token de administrador inválido." });
    if (req.method === "GET" && caminho === "/api/admin/verificar") return res.json({ ok: true });

    if (req.method === "POST" && caminho === "/api/postagens") {
      let info = analisarLink(corpo.url);
      if (!info.idPostagem && info.curto) {
        try { info = { ...analisarLink(await resolverLinkCurto(info.url)), url: info.url }; } catch { /* segue sem ID */ }
      }
      const post = await adicionarPostagem({ ...info, titulo: corpo.titulo, idApi: corpo.idApi });
      if (credenciaisConfiguradas()[post.rede]) await sincronizar(post.id);
      return res.status(201).json({ postagem: post.id, rede: REDES[post.rede], idPostagem: post.idPostagem });
    }

    const m = caminho.match(/^\/api\/postagens\/([\w-]+)(\/[a-z]+)?$/);
    if (m) {
      const [, id, acao] = m;
      if (req.method === "DELETE" && !acao) {
        return (await removerPostagem(id)) ? res.json({ ok: true }) : res.status(404).json({ erro: "Postagem não encontrada." });
      }
      if (req.method === "POST" && acao === "/sincronizar") {
        const r = await sincronizar(id);
        return res.status(r.erro ? 502 : 200).json({ ok: !r.erro, ...r });
      }
      if (req.method === "POST" && acao === "/comentarios") {
        const comentarios = await linhasParaComentarios(corpo.texto);
        const r = await registrarComentarios(id, comentarios);
        return res.json({ lidos: comentarios.length, ...r });
      }
    }
    return res.status(404).json({ erro: "Rota não encontrada." });
  } catch (e) {
    return res.status(400).json({ erro: e.message });
  }
});
