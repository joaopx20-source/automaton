// Identifica a rede social e o ID da postagem a partir do link colado no painel.

export const REDES = {
  facebook: "Facebook",
  instagram: "Instagram",
  x: "X (Twitter)",
  tiktok: "TikTok",
  youtube: "YouTube",
};

export function analisarLink(link) {
  let url;
  try {
    url = new URL(String(link).trim());
  } catch {
    throw new Error("Link inválido. Cole o endereço completo da postagem (https://...).");
  }
  const host = url.hostname.replace(/^(www|m|mobile|web|vm|vt)\./, "");
  const caminho = url.pathname;
  let m;

  if (/(^|\.)(x\.com|twitter\.com)$/.test(host)) {
    m = caminho.match(/\/status(?:es)?\/(\d+)/);
    return { rede: "x", idPostagem: m?.[1] ?? null, url: url.href };
  }

  if (/(^|\.)instagram\.com$/.test(host)) {
    m = caminho.match(/\/(?:p|reel|reels|tv)\/([A-Za-z0-9_-]+)/);
    return { rede: "instagram", idPostagem: m?.[1] ?? null, url: url.href };
  }

  if (/(^|\.)tiktok\.com$/.test(host)) {
    m = caminho.match(/\/(?:video|photo)\/(\d+)/);
    return { rede: "tiktok", idPostagem: m?.[1] ?? null, url: url.href, curto: !m };
  }

  if (/(^|\.)(facebook\.com|fb\.com|fb\.watch)$/.test(host)) {
    // facebook.com/permalink.php?story_fbid=X&id=PAGINA
    const story = url.searchParams.get("story_fbid");
    const dono = url.searchParams.get("id");
    if (story && dono && /^\d+$/.test(story)) return { rede: "facebook", idPostagem: `${dono}_${story}`, url: url.href };
    // facebook.com/PAGINA/posts/123 ou /videos/123 ou /photo?fbid=123
    m = caminho.match(/\/(?:posts|videos|reel)\/(\d+)/);
    const fbid = m?.[1] ?? url.searchParams.get("fbid") ?? url.searchParams.get("v");
    return { rede: "facebook", idPostagem: fbid && /^\d+$/.test(fbid) ? fbid : null, url: url.href, curto: !fbid };
  }

  if (/(^|\.)(youtube\.com|youtu\.be)$/.test(host)) {
    m = host === "youtu.be" ? caminho.match(/^\/([\w-]{11})/) : caminho.match(/\/(?:shorts|live)\/([\w-]{11})/);
    return { rede: "youtube", idPostagem: m?.[1] ?? url.searchParams.get("v"), url: url.href };
  }

  throw new Error("Rede social não suportada. Use links do Facebook, Instagram, X, TikTok ou YouTube.");
}

// Links curtos (vm.tiktok.com, fb.watch, facebook.com/share/...) precisam seguir o redirecionamento.
export async function resolverLinkCurto(link) {
  const resp = await fetch(link, { redirect: "follow", headers: { "user-agent": "Mozilla/5.0" } });
  return resp.url || link;
}
