import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Store } from "../lib/store.js";

const novoStore = (op) => new Store(join(mkdtempSync(join(tmpdir(), "placar-")), "db.json"), op);

test("cada comentário conta uma vez e porcentagens fecham 100%", () => {
  const s = novoStore();
  const p = s.adicionarPostagem({ url: "https://www.instagram.com/p/A1/", rede: "instagram", idPostagem: "A1" });
  s.registrarComentarios(p, [{ id: "a", texto: "13" }, { id: "b", texto: "22" }, { id: "c", texto: "Faz o L" }, { id: "d", texto: "oi" }]);
  s.registrarComentarios(p, [{ id: "a", texto: "13" }, { id: "e", texto: "mito" }]);
  const r = s.resumo();
  assert.deepEqual([r.totais.lula, r.totais.flavio, r.totais.ignorados, r.totais.total], [2, 2, 1, 4]);
  assert.equal(r.totais.pctLula + r.totais.pctFlavio, 100);
  assert.equal(r.porRede.instagram.lula, 2);
});

test("importação manual não duplica ao colar a mesma lista", () => {
  const s = novoStore();
  const p = s.adicionarPostagem({ url: "https://www.facebook.com/p/posts/1", rede: "facebook", idPostagem: "1" });
  assert.equal(s.importarTexto(p, "13\n13\n22\n").novos, 3);
  assert.equal(s.importarTexto(p, "13\n13\n22\n22\n").novos, 1);
  assert.deepEqual(p.votos, { lula: 2, flavio: 2, ignorados: 0 });
});

test("um voto por pessoa (opcional)", () => {
  const s = novoStore({ umVotoPorPessoa: true });
  const p = s.adicionarPostagem({ url: "https://www.instagram.com/p/A2/", rede: "instagram", idPostagem: "A2" });
  s.registrarComentarios(p, [{ id: "1", texto: "13", autor: "ana" }, { id: "2", texto: "13", autor: "ana" }, { id: "3", texto: "22", autor: "bia" }]);
  assert.deepEqual(p.votos, { lula: 1, flavio: 1, ignorados: 1 });
});

test("remover postagem tira os votos dela", () => {
  const s = novoStore();
  const p = s.adicionarPostagem({ url: "https://www.instagram.com/p/A3/", rede: "instagram", idPostagem: "A3" });
  s.registrarComentarios(p, [{ id: "1", texto: "22" }]);
  s.removerPostagem(p.id);
  assert.equal(s.resumo().totais.total, 0);
});
