import { test } from "node:test";
import assert from "node:assert/strict";
import { analisarLink } from "../lib/links.js";

test("identifica cada rede e o ID", () => {
  assert.deepEqual(
    [
      "https://x.com/fulano/status/1834567890123456789",
      "https://twitter.com/fulano/status/1834567890123456789?s=20",
      "https://www.instagram.com/p/C9abc_-12/",
      "https://www.instagram.com/reel/C9abc_-12/?igsh=xyz",
      "https://www.tiktok.com/@fulano/video/7412345678901234567",
      "https://www.facebook.com/minhapagina/posts/987654321",
      "https://www.facebook.com/permalink.php?story_fbid=111&id=222",
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "https://youtu.be/dQw4w9WgXcQ",
    ].map((u) => { const r = analisarLink(u); return [r.rede, r.idPostagem]; }),
    [
      ["x", "1834567890123456789"], ["x", "1834567890123456789"],
      ["instagram", "C9abc_-12"], ["instagram", "C9abc_-12"],
      ["tiktok", "7412345678901234567"],
      ["facebook", "987654321"], ["facebook", "222_111"],
      ["youtube", "dQw4w9WgXcQ"], ["youtube", "dQw4w9WgXcQ"],
    ],
  );
});

test("link curto do TikTok é marcado para resolver", () => {
  const r = analisarLink("https://vm.tiktok.com/ZMabc123/");
  assert.equal(r.rede, "tiktok");
  assert.equal(r.idPostagem, null);
  assert.equal(r.curto, true);
});

test("rejeita link inválido ou de outra rede", () => {
  assert.throws(() => analisarLink("não é link"));
  assert.throws(() => analisarLink("https://exemplo.com/post/1"));
});
