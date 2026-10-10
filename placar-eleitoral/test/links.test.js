import { test } from "node:test";
import assert from "node:assert/strict";
import { analisarLink } from "../lib/links.js";

test("identifica Instagram e Facebook e o ID da postagem", () => {
  assert.deepEqual(
    [
      "https://www.instagram.com/p/C9abc_-12/",
      "https://www.instagram.com/reel/C9abc_-12/?igsh=xyz",
      "https://www.facebook.com/minhapagina/posts/987654321",
      "https://m.facebook.com/permalink.php?story_fbid=111&id=222",
      "https://www.facebook.com/minhapagina/videos/555",
    ].map((u) => { const r = analisarLink(u); return [r.rede, r.idPostagem]; }),
    [
      ["instagram", "C9abc_-12"], ["instagram", "C9abc_-12"],
      ["facebook", "987654321"], ["facebook", "222_111"], ["facebook", "555"],
    ],
  );
});

test("link de compartilhamento do Facebook é marcado para resolver", () => {
  const r = analisarLink("https://www.facebook.com/share/p/AbCdEf/");
  assert.equal(r.rede, "facebook");
  assert.equal(r.idPostagem, null);
  assert.equal(r.curto, true);
});

test("recusa outras redes e links inválidos", () => {
  for (const u of ["https://x.com/a/status/1", "https://www.tiktok.com/@a/video/1", "https://youtu.be/dQw4w9WgXcQ", "https://exemplo.com/post/1", "não é link"]) {
    assert.throws(() => analisarLink(u));
  }
});
