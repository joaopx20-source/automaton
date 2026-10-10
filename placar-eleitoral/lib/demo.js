// Modo demonstração: cria postagens fictícias e injeta comentários aleatórios
// para ver o placar mexendo em tempo real sem precisar de credenciais.

const EXEMPLOS = [
  "13", "22", "Lula 13!!", "Faz o L", "#Lula13", "PT sempre", "Lulinha paz e amor", "1️⃣3️⃣",
  "22 é o caminho", "Mito!", "Flávio presidente 🇧🇷", "PL 22", "Bolsonaro 2026", "Fora PT",
  "fora bolsonaro", "ele não", "#flavio22", "vote 22", "vote 13", "Lula lá ⭐",
  "kkkkk", "que vídeo bom", "quem viu até o final?", "🙏", "bom dia",
];

export function iniciarDemo(store) {
  if (!store.db.postagens.some((p) => p.demo)) {
    const base = [
      ["facebook", "https://www.facebook.com/exemplo/posts/1000000000000001", "Post no Facebook (demo)"],
      ["instagram", "https://www.instagram.com/p/DEMO0000001/", "Post no Instagram (demo)"],
    ];
    for (const [rede, url, titulo] of base) store.adicionarPostagem({ rede, url, titulo, demo: true });
  }
  let n = 0;
  setInterval(() => {
    const posts = store.db.postagens.filter((p) => p.demo);
    if (!posts.length) return;
    const post = posts[Math.floor(Math.random() * posts.length)];
    const lote = Array.from({ length: 1 + Math.floor(Math.random() * 3) }, () => ({
      id: `demo-${Date.now()}-${n++}`,
      texto: EXEMPLOS[Math.floor(Math.random() * EXEMPLOS.length)],
      autor: null,
    }));
    store.registrarComentarios(post, lote);
  }, 1200);
}
