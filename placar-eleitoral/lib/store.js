import { EventEmitter } from "node:events";
import { createHash, randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { classificar } from "./classifier.js";

const TAMANHO_FEED = 40;

/**
 * Guarda postagens, comentários já contados e votos num arquivo JSON.
 * Cada comentário é contado uma única vez (pelo ID na rede social), então
 * sincronizar de novo a mesma postagem nunca duplica votos.
 */
export class Store extends EventEmitter {
  constructor(arquivo, { umVotoPorPessoa = false } = {}) {
    super();
    this.arquivo = arquivo;
    this.umVotoPorPessoa = umVotoPorPessoa;
    this.db = { postagens: [], feed: [] };
    if (existsSync(arquivo)) this.db = { ...this.db, ...JSON.parse(readFileSync(arquivo, "utf8")) };
    this._timer = null;
  }

  _salvar() {
    this.emit("mudou");
    if (this._timer) return;
    this._timer = setTimeout(() => this.salvarAgora(), 1000);
  }

  salvarAgora() {
    clearTimeout(this._timer);
    this._timer = null;
    mkdirSync(dirname(this.arquivo), { recursive: true });
    const tmp = `${this.arquivo}.tmp`;
    writeFileSync(tmp, JSON.stringify(this.db));
    renameSync(tmp, this.arquivo);
  }

  postagem(id) {
    return this.db.postagens.find((p) => p.id === id);
  }

  adicionarPostagem({ url, rede, idPostagem, idApi, titulo, demo }) {
    const existente = this.db.postagens.find((p) => p.url === url);
    if (existente) throw new Error("Essa postagem já está no placar.");
    const post = {
      id: randomUUID().slice(0, 8),
      url, rede, idPostagem: idPostagem || null, idApi: idApi || null,
      titulo: titulo || "",
      demo: !!demo,
      criadoEm: new Date().toISOString(),
      ultimaSync: null, erro: null, estado: {},
      votos: { lula: 0, flavio: 0, ignorados: 0 },
      vistos: {}, autores: {},
    };
    this.db.postagens.push(post);
    this._salvar();
    return post;
  }

  removerPostagem(id) {
    const antes = this.db.postagens.length;
    this.db.postagens = this.db.postagens.filter((p) => p.id !== id);
    this.db.feed = this.db.feed.filter((f) => f.postagem !== id);
    if (this.db.postagens.length === antes) return false;
    this._salvar();
    return true;
  }

  registrarErro(post, erro) {
    post.erro = erro ? String(erro.message || erro) : null;
    post.ultimaSync = new Date().toISOString();
    this._salvar();
  }

  /** Conta os comentários ainda não vistos. Retorna quantos votos novos entraram. */
  registrarComentarios(post, comentarios, estado) {
    let novos = 0;
    for (const c of comentarios) {
      const chave = String(c.id);
      if (chave in post.vistos) continue;
      const { voto } = classificar(c.texto);
      let valido = voto;
      if (valido && this.umVotoPorPessoa && c.autor) {
        if (post.autores[c.autor]) valido = null;
        else post.autores[c.autor] = 1;
      }
      post.vistos[chave] = valido || 0;
      if (valido) {
        post.votos[valido]++;
        novos++;
        this.db.feed.unshift({
          postagem: post.id,
          rede: post.rede,
          voto: valido,
          texto: String(c.texto).slice(0, 140),
          em: new Date().toISOString(),
        });
      } else {
        post.votos.ignorados++;
      }
    }
    this.db.feed.length = Math.min(this.db.feed.length, TAMANHO_FEED);
    if (estado) post.estado = { ...post.estado, ...estado };
    post.erro = null;
    post.ultimaSync = new Date().toISOString();
    this._salvar();
    return novos;
  }

  /**
   * Importação manual: cada linha de texto é um comentário.
   * O ID é derivado do conteúdo + ocorrência, então colar a mesma lista
   * (ou uma lista maior com os mesmos comentários) não conta duas vezes.
   */
  importarTexto(post, texto) {
    const ocorrencias = {};
    const comentarios = String(texto)
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
      .map((linha) => {
        const h = createHash("sha1").update(linha).digest("hex").slice(0, 16);
        ocorrencias[h] = (ocorrencias[h] || 0) + 1;
        return { id: `manual:${h}:${ocorrencias[h]}`, texto: linha, autor: null };
      });
    return { lidos: comentarios.length, novos: this.registrarComentarios(post, comentarios) };
  }

  resumo() {
    const totais = { lula: 0, flavio: 0, ignorados: 0 };
    const porRede = {};
    for (const p of this.db.postagens) {
      totais.lula += p.votos.lula;
      totais.flavio += p.votos.flavio;
      totais.ignorados += p.votos.ignorados;
      porRede[p.rede] ??= { lula: 0, flavio: 0, postagens: 0 };
      porRede[p.rede].lula += p.votos.lula;
      porRede[p.rede].flavio += p.votos.flavio;
      porRede[p.rede].postagens++;
    }
    const total = totais.lula + totais.flavio;
    const pct = (n) => (total ? Math.round((n / total) * 1000) / 10 : 0);
    return {
      totais: { ...totais, total, pctLula: pct(totais.lula), pctFlavio: total ? Math.round((100 - pct(totais.lula)) * 10) / 10 : 0 },
      porRede,
      postagens: this.db.postagens.map(({ vistos, autores, estado, ...p }) => p),
      feed: this.db.feed,
      atualizadoEm: new Date().toISOString(),
    };
  }
}
