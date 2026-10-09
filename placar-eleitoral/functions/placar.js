// Regras de contagem usadas pelas Cloud Functions, sem dependência do Firebase
// (assim podem ser testadas isoladamente). Mesmas regras do servidor Node (lib/store.js).
import { classificar } from "./lib/classifier.js";

export const TAMANHO_FEED = 40;
// Os IDs de comentários já contados ficam em documentos "pedaço" de até este tamanho
// (o limite de um documento do Firestore é 1 MB).
export const MAX_POR_PEDACO = 15000;

/**
 * Conta os comentários ainda não vistos.
 * @param vistos  Set com as chaves já contadas desta postagem
 * @param autores Set com os autores que já votaram (só usado com umVotoPorPessoa)
 * @returns { novos, novasChaves: [[chave, voto|0]], novosAutores: [], votos, feedNovo: [] }
 */
export function aplicarComentarios({ vistos, autores, votos, rede, postagemId }, comentarios, { umVotoPorPessoa = false, agora = new Date() } = {}) {
  const v = { lula: 0, flavio: 0, ignorados: 0, ...votos };
  const novasChaves = [];
  const novosAutores = [];
  const feedNovo = [];
  const vistosAgora = new Set();
  let novos = 0;

  for (const c of comentarios) {
    const chave = chaveSegura(c.id);
    if (vistos.has(chave) || vistosAgora.has(chave)) continue;
    vistosAgora.add(chave);
    let voto = classificar(c.texto).voto;
    if (voto && umVotoPorPessoa && c.autor) {
      const a = chaveSegura(c.autor);
      if (autores.has(a)) voto = null;
      else { autores.add(a); novosAutores.push(a); }
    }
    novasChaves.push([chave, voto || 0]);
    if (voto) {
      v[voto]++;
      novos++;
      feedNovo.unshift({ postagem: postagemId, rede, voto, texto: String(c.texto).slice(0, 140), em: agora.toISOString() });
    } else {
      v.ignorados++;
    }
  }
  return { novos, novasChaves, novosAutores, votos: v, feedNovo };
}

// Chaves de mapa no Firestore não podem ser vazias nem conter certos caracteres especiais.
export function chaveSegura(id) {
  const s = String(id ?? "").replace(/[./\[\]*`~]/g, "_");
  return s || "_vazio";
}

/** Distribui as novas chaves entre os pedaços existentes, criando novos quando enchem. */
export function distribuirEmPedacos(pedacos, novasChaves, max = MAX_POR_PEDACO) {
  // pedacos: [{ id, tamanho }], ordenados; devolve [{ id|null, entradas: [[k, v]] }]
  const saida = [];
  let i = 0;
  const ultimo = pedacos[pedacos.length - 1];
  if (ultimo && ultimo.tamanho < max) {
    const cabe = max - ultimo.tamanho;
    const parte = novasChaves.slice(0, cabe);
    if (parte.length) saida.push({ id: ultimo.id, entradas: parte });
    i = parte.length;
  }
  let proximo = pedacos.length;
  while (i < novasChaves.length) {
    saida.push({ id: String(proximo++).padStart(4, "0"), entradas: novasChaves.slice(i, i + max), novo: true });
    i += max;
  }
  return saida;
}

/** Monta o documento público placar/resumo a partir da lista de postagens e do feed. */
export function montarResumo(postagens, feed, agora = new Date()) {
  const totais = { lula: 0, flavio: 0, ignorados: 0 };
  const porRede = {};
  for (const p of postagens) {
    totais.lula += p.votos.lula;
    totais.flavio += p.votos.flavio;
    totais.ignorados += p.votos.ignorados;
    porRede[p.rede] ??= { lula: 0, flavio: 0, postagens: 0 };
    porRede[p.rede].lula += p.votos.lula;
    porRede[p.rede].flavio += p.votos.flavio;
    porRede[p.rede].postagens++;
  }
  const total = totais.lula + totais.flavio;
  const pctLula = total ? Math.round((totais.lula / total) * 1000) / 10 : 0;
  return {
    totais: { ...totais, total, pctLula, pctFlavio: total ? Math.round((100 - pctLula) * 10) / 10 : 0 },
    porRede,
    postagens,
    feed: feed.slice(0, TAMANHO_FEED),
    atualizadoEm: agora.toISOString(),
  };
}

/** Campos de uma postagem que podem aparecer no placar público. */
export function postagemPublica(id, p) {
  return {
    id,
    url: p.url,
    rede: p.rede,
    idPostagem: p.idPostagem ?? null,
    idApi: p.idApi ?? null,
    titulo: p.titulo ?? "",
    demo: false,
    criadoEm: p.criadoEm,
    ultimaSync: p.ultimaSync ?? null,
    erro: p.erro ?? null,
    votos: { lula: 0, flavio: 0, ignorados: 0, ...p.votos },
  };
}

/** Lê o texto colado no painel: uma linha = um comentário; o ID vem do conteúdo + ocorrência. */
export async function linhasParaComentarios(texto) {
  const { createHash } = await import("node:crypto");
  const ocorrencias = {};
  return String(texto ?? "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((linha) => {
      const h = createHash("sha1").update(linha).digest("hex").slice(0, 16);
      ocorrencias[h] = (ocorrencias[h] || 0) + 1;
      return { id: `manual:${h}:${ocorrencias[h]}`, texto: linha, autor: null };
    });
}
