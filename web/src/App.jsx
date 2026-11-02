/* DEALS — application grand public, branchée sur /api/r/. Interface v47 : un flux vivant de remises, à la croisée d'un
   Pinterest (des visuels, une mosaïque, l'inspiration par pièce) et d'un Bloomberg (un bandeau qui défile, l'heure de
   mise à jour, la courbe du prix sur 90 jours, « au plus bas depuis 90 jours »).

   v48 : sur la fiche, la marque et la catégorie se touchent et mènent à tous leurs produits (jamais de cul-de-sac) ;
   « Me prévenir sous un prix » pour ce produit ou tous les comparables ; les Missions, un onglet : une envie et un prix
   en une phrase (« aspirateur balai sous 300 € »), ce qui y répond déjà, puis un e-mail la nuit où c'est le cas.

   v49 : deux onglets, deux rôles. L'Accueil est éditorial (les pièces, les marques en promo, notre sélection) ; la
   Recherche sert à trouver (un produit, une marque, une catégorie). La fiche dit en mots et d'un coup d'œil si le prix
   du jour est bas sur les derniers mois, et ne propose que l'enseigne la moins chère.

   v50 : la Recherche répond à une intention précise, sobrement : un champ, trois filtres (catégorie, budget, remise) et
   un tri visibles d'emblée, des résultats en mosaïque ; avant toute recherche, quelques exemples. L'accueil inspire, la
   recherche répond, les missions guettent.

   v51 : la Recherche n'est jamais vide. Un feed est là avant toute saisie (l'étendue du catalogue, une catégorie à tour
   de rôle, ou « Pour vous » d'après vos dernières recherches, gardées par ce navigateur) ; chaque lettre, filtre ou tri
   l'adapte sur place, sans écran blanc, et une recherche sans résultat retombe sur le feed.

   v52 : la conversion d'abord (modèle d'affiliation, enseignes partenaires seulement). Une mission mène à l'offre en un
   geste (« Voir l'offre » sur la mission atteinte, et dans son e-mail) ; lancée sans compte, elle attend le lien sur le
   serveur et démarre sur n'importe quel appareil. Chaque fiche ouverte est comptée, d'où elle vient (taux de clic par
   écran, par mission) ; la mention « enseigne partenaire » est près de l'offre, et « Comment ça marche » sur chaque écran.

   v53 : l'accueil commence par les top deals (les plus fortes remises et les prix parmi les plus bas depuis longtemps, à
   tour de rôle, chacun dit pourquoi il est là) ; la Recherche filtre par promo (−10 % à −50 %, ou prix bas), avec le
   nombre de produits de chaque choix ; les favoris passent dans le Profil : quatre onglets.

   v58 : dans un domaine qui a son ontologie (les aspirateurs), la Recherche comprend le type (balai, robot, traîneau…) et
   deux attributs (sans fil, sans sac), lus dans l'offre de l'enseigne ; Affiner les propose. Le Profil est aéré : des
   titres seuls, vos rayons repliés.

   v59 : chaque rayon a son ontologie, et l'électronique arrive (téléviseurs, smartphones, ordinateurs portables, tablettes,
   casques, enceintes, montres, consoles, écrans PC) : une pièce « High-tech » à l'accueil, ses exemples dans la Recherche,
   ses illustrations.

   v60 : Affiner en entonnoir. Une question à la fois — l'univers (High-tech, Salon…), le rayon, le type, un attribut, le
   budget —, chaque réponse avec son nombre de produits, « Passer » pour passer ; quand il n'y a plus de question,
   c'est votre sélection. Le même entonnoir dans la Recherche et sur la page d'une marque, d'une catégorie, d'une pièce.
   La fiche n'a plus la jauge du prix des derniers mois : le prix, la remise, l'offre.

   v64 : quatre onglets. Top deals (les plus fortes remises réelles et les prix parmi les plus bas, à tour de rôle)
   devient un onglet, le premier, ouvert au lancement ; l'Accueil devient Explorer, le même sans les top deals (le
   bandeau, « Pour vous », les inspirations du moment, les marques en promo, notre sélection) ; « Pour vous » y montre
   tous vos deals, top deals compris. Recherche et Profil ne changent pas.

   Les visuels sont des illustrations originales par catégorie (art.jsx) : aucune image extérieure, aucune requête vers un
   tiers, aucun droit de tiers. Gardé des versions précédentes : le produit comme entrée, un deal identique pour tous, des
   remises réelles seulement (la qualité est implicite), les durées dans la fiche seulement, « Moins cher, comparable »,
   la recherche dans tout le catalogue, la connexion au moment de l'action, contrastes et zones à toucher aux normes. */
import { useState, useEffect, useRef, useMemo } from "react";
import { Vignette, ratioOf } from "./art.jsx";

/* ---------------------------------------------------------------- pictogrammes (dessins originaux, 24 × 24) */
const C = (x, y, r) => `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
const HEART = "M12 20.3s-7.6-4.6-7.6-10.1A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.6 2.6c0 5.5-7.6 10.1-7.6 10.1z";
const UI = {
  search: [C(10.5, 10.5, 6.5), "M15.5 15.5L20 20"],
  back: ["M14.5 5.5L8 12l6.5 6.5"],
  ext: ["M9 15l6.5-6.5", "M10 8.5h5.5V14"],
  check: ["M5.5 12.5l4 4 9-9"],
  x: ["M7 7l10 10", "M17 7L7 17"],
  plus: ["M12 5v14", "M5 12h14"],
  heart: [HEART],
  bell: ["M6.5 16.5V11a5.5 5.5 0 0 1 11 0v5.5l1.5 2h-14z", "M10 20.5a2.2 2.2 0 0 0 4 0"],
  home: ["M4.5 10.5L12 4.5l7.5 6V19a1 1 0 0 1-1 1h-4v-5.5h-5V20h-4a1 1 0 0 1-1-1z"],
  flame: ["M12 20.5c-3.5 0-6-2.5-6-5.8 0-2.6 1.4-4.3 2.8-5.9.2 1.5.9 2.6 2 3.2-.1-3.3 1.4-6.1 4-8 .2 3 1.8 4.9 3 6.6.9 1.3 1.5 2.6 1.5 4.3 0 3.1-2.6 5.6-6.3 5.6z"],
  compass: ["M15.2 8.8l-1.9 4.5-4.5 1.9 1.9-4.5z", C(12, 12, 8.2)],   // l'aiguille d'abord : c'est elle que l'onglet ouvert remplit
  user: [C(12, 8.5, 3.8), "M4.8 20c.8-3.6 3.6-5.6 7.2-5.6s6.4 2 7.2 5.6"],
  share: ["M12 15V4.5", "M8 8l4-4 4 4", "M6 12.5V19a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-6.5"],
  cal: ["M5.5 6h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z", "M4.5 10h15", "M8.5 4v4", "M15.5 4v4"],
  next: ["M9.5 5.5L16 12l-6.5 6.5"],
  target: [C(12, 12, 8), C(12, 12, 4.2), "M12 12h.01"],
  down: ["M7 10l5 5 5-5"],
  bookmark: ["M7.5 4.5h9a1 1 0 0 1 1 1v14.5l-5.5-3.6-5.5 3.6V5.5a1 1 0 0 1 1-1z"],
};
const Icon = ({ d, size = 20, sw = 1.8, fill }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className="i"
  fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
  {d.map((p, i) => <path key={i} d={p} />)}{fill && <path d={d[0]} fill="currentColor" stroke="none" />}</svg>;

/* ---------------------------------------------------------------- formats */
const eur = n => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " €";
const iso = d => new Date(`${d}T12:00:00`);
const dayLabel = d => new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short" }).format(iso(d));
const daysBetween = (a, b) => Math.round((iso(b) - iso(a)) / 86400000);
const clock = ts => new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(new Date(ts * 1000));
const shortDay = ts => new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" }).format(new Date(ts * 1000));
const plural = (n, w) => `${n} ${w}${n > 1 ? "s" : ""}`;
const norm = s => (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const FAMILY = { electromenager: "Électroménager", electronique: "Électronique", ameublement: "Ameublement", literie: "Literie" };
// Recherche : des exemples pour démarrer, le filtre de promo et les tris (le rayon et le budget : l'entonnoir).
const TRY = ["aspirateur balai sans fil", "TV OLED 55 pouces", "smartphone 5G", "lave-linge 9 kg", "canapé d'angle"];
// Promo : un palier de remise, ou un prix parmi les plus bas depuis longtemps (catalog.cheap) ; seuls les choix qui
// donnent quelque chose sont proposés, avec leur nombre de produits.
const OFFS = [["", "Toutes"], ["1", "En promo"], ["10", "−10 % et plus"], ["20", "−20 % et plus"], ["30", "−30 % et plus"],
  ["40", "−40 % et plus"], ["50", "−50 % et plus"], ["low", "Prix parmi les plus bas"]];
const SORTS = [["relevance", "Pertinence"], ["price", "Prix croissant"], ["price_desc", "Prix décroissant"], ["discount", "Plus forte promo"]];
// Pages d'une marque, d'une catégorie, d'une pièce : leur tri, dit au serveur (catalog.SORTS).
const PAGE_SORT = { pct: "discount", asc: "price", desc: "price_desc" };
// Les critères choisis dans l'app (puces, Affiner) ; la phrase tapée dit le reste (deals/query.py).
// Dans un rayon et son ontologie (v59 : tous) : domain, sub (le type), props (sans fil, 5G, No Frost… : exigés).
const NO_CRIT = { category: null, room: null, brand: null, features: [], attrs: {}, min: null, max: null, off: null, low: false, sort: null,
  domain: null, sub: null, props: {} };
const hasCrit = c => !!(c.category || c.room || c.brand || c.features.length || Object.keys(c.attrs).length || c.min != null || c.max != null
  || c.off || c.low || c.sort || c.domain || c.sub || Object.keys(c.props).length);
const searchParams = (text, c) => {
  const p = new URLSearchParams();
  if (text) p.set("q", text);
  for (const [k, v] of [["category", c.category], ["room", c.room], ["brand", c.brand], ["min", c.min], ["max", c.max], ["off", c.off], ["sort", c.sort],
                        ["domain", c.domain], ["sub", c.sub]])
    if (v != null && v !== "") p.set(k, v);
  if (c.features.length) p.set("feat", c.features.join(","));
  const a = Object.entries(c.attrs);
  if (a.length) p.set("attr", a.map(([k, v]) => `${k}:${v}`).join(","));
  if (c.low) p.set("low", "1");
  const pr = Object.entries(c.props);
  if (pr.length) p.set("prop", pr.map(([k, v]) => `${k}:${v ? 1 : 0}`).join(","));
  return p;
};
// Une réponse de l'entonnoir, ou le retour avant une étape, appliquée aux critères (deals/funnel.py) : props et attrs
// s'y ajoutent (null les vide, une valeur null retire la clé), le reste est remplacé.
const applyPatch = (c, patch) => {
  const out = { ...c };
  for (const [k, v] of Object.entries(patch)) {
    if (k !== "props" && k !== "attrs") { out[k] = v; continue; }
    const m = v == null ? {} : { ...c[k] };
    for (const [x, y] of Object.entries(v || {})) { if (y == null) delete m[x]; else m[x] = y; }
    out[k] = m;
  }
  return out;
};
// Où en est l'entonnoir : les étapes (sans celles que le titre de la page dit déjà : hide), la question posée (la
// première qui n'est pas passée), celles qui restent, combien sont faites (choisies ou passées).
const funnelAt = (f, skip, hide = []) => {
  if (!f) return null;
  const path = f.path.filter(s => !hide.includes(s.level));
  const open = f.questions.filter(q => !skip.includes(q.key));
  return { path, open, q: open[0] || null, done: path.filter(s => !s.fixed).length + f.questions.length - open.length };
};
/* Vos dernières recherches (4, la plus récente d'abord), gardées par ce navigateur seulement : elles orientent le feed
   de la Recherche (« Pour vous ») ; le serveur ne les garde pas. */
const RECENT = "deals.recent", RECENT_MAX = 4;
const recents = {
  get() { try { const v = JSON.parse(localStorage.getItem(RECENT) || "[]"); return Array.isArray(v) ? v.filter(x => typeof x === "string").slice(0, RECENT_MAX) : []; } catch { return []; } },
  set(list) { try { localStorage.setItem(RECENT, JSON.stringify(list)); } catch { /* stockage indisponible */ } },
};
/* Vos goûts (deals/profile.py) : les rayons que vous choisissez et, pendant la visite, les fiches que vous ouvrez et les
   offres que vous allez voir. Sans compte, ce navigateur les garde (les fiches ouvertes seulement si vous l'acceptez dans
   Profil) et les envoie avec les lectures pour mettre vos deals en tête ; le serveur n'en garde rien. Avec un compte, ils
   sont sur le compte. */
const kept = (key, fallback) => ({
  get() { try { const v = JSON.parse(localStorage.getItem(key) || "null"); return v ?? fallback; } catch { return fallback; } },
  set(v) { try { if (v == null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(v)); } catch { /* stockage indisponible */ } },
});
const PICKS = kept("deals.picks", []), SEEN = kept("deals.seen", []), LEARN = kept("deals.learn", false), PICKER = kept("deals.picker", "on");
const SEEN_MAX = 60, PICKS_MAX = 12;
const cleanPicks = v => Array.isArray(v) ? [...new Set(v.filter(x => typeof x === "string" && /^[a-z_]{2,40}$/.test(x)))].slice(0, PICKS_MAX) : [];
const seenParam = list => list.slice(-SEEN_MAX).reverse()
  .map(e => `${e.k}${e.id}.${Math.min(365, Math.max(0, Math.floor((Date.now() / 1000 - e.t) / 86400)))}`).join(",");
/* « Vos rayons : Canapés, Matelas », « D'après vos recherches : Aspirateurs » ou « D'après vos visites : Canapés » : ce que
   l'app a compris, dit en une ligne ; les rayons que vous avez choisis d'abord (picks), puis ceux de vos recherches et
   alertes (chosen, côté serveur), puis ceux des fiches ouvertes. */
function tasteLine(t, picks = []) {
  const cats = t?.cats || [], mine = cats.filter(c => picks.includes(c.key)), asked = cats.filter(c => c.chosen && !picks.includes(c.key));
  const [say, list] = mine.length ? ["Vos rayons", mine] : asked.length ? ["D'après vos recherches", asked] : ["D'après vos visites", cats];
  if (!list.length) return t?.brands?.length ? `Vos marques : ${t.brands.slice(0, 2).map(b => b.name).join(", ")}` : "";
  return `${say} : ${list.slice(0, 2).map(c => c.label).join(", ")}${list.length > 2 ? "…" : ""}`;
}
// L'inspiration par pièce : des catégories regroupées comme on pense son intérieur ; le high-tech en premier (v59).
const ROOMS = [
  { key: "high_tech", label: "High-tech", art: "televiseur",
    cats: ["televiseur", "smartphone", "ordinateur_portable", "tablette", "casque_audio", "enceinte", "montre_connectee", "console", "ecran_pc"] },
  { key: "chambre", label: "Chambre", art: "lit", cats: ["lit", "matelas", "sommier", "armoire", "commode"] },
  { key: "salon", label: "Salon", art: "canape", cats: ["canape", "fauteuil", "table", "buffet", "meuble_tv", "luminaire"] },
  { key: "cuisine", label: "Cuisine", art: "refrigerateur",
    cats: ["refrigerateur", "congelateur", "four", "plaque_cuisson", "hotte", "lave_vaisselle", "cuisiniere", "micro_ondes", "machine_cafe"] },
  { key: "buanderie", label: "Buanderie", art: "lave_linge", cats: ["lave_linge", "seche_linge", "lave_linge_sechant"] },
  { key: "entretien", label: "Entretien", art: "aspirateur", cats: ["aspirateur", "robot_aspirateur"] },
];

/* Durées : seulement dans la fiche, en une ligne. */
function timing(p) {
  if (!(p.pct > 0) || !p.published_on) return null;
  const parts = [];
  if (p.since) {
    const n = daysBetween(p.since, p.published_on);
    parts.push(n <= 0 ? "En remise depuis aujourd'hui" : `En remise depuis ${n} jour${n > 1 ? "s" : ""}`);
  }
  if (p.ends && daysBetween(p.published_on, p.ends) >= 0) parts.push(`${parts.length ? "jusqu'au" : "Jusqu'au"} ${dayLabel(p.ends)}`);
  return parts.length ? parts.join(", ") : null;
}

async function api(path, body) {
  const r = await fetch(`/api/r/${path}`, {
    credentials: "same-origin",
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(data.error || "Erreur"); e.status = r.status; throw e; }
  return data;
}

/* Prix proposés pour une alerte : −5 %, −10 % et −20 % du prix du jour. */
function suggestions(p) {
  const out = [];
  for (const f of [0.95, 0.9, 0.8]) { const v = Math.floor(p.price * f); if (!out.some(([x]) => x === v)) out.push([v, `−${Math.round((1 - f) * 100)} %`]); }
  return out;
}

const withOut = (set, id) => { const n = new Set(set); n.delete(id); return n; };
const withIn = (set, id) => { const n = new Set(set); n.add(id); return n; };
const useWidth = () => {
  const [w, setW] = useState(typeof window === "undefined" ? 390 : window.innerWidth);
  useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener("resize", f); return () => window.removeEventListener("resize", f); }, []);
  return w;
};

const CSS = `
.d{--ink:#141414;--paper:#FFFFFF;--tint:#F4F2EF;--tint2:#EAE7E2;--mid:#5E6166;--soft:#6B6E73;--icon:#8A8D92;--line:#ECE9E4;
  --accent:#D63A0D;--accent-ink:#B5300A;--accent-soft:#FCEDE6;--good:#1F7A52;--warn:#A9480A;--terminal:#121315;
  --serif:"Instrument Serif",Georgia,"Times New Roman",serif;--mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
  font-family:Manrope,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif;color:var(--ink);background:var(--paper);min-height:100vh;
  font-size:15px;line-height:1.4;-webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1}
.d *{box-sizing:border-box}.d button{font:inherit;color:inherit;cursor:pointer}.d input{font:inherit}
.d .i{display:block;flex:0 0 auto}
.d :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:10px}
.d .app{max-width:520px;margin:0 auto;min-height:100vh;background:var(--paper);position:relative;padding-bottom:96px}
.d .top{display:flex;justify-content:space-between;align-items:center;height:58px;padding:0 10px 0 16px}
.d .logo{font-family:var(--serif);font-size:32px;line-height:1;letter-spacing:-.01em;border:0;background:none;min-height:44px;padding:0 4px;margin-left:-4px}
.d .logo b{color:var(--accent);font-weight:400}
.d .tabs{display:none}
.d .ibtn{position:relative;flex:0 0 auto;border:0;background:none;width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center}
.d .ibtn .dot{position:absolute;top:6px;right:5px;min-width:18px;height:18px;border-radius:9px;background:var(--accent);color:#fff;font-size:11px;font-weight:800;line-height:18px;padding:0 5px}
/* bandeau défilant */
.d .ticker{display:flex;align-items:center;height:34px;background:var(--terminal);color:#E7E5E0;font-family:var(--mono);font-size:12px;letter-spacing:.02em;overflow:hidden}
.d .ticker .live{flex:0 0 auto;display:flex;align-items:center;gap:7px;padding:0 12px;height:100%;background:#1E2023;color:#FF9A70;font-weight:700;white-space:nowrap}
.d .ticker .live i{width:7px;height:7px;border-radius:50%;background:#FF6A3D;box-shadow:0 0 0 3px rgba(255,106,61,.2)}
.d .tape{flex:1;overflow:hidden;mask-image:linear-gradient(90deg,transparent,#000 24px,#000 calc(100% - 24px),transparent)}
.d .run{display:inline-flex;white-space:nowrap;animation:tape linear infinite;will-change:transform}
.d .ticker:hover .run{animation-play-state:paused}
.d .tk{display:inline-flex;align-items:center;gap:7px;padding:0 16px;border-right:1px solid #2E3034}
.d .tk .dn{color:#FF6A3D;font-weight:700}.d .tk .pc{color:#FF9A70;font-weight:700}
@keyframes tape{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.d .run{animation:none}.d .tape{overflow-x:auto}.d .flow{transition:none}}
/* titres */
.d .intro{padding:18px 16px 0}
.d h1{font-family:var(--serif);font-weight:400;font-size:42px;line-height:1;letter-spacing:-.015em;margin:0}
.d .pagehead{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;padding:12px 10px 0 16px}
.d .sub{color:var(--mid);font-size:14.5px;margin-top:6px}
.d h2{font-family:var(--serif);font-weight:400;font-size:26px;line-height:1.05;letter-spacing:-.01em;margin:0}
.d .sechead{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:26px 16px 12px}
.d .sechead .n{font-family:var(--mono);font-size:12px;color:var(--soft)}
/* recherche, univers */
.d .sbar{display:flex;align-items:center;gap:10px;background:var(--tint);border-radius:999px;padding:0 6px 0 16px;height:50px;margin:16px 16px 0;color:var(--mid)}
.d .sbar input{flex:1;min-width:0;border:0;outline:0;background:transparent;font-size:16px;color:var(--ink);height:100%}
.d .sbar input::placeholder{color:var(--soft)}
.d .sx{border:0;background:none;color:var(--mid);width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:12px}
.d .chips{display:flex;gap:8px;overflow-x:auto;padding:14px 16px 2px;scrollbar-width:none}
.d .chips::-webkit-scrollbar{display:none}
.d .chips button{flex:0 0 auto;border:0;background:var(--tint);border-radius:999px;min-height:44px;padding:0 18px;font-size:14.5px;font-weight:700;white-space:nowrap}
.d .chips button.on{background:var(--ink);color:#fff}
/* inspirations par pièce */
.d .rooms{display:flex;gap:10px;overflow-x:auto;padding:0 16px 4px;scroll-snap-type:x mandatory;scroll-padding-inline:16px;scrollbar-width:none}
.d .rooms::-webkit-scrollbar{display:none}
.d .room{position:relative;flex:0 0 auto;width:156px;height:208px;border:0;padding:0;border-radius:18px;overflow:hidden;scroll-snap-align:start;text-align:left;background:var(--tint)}
.d .room .shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 30%,rgba(0,0,0,.5) 56%,rgba(0,0,0,.82))}
.d .room .rt{position:absolute;left:12px;right:12px;bottom:12px;color:#fff;display:flex;flex-direction:column;gap:2px}
.d .room .rt b{font-size:19px;font-weight:800;letter-spacing:-.02em}
.d .room .rt{text-shadow:0 1px 2px rgba(0,0,0,.35)}
.d .room .rt span{font-size:14px;font-weight:700}
.d .room .rt small{font-size:11.5px;font-weight:600;opacity:.92;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* mosaïque */
.d .masonry{display:grid;gap:12px;padding:0 16px;align-items:start}
.d .mcol{display:flex;flex-direction:column;gap:18px;min-width:0}
.d .card{display:block;cursor:pointer;min-width:0}
.d .vis{position:relative;border-radius:16px;overflow:hidden;background:var(--tint)}
.d .badge{position:absolute;left:10px;bottom:10px;background:var(--accent);color:#fff;font-size:13px;font-weight:800;border-radius:8px;padding:4px 8px;letter-spacing:-.01em}
.d .badge.good{background:var(--good)}
.d .meta .why{display:flex;align-items:center;gap:5px;margin-top:4px;font-size:12px;font-weight:700;color:var(--good);line-height:1.3}
.d .meta .why .i{flex:0 0 auto}
.d .sechead .n.drop{color:var(--good);font-weight:700}
.d .heart{position:absolute;top:2px;right:2px;width:44px;height:44px;border:0;background:none;display:flex;align-items:center;justify-content:center;color:var(--ink)}
.d .heart span{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.92);display:flex;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.d .heart.on{color:var(--accent)}
.d .meta{padding:9px 2px 0}
.d .meta .brand{font-size:11px;font-weight:800;color:var(--mid);text-transform:uppercase;letter-spacing:.08em}
.d .meta .name{font-size:14.5px;font-weight:600;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.d .meta .price{display:flex;align-items:baseline;gap:7px;margin-top:3px}
.d .meta .price b{font-size:20px;font-weight:800;letter-spacing:-.03em}
.d .meta .price b.deal{color:var(--accent)}
.d .meta .price s{font-size:12.5px;color:var(--mid)}
.d .meta .drop{font-size:13px;font-weight:800;color:var(--good);margin-top:2px}
.d .scroller{display:flex;gap:12px;overflow-x:auto;padding:0 16px 4px;scrollbar-width:none}
.d .scroller::-webkit-scrollbar{display:none}
.d .scroller .card{flex:0 0 auto;width:158px}
.d .empty{padding:28px 16px;color:var(--mid)}
.d .err{color:var(--accent);font-size:14px;font-weight:700;margin-top:10px}
.d .back{border:0;background:none;min-height:44px;padding:0 16px 0 10px;font-size:14px;font-weight:800;color:var(--mid);display:flex;align-items:center;gap:4px}
/* fiche */
.d .hero{position:relative;background:var(--tint)}
.d .hero .vis{border-radius:0;max-height:58vh}
.d .hero .float{position:absolute;top:10px;left:10px;right:10px;display:flex;justify-content:space-between;pointer-events:none}
.d .hero .float div{display:flex;gap:8px}
.d .fbtn{pointer-events:auto;width:44px;height:44px;border:0;border-radius:50%;background:rgba(255,255,255,.94);display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.14)}
.d .fbtn.on{color:var(--accent)}
.d .info{padding:18px 16px 0}
.d .info .title{font-family:inherit;font-size:21px;font-weight:700;letter-spacing:-.02em;line-height:1.2;margin:4px 0 0}
.d .prices{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 14px;margin-top:12px}
.d .prices .pct{font-size:46px;font-weight:800;letter-spacing:-.05em;color:var(--accent);line-height:1}
.d .prices .now{font-size:34px;font-weight:800;letter-spacing:-.04em;line-height:1}
.d .prices s{font-size:17px;color:var(--mid)}
.d .when{display:flex;align-items:center;gap:10px;margin-top:14px;background:var(--accent-soft);border-radius:14px;padding:12px 14px;font-size:14px;font-weight:600}
.d .when .i{color:var(--accent)}
.d .buy{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:14px;min-height:54px;border-radius:15px;background:var(--ink);color:#fff;font-size:16px;font-weight:800;text-decoration:none}
/* comptes, marques */
.d .cta{display:block;width:100%;margin-top:16px;border:0;background:var(--ink);color:#fff;border-radius:16px;min-height:50px;font-size:15px;font-weight:800}
.d .cta:disabled{opacity:.5}
.d .ghost{border:0;background:none;color:var(--mid);font-size:14px;font-weight:800;min-height:44px;padding:0 16px;margin-top:12px;display:block}
.d .pill{flex:0 0 auto;display:flex;align-items:center;gap:6px;border:0;background:var(--ink);color:#fff;border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:800}
.d .pill.on{background:var(--accent-soft);color:var(--accent-ink)}
.d .me{padding:6px 16px 0;color:var(--mid);font-size:14.5px}
.d .me b{color:var(--ink)}
.d .bchips{display:flex;flex-wrap:wrap;gap:8px;padding:0 16px}
.d .bchips button{border:0;background:var(--tint);border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:800}
.d .sheet-wrap{position:fixed;inset:0;background:rgba(18,19,21,.42);display:flex;align-items:flex-end;justify-content:center;z-index:10}
.d .sheet{width:100%;max-width:520px;background:var(--paper);border-radius:26px 26px 0 0;padding:24px 20px 32px;max-height:86vh;overflow:auto}
.d .sheet h2{margin:6px 0 0}
.d .sheet h3{font-size:13px;font-weight:800;color:var(--mid);text-transform:uppercase;letter-spacing:.08em;margin:20px 0 10px}
.d .sheet p.hint{color:var(--mid);font-size:14px;margin:8px 0 0}
.d .sheet input{width:100%;margin-top:16px;border:1px solid #CFCFCA;border-radius:14px;padding:14px;font-size:16px;color:var(--ink);outline:0}
.d .sheet input:focus{border-color:var(--ink)}
.d .eyebrow{font-size:11.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--mid)}
.d .opts{display:flex;flex-direction:column;gap:6px}
.d .opts button{display:flex;justify-content:space-between;align-items:center;border:0;background:var(--tint);border-radius:14px;min-height:48px;padding:0 16px;font-size:15px;font-weight:700;text-align:left}
.d .opts button.on{background:var(--ink);color:#fff}
.d .opts button{padding:10px 16px}
.d .opts small{display:block;font-size:13px;font-weight:600;color:var(--mid);margin-top:2px}
.d .opts button.on small{color:#D9D7D2}
.d .opts .aside{display:flex;align-items:center;gap:10px}
.d .opts .aside em{font-style:normal;font-size:13.5px;font-weight:700;color:var(--mid)}
.d .opts button.on .aside em{color:#D9D7D2}
/* fiche : marque et catégorie, alerte de prix */
.d .crumbs{position:absolute;left:12px;right:12px;bottom:12px;display:flex;flex-wrap:wrap;gap:8px}
.d .crumbs button{display:flex;align-items:center;gap:3px;border:0;background:rgba(255,255,255,.95);border-radius:999px;min-height:44px;padding:0 11px 0 15px;font-size:12.5px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;box-shadow:0 1px 4px rgba(0,0,0,.14)}
.d .crumbs .i{color:var(--mid)}
.d .aff{margin:8px 2px 0;font-size:12.5px;line-height:1.45;color:var(--mid)}
.d .lnk{border:0;background:none;padding:0;font:inherit;font-weight:800;color:var(--ink);text-decoration:underline;text-underline-offset:3px;min-height:44px}
.d .aff .lnk,.d .legal .lnk{display:inline-block;min-height:0;line-height:18px;padding:13px 0;margin:-13px 0}
.d .legal{padding:28px 16px 8px;font-size:12.5px;color:var(--mid);line-height:1.5}
.d .about{padding:0 16px 8px;max-width:680px}
.d .about h1{font-size:40px;margin:6px 0 0}
.d .about .lead{font-size:17px;line-height:1.5;margin:14px 0 0}
.d .about h2{font-size:18px;font-weight:800;letter-spacing:-.01em;margin:26px 0 0}
.d .about p,.d .about li{font-size:15px;line-height:1.55;color:#33363A}
.d .about p{margin:8px 0 0}.d .about ul{margin:8px 0 0;padding-left:20px}.d .about li{margin-top:6px}
.d .mbuy{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:12px 10px 0 0;min-height:50px;padding:0 14px 0 16px;border-radius:14px;background:var(--ink);color:#fff;text-decoration:none;font-size:14.5px;font-weight:700}
.d .mbuy b{font-weight:800;color:#FFB08F}
.d .alertbtn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;margin-top:10px;min-height:52px;border-radius:15px;border:1.5px solid var(--ink);background:var(--paper);font-size:15px;font-weight:800}
.d .alertbtn.on{border-color:var(--good);color:var(--good);background:#EAF5EF}
/* prix voulu */
.d .pchips{display:flex;flex-wrap:wrap;gap:8px}
.d .pchips button{border:0;background:var(--tint);border-radius:14px;min-height:56px;padding:7px 14px;text-align:left;display:flex;flex-direction:column;justify-content:center}
.d .pchips button b{font-size:17px;font-weight:800;letter-spacing:-.02em}
.d .pchips button span{font-size:12px;font-weight:700;color:var(--mid)}
.d .pchips button.on{background:var(--ink);color:#fff}.d .pchips button.on span{color:#D9D7D2}
.d .pinput{display:flex;align-items:center;gap:10px;margin-top:10px;border:1px solid #CFCFCA;border-radius:14px;padding:0 16px;min-height:56px;background:var(--paper)}
.d .pinput:focus-within{border-color:var(--ink)}
.d .pinput span{font-size:13px;font-weight:800;color:var(--mid);white-space:nowrap}
.d .pinput input,.d .sheet .pinput input{flex:1;align-self:stretch;min-width:0;width:auto;border:0;margin:0;padding:0;outline:0;background:transparent;font-size:20px;font-weight:800;color:var(--ink);text-align:right;-moz-appearance:textfield;appearance:textfield}
.d .pinput input::-webkit-outer-spin-button,.d .pinput input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
.d .pinput b{font-size:20px;font-weight:800}
.d .state{display:flex;align-items:center;gap:9px;margin-top:14px;font-size:14.5px;font-weight:700;color:var(--mid)}
.d .state i{width:9px;height:9px;border-radius:50%;background:var(--icon);flex:0 0 auto}
.d .state.ok{color:var(--good)}.d .state.ok i{background:var(--good);box-shadow:0 0 0 3px rgba(31,122,82,.15)}
/* recherche : un champ, trois filtres, des exemples ou vos recherches sur une ligne, un feed que la saisie adapte */
.d .sbar.big{height:58px;border-radius:18px;padding-left:18px;margin-top:14px}
.d .sbar.big input{font-size:17px;font-weight:600}
.d .filters{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px 2px}
.d .fchip{flex:0 0 auto;display:flex;align-items:center;gap:6px;border:1px solid #D9D6D0;background:var(--paper);border-radius:999px;min-height:44px;padding:0 12px 0 16px;font-size:14.5px;font-weight:700;white-space:nowrap}
.d .fchip.on{background:var(--ink);border-color:var(--ink);color:#fff}
.d .fchip .i{color:inherit;opacity:.75}
.d .tryit{padding:26px 16px 0}
.d .tryit h3{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--mid);margin:0 0 10px}
.d .ctags{display:flex;flex-wrap:wrap;gap:8px}
.d .ctags.row{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin:0 -16px;padding:0 16px}
.d .ctags.row::-webkit-scrollbar{display:none}
.d .ctags.row .ctag{flex:0 0 auto;white-space:nowrap}
.d .tryit .th{display:flex;align-items:center;justify-content:space-between;margin:-12px 0 -2px}
.d .tryit .th h3{margin:0}
.d .forget{border:0;background:none;min-height:44px;padding:0 0 0 12px;font-size:13.5px;font-weight:800;color:var(--mid);text-decoration:underline;text-underline-offset:3px}
.d .flow{transition:opacity .18s}
.d .flow.dim{opacity:.45}
.d .ctag{display:flex;align-items:center;gap:8px;border:0;background:var(--tint);border-radius:999px;min-height:44px;padding:0 16px;font-size:14.5px;font-weight:700}
.d .ctag.more{background:var(--paper);border:1px solid #D9D6D0;padding:0 12px 0 16px;gap:6px}
.d .ctag.on{background:var(--ink);color:#fff}
.d .bchips button{display:inline-flex;align-items:center;gap:6px}
.d .bchips button.on{background:var(--ink);color:#fff}
.d .bchips button.soft{background:var(--paper);box-shadow:inset 0 0 0 1.5px var(--line)}
.d .sw{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:20px 16px 0;padding:14px 16px;border-radius:18px;
  background:var(--tint);min-height:44px;width:calc(100% - 32px);border:0;text-align:left;font-size:14.5px;font-weight:700;color:var(--ink)}
.d .sw small{display:block;color:var(--mid);font-weight:600;font-size:13px;margin-top:3px;line-height:1.4}
.d .sw .knob{flex:0 0 auto;width:48px;height:30px;border-radius:15px;background:var(--paper);box-shadow:inset 0 0 0 2px var(--mid);position:relative}
.d .sw .knob:after{content:"";position:absolute;top:5px;left:5px;width:20px;height:20px;border-radius:50%;background:var(--mid);transition:left .2s}
.d .sw[aria-checked=true] .knob{background:var(--ink);box-shadow:none}
.d .sw[aria-checked=true] .knob:after{left:23px;background:#fff}
@media (prefers-reduced-motion:reduce){.d .sw .knob:after{transition:none}.d .fold button .i{transition:none}}
.d .brow{display:flex;align-items:center;gap:10px;width:calc(100% - 32px);margin:16px 16px 0;min-height:56px;border:0;border-radius:16px;background:var(--tint);padding:0 14px 0 16px;text-align:left}
.d .brow small{font-size:11.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--mid)}
.d .brow b{font-family:var(--serif);font-weight:400;font-size:24px;line-height:1}
.d .brow span{flex:1;font-size:13.5px;font-weight:700;color:var(--mid)}
.d .fchip.clear{border-color:transparent;background:none;color:var(--mid);padding:0 12px;gap:4px}
.d .note{color:var(--mid);font-size:13.5px;margin:10px 0 0;line-height:1.45}
.d .note{padding:0 16px}
.d .sechead + .note{margin:-4px 0 12px}
.d .mlist{display:flex;flex-direction:column;gap:12px;padding:0 16px}
.d .mi{border:1px solid var(--line);border-radius:20px;padding:14px 6px 14px 16px}
.d .mi .row{display:flex;justify-content:space-between;align-items:flex-start;gap:6px}
.d .mi .st{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:11.5px;font-weight:700;letter-spacing:.06em;color:var(--soft);margin-top:4px}
.d .mi .st i{width:8px;height:8px;border-radius:50%;background:var(--icon)}
.d .mi.ok .st{color:var(--good)}.d .mi.ok .st i{background:var(--good);box-shadow:0 0 0 3px rgba(31,122,82,.15)}
.d .mi h3{font-size:17px;font-weight:800;letter-spacing:-.02em;margin:5px 0 0;line-height:1.25}
.d .mi .nums{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:6px;font-family:var(--mono);font-size:12.5px;color:var(--mid)}
.d .mi .nums b{color:var(--ink)}.d .mi .nums b.ok{color:var(--good)}
.d .mi .scroller{padding:12px 10px 2px 0}
.d .near{display:flex;align-items:center;gap:12px;width:calc(100% - 10px);margin-top:12px;border:0;background:var(--tint);border-radius:14px;padding:8px 10px 8px 8px;text-align:left;min-height:64px}
.d .near .th{flex:0 0 48px;width:48px;height:48px;border-radius:10px;overflow:hidden;background:var(--tint2)}
.d .near .tx{flex:1;min-width:0;font-size:13.5px;font-weight:700;line-height:1.3}
.d .near .tx small{display:block;font-size:12px;font-weight:700;color:var(--mid);text-transform:uppercase;letter-spacing:.06em}
.d .near .tx span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.d .near b{font-size:16px;font-weight:800;letter-spacing:-.02em}
/* recherche v56 : les critères compris, en puces modifiables ; sauvegarder */
.d .crit{flex:0 0 auto;display:flex;align-items:center;background:var(--ink);color:#fff;border-radius:999px;min-height:44px}
.d .crit .cl{display:flex;align-items:center;border:0;background:none;color:inherit;min-height:44px;min-width:44px;padding:0 2px 0 15px;font-size:14.5px;font-weight:700;white-space:nowrap}
.d .crit .cx{border:0;background:none;color:inherit;width:44px;height:44px;display:grid;place-items:center;border-radius:999px;opacity:.85}
.d .savebtn{flex:0 0 auto;display:flex;align-items:center;gap:7px;border:1.5px solid var(--ink);background:var(--paper);border-radius:999px;min-height:44px;padding:0 15px;font-size:14px;font-weight:800}
.d .savebtn.on{background:var(--ink);color:#fff}
.d .savebar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 16px 14px;padding:10px 10px 10px 16px;border-radius:18px;background:var(--tint);font-size:14px;font-weight:700;color:var(--mid)}
.d .ctag em{font-style:normal;font-size:12.5px;font-weight:700;color:var(--mid)}
.d .ctag.on em{color:#D9D7D2}
.d .ctag em.new,.d .st em.new{font-style:normal;background:var(--accent);color:#fff;border-radius:999px;font-size:11px;font-weight:800;padding:2px 7px;line-height:1.3;letter-spacing:.02em}
.d .sechead > div .n{display:block;margin-top:4px}
/* v60 : Affiner en entonnoir — une question à la fois, chaque réponse avec son nombre de produits, une fin.
   v61 : dans les teintes de la page (fond tint, pilules et options blanches à filet), pas de bloc sombre */
.d .funnel{margin:14px 16px 0;background:var(--tint);color:var(--ink);border-radius:20px;padding:16px}
.d .funnel .k{display:flex;align-items:center;gap:8px;min-height:16px;font-family:var(--mono);font-size:11.5px;font-weight:700;letter-spacing:.08em;color:var(--mid)}
.d .funnel .k i{width:7px;height:7px;border-radius:50%;background:var(--ink)}
.d .funnel .prog{display:flex;gap:4px;margin-left:auto}
.d .funnel .prog b{width:14px;height:4px;border-radius:2px;background:var(--tint2)}
.d .funnel .prog b.on{background:var(--ink)}.d .funnel .prog b.at{background:var(--accent)}
.d .fpath{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.d .fstep{display:flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:999px;min-height:44px;padding:0 12px 0 15px;font-size:14px;font-weight:700;white-space:nowrap}
.d .fstep .i{opacity:.7}
.d .fstep.fixed{background:none;border-style:dashed;border-color:#D9D6D0;color:var(--mid);padding:0 15px}
.d .fq{animation:fin .22s ease-out}
.d .funnel h3{margin:14px 0 0;font-family:var(--serif);font-weight:400;font-size:28px;line-height:1.1;letter-spacing:-.01em;color:var(--ink)}
.d .fopts{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.d .fopt{display:flex;align-items:center;gap:10px;border:1px solid #D9D6D0;background:var(--paper);color:var(--ink);border-radius:14px;min-height:48px;padding:0 14px 0 16px;font-size:15px;font-weight:800;text-align:left}
.d .fopt em{font-style:normal;font-family:var(--mono);font-size:12.5px;font-weight:700;color:var(--mid)}
.d .fskip{display:block;border:0;background:none;color:var(--mid);font-size:14px;font-weight:700;min-height:44px;padding:0 2px;margin-top:4px;text-decoration:underline;text-underline-offset:3px}
.d .funnel .done{display:flex;flex-wrap:wrap;align-items:center;gap:10px 12px;margin:14px 0 6px}
.d .funnel .done .ok{flex:0 0 auto;width:32px;height:32px;border-radius:50%;background:var(--good);color:#fff;display:grid;place-items:center}
.d .funnel .done h2{flex:1;color:var(--ink);font-size:30px}
.d .funnel .done .fskip{flex-basis:100%;margin-top:0}
.d .fskip.pass{display:flex;align-items:center;width:max-content;min-height:44px;margin-top:12px;border-radius:999px;background:var(--accent-soft);color:var(--accent-ink);padding:0 18px;font-size:14.5px;font-weight:800;text-decoration:none}
.d .funnel .fnone{margin:14px 0 8px;color:var(--mid);font-size:14px;font-weight:600}
@keyframes fin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.d .fq{animation:none}}
@media (hover:hover){.d .fskip.pass:hover{background:#F8D9CB}.d .fopt:hover{border-color:var(--ink)}.d button.fstep:hover{background:var(--tint2)}}
/* profil : le centre de commande */
.d .idline{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:4px 14px;margin:14px 16px 0;padding:12px 16px;border-radius:16px;background:var(--tint);font-size:14px;color:var(--mid);font-weight:600}
.d .idline b{color:var(--ink)}
.d .mi .mopen{flex:1;min-width:0;border:0;background:none;padding:0;text-align:left;display:flex;flex-direction:column;min-height:44px}
.d .mi .macts{display:flex;flex:0 0 auto}
.d .ibtn.on{color:var(--accent)}
.d .out{padding:18px 0 0}
/* v58 : le Profil aéré — des titres seuls, vos rayons repliés */
.d .profile .psec{margin-top:40px}
.d .profile .psec .sechead{padding-top:0;padding-bottom:0;min-height:48px}
.d .profile .psec > * + *{margin-top:14px}
.d .profile .psec .sw{margin-top:0}
.d .profile .out{padding-top:40px}
.d .fold{margin:0;padding:0 16px}
.d .fold button{display:flex;align-items:center;gap:12px;width:100%;min-height:48px;border:0;background:none;padding:0;text-align:left;font:inherit;color:inherit}
.d .fold button span{flex:1;min-width:0}
.d .fold button small{font-family:var(--mono);font-size:12px;color:var(--soft);letter-spacing:normal}
.d .fold button .i{flex:0 0 auto;color:var(--mid);transition:transform .2s}
.d .fold button[aria-expanded=true] .i{transform:rotate(180deg)}
.d .confirm{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin:12px 16px 0;padding:14px 16px;border-radius:16px;background:var(--accent-soft);font-size:14px;font-weight:700}
.d .confirm .ghost{margin:0}
.d .danger{border:0;background:var(--accent-ink);color:#fff;border-radius:999px;min-height:44px;padding:0 18px;font-size:14px;font-weight:800}
.d .toast{position:fixed;bottom:104px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 18px;border-radius:999px;font-size:14px;font-weight:700;z-index:11;white-space:nowrap}
nav.d-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:520px;display:grid;grid-template-columns:repeat(4,1fr);gap:4px;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid var(--line);z-index:5;padding:6px 8px calc(10px + env(safe-area-inset-bottom))}
.d-nav button{position:relative;border:0;background:none;min-height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;font-size:12px;font-weight:700;color:var(--soft);border-radius:16px}
.d-nav button.on{color:var(--ink);font-weight:800}
.d-nav .ic{position:relative}
.d-nav .dot,.d .tabs .dot{min-width:17px;height:17px;border-radius:9px;background:var(--accent);color:#fff;font-size:10.5px;font-weight:800;line-height:17px;padding:0 5px;text-align:center}
.d-nav .dot{position:absolute;top:-5px;left:15px}
@media (min-width:1000px){
  .d .app{max-width:1240px;padding:0 32px 56px}
  .d .top{height:76px;padding:0;position:sticky;top:0;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);z-index:6}
  .d .logo{font-size:36px}
  .d .tabs{display:flex;gap:4px;margin-left:auto;margin-right:8px}
  .d .tabs button{border:0;background:none;min-height:44px;padding:0 16px;border-radius:12px;font-size:14.5px;font-weight:800;color:var(--soft);display:flex;align-items:center;gap:7px}
  .d .tabs button.on{background:var(--tint);color:var(--ink)}
  nav.d-nav{display:none}
  .d .toast{bottom:32px}
  .d .ticker{border-radius:12px;margin-bottom:8px}
  .d .intro,.d .sechead,.d .pagehead{padding-left:0;padding-right:0}
  .d .sbar{margin-left:0;margin-right:0;max-width:640px}
  .d .chips,.d .rooms,.d .masonry,.d .scroller,.d .bchips,.d .me,.d .mlist,.d .note,.d .filters,.d .tryit{padding-left:0;padding-right:0}
  .d .idline,.d .savebar,.d .confirm{margin-left:0;margin-right:0}
  .d .funnel{margin-left:0;margin-right:0;max-width:760px;padding:20px 22px 12px}
  .d .profile .psec{margin-top:48px}.d .fold{padding:0}
  .d .profile .sw{margin-left:0;margin-right:0}.d .profile .out > .ghost{padding-left:0;padding-right:0}
  .d .center{max-width:900px}
  .d .brow{margin-left:0;margin-right:0;width:100%;max-width:640px}
  .d .ctags.row{flex-wrap:wrap;margin:0;padding:0}
  .d .legal,.d .about{padding-left:0;padding-right:0}
  .d h1{font-size:64px}
  .d .room{width:228px;height:292px}
  .d .rooms{scroll-padding-inline:0}
  .d .masonry{gap:20px}
  .d .item{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:44px;align-items:start;padding-top:8px}
  .d .item .hero{position:sticky;top:96px;border-radius:24px;overflow:hidden}
  .d .item .hero .vis{max-height:none}
  .d .item .info{padding-left:0;padding-right:0;padding-top:0}
  .d .sheet-wrap{align-items:center}.d .sheet{border-radius:26px}
}
@media (hover:hover){.d .card:hover .vis{filter:brightness(.97)}.d .chips button:hover,.d .ctag:hover,.d .brow:hover{background:var(--tint2)}.d .chips button.on:hover,.d .ctag.on:hover{background:var(--ink)}}
`;

/* Une feuille se ferme aussi avec Échap. */
function useEscape(onClose, on = true) {
  useEffect(() => {
    if (!on) return;
    const f = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [onClose, on]);
}

function Toast({ text }) {
  return text ? <div className="toast" role="status">{text}</div> : null;
}

/* Ajouter son e-mail (facultatif) : pour recevoir les alertes par e-mail et retrouver ce qu'on a gardé sur un autre
   appareil. Le lien ouvert rattache l'adresse au compte invité de cet appareil (rien n'est perdu). */
function EmailSheet({ reason, onClose, onDone }) {
  useEscape(onClose);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState(null);
  const submit = async e => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await api("auth/request", { email }); setSent(true); }
    catch (ex) { setErr(ex.message); }
    finally { setBusy(false); }
  };
  return <div className="sheet-wrap" onClick={onClose}>
    <form className="sheet" role="dialog" aria-modal="true" aria-labelledby="email-h" onClick={e => e.stopPropagation()} onSubmit={submit}>
      {!sent ? <>
        <div className="eyebrow">Facultatif</div>
        <h2 id="email-h">{reason || "Ajouter votre e-mail"}</h2>
        <p className="hint">Pour recevoir vos alertes par e-mail et retrouver vos favoris, vos marques et vos recherches sur un autre
          appareil. Un lien vous est envoyé : aucun mot de passe. Sans e-mail, tout reste gardé sur cet appareil.</p>
        <input type="email" required autoFocus value={email} onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.fr" aria-label="Adresse e-mail" />
        {err && <div className="err">{err}</div>}
        <button className="cta" disabled={busy}>Recevoir le lien</button>
      </> : <>
        <div className="eyebrow">Lien envoyé</div>
        <h2 id="email-h">Ouvrez le lien reçu.</h2>
        <p className="hint">Il est valable 15 minutes. Ce que vous avez gardé ici passe sur votre adresse.</p>
        <button type="button" className="cta" autoFocus onClick={onDone}>J'ai ouvert le lien</button>
      </>}
    </form>
  </div>;
}

/* Vos marques : toutes celles du catalogue, à suivre ou non, d'un geste ; un champ pour trouver la sienne. */
function BrandSheet({ brands, followed, onToggle, onClose }) {
  useEscape(onClose);
  const box = useRef(null);
  useEffect(() => { box.current?.focus(); }, []);
  const [find, setFind] = useState("");
  const shown = brands.filter(b => b.products > 0 && norm(b.name).includes(norm(find)));
  return <div className="sheet-wrap" onClick={onClose}>
    <div className="sheet" ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="brands-h" onClick={e => e.stopPropagation()}>
      <div className="eyebrow">Profil</div>
      <h2 id="brands-h">Vos marques</h2>
      <p className="hint">Leurs remises passent en tête, partout dans l'app.</p>
      <input value={find} onChange={e => setFind(e.target.value)} placeholder="Une marque…" aria-label="Chercher une marque" />
      <div className="opts" style={{ marginTop: 12 }}>{shown.map(b => {
        const on = followed.has(b.name);
        return <button key={b.name} className={on ? "on" : ""} aria-pressed={on} onClick={() => onToggle(b.name)}>
          <span><b>{b.name}</b><small>{plural(b.products, "produit")}{b.count > 0 ? ` · ${plural(b.count, "remise")}` : ""}</small></span>
          <span className="aside">{on ? <Icon d={UI.check} size={18} sw={2.4} /> : <Icon d={UI.plus} size={18} sw={2.2} />}</span></button>;
      })}</div>
      <button className="cta" onClick={onClose}>Terminé</button>
    </div>
  </div>;
}

/* « Me prévenir sous un prix », depuis la fiche : ce produit, ou tous les comparables (même catégorie, mêmes fonctions,
   même taille : la règle est côté serveur) ; trois prix proposés ou le sien. */
function AlertSheet({ item, current, onClose, onLaunch, onStop }) {
  useEscape(onClose);
  const box = useRef(null);
  useEffect(() => { box.current?.focus(); }, []);           // le focus entre dans la feuille
  const sugg = suggestions(item);
  const [mode, setMode] = useState("product");
  const [price, setPrice] = useState(String(current ? Math.round(current.max_price) : sugg[0]?.[0] ?? ""));
  const [like, setLike] = useState(null);                  // aperçu des comparables : ce qui est guetté, ce qui y répond déjà
  const [busy, setBusy] = useState(false);
  const n = Number(price), ok = price !== "" && n >= 1;
  useEffect(() => {
    const t = setTimeout(() => api("missions/preview", { like: item.id, max_price: ok ? n : null }).then(setLike).catch(() => setLike(null)), 250);
    return () => clearTimeout(t);
  }, [price]);
  const status = !ok ? null : mode === "product"
    ? (item.price <= n ? { ok: true, text: `Déjà à ${eur(item.price)} aujourd'hui` } : { text: `Aujourd'hui ${eur(item.price)} : encore ${eur(item.price - n)}` })
    : like && (like.total > 0 ? { ok: true, text: `${plural(like.total, "comparable")} déjà sous ${eur(n)} aujourd'hui` }
      : like.nearest ? { text: `Le moins cher aujourd'hui : ${eur(like.nearest.price)}` } : { text: "Aucun comparable pour l'instant : l'alerte guette les nouveaux" });
  const launch = async () => {
    setBusy(true);
    const done = await onLaunch(mode === "like" ? { like: item.id, max_price: n } : { product_id: item.id, max_price: n });
    setBusy(false);
    if (done) onClose();
  };
  return <div className="sheet-wrap" onClick={onClose}>
    <div className="sheet" ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="alert-h" onClick={e => e.stopPropagation()}>
      <div className="eyebrow">Alerte de prix</div>
      <h2 id="alert-h">Me prévenir sous un prix</h2>
      <h3>Pour</h3>
      <div className="opts">
        {[["product", "Ce produit", `${item.brand} ${item.name || item.title}`], ["like", "Tous les comparables", like ? like.title : item.kind]].map(([k, l, sub]) =>
          <button key={k} className={mode === k ? "on" : ""} aria-pressed={mode === k} onClick={() => setMode(k)}>
            <span><b>{l}</b><small>{sub}</small></span>{mode === k && <Icon d={UI.check} size={18} sw={2.4} />}</button>)}
      </div>
      <h3>Prix maximum</h3>
      <div className="pchips">{sugg.map(([v, l]) => <button key={v} className={ok && n === v ? "on" : ""} aria-pressed={ok && n === v}
        onClick={() => setPrice(String(v))}><b>{eur(v)}</b><span>{l}</span></button>)}</div>
      <label className="pinput"><span>Mon prix</span>
        <input type="number" inputMode="numeric" min="1" value={price} onChange={e => setPrice(e.target.value)} aria-label="Mon prix maximum, en euros" /><b>€</b></label>
      {status && <div className={`state ${status.ok ? "ok" : ""}`} role="status"><i />{status.text}</div>}
      <button className="cta" disabled={!ok || busy} onClick={launch}>{ok ? `Me prévenir sous ${eur(n)}` : "Me prévenir"}</button>
      {current && <button className="ghost" onClick={() => { onStop(current); onClose(); }}>Arrêter l'alerte à {eur(current.max_price)}</button>}
      <p className="hint">Votre alerte est dans Profil, avec vos recherches ; par e-mail aussi, si vous ajoutez votre adresse.</p>
    </div>
  </div>;
}

/* Un filtre ou un tri de la Recherche : une liste, un choix, la feuille se ferme. */
function ChoiceSheet({ title, options, value, onPick, onClose }) {
  useEscape(onClose);
  const box = useRef(null);
  useEffect(() => { box.current?.focus(); }, []);
  return <div className="sheet-wrap" onClick={onClose}>
    <div className="sheet" ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}>
      <div className="eyebrow">Recherche</div>
      <h2>{title}</h2>
      <div className="opts" style={{ marginTop: 14 }}>{options.map(([v, label, count]) =>
        <button key={v} className={value === v ? "on" : ""} aria-pressed={value === v} onClick={() => { onPick(v); onClose(); }}
          aria-label={count != null ? `${label}, ${plural(count, "produit")}` : undefined}>
          <span><b>{label}</b></span><span className="aside">{count != null && <em>{count}</em>}{value === v && <Icon d={UI.check} size={18} sw={2.4} />}</span></button>)}</div>
    </div>
  </div>;
}

/* Bandeau : les remises du jour défilent, comme un fil de cotations. */
function Ticker({ items, publishedAt }) {
  if (!items.length) return null;
  const run = items.slice(0, 24).map(p => <span className="tk" key={p.id}><b className="dn">▼</b>{p.brand.toUpperCase()} · {p.kind.toUpperCase()}
    <b className="pc">−{p.pct} %</b>{eur(p.price)}</span>);
  return <div className="ticker" role="marquee" aria-label={`${items.length} remises aujourd'hui`}>
    <span className="live"><i />{publishedAt ? `MAJ ${shortDay(publishedAt).toUpperCase()} ${clock(publishedAt)}` : "AUJOURD'HUI"}</span>
    <div className="tape"><div className="run" style={{ animationDuration: `${Math.max(28, items.length * 5)}s` }}>
      {run}<span aria-hidden="true" style={{ display: "inline-flex" }}>{run}</span></div></div>
  </div>;
}

/* Mosaïque : chaque carte va dans la colonne la moins haute ; l'ordre du classement se lit de gauche à droite. */
function Masonry({ items, cols, render }) {
  const columns = Array.from({ length: cols }, () => ({ h: 0, items: [] }));
  for (const p of items) {
    const c = columns.reduce((a, b) => (b.h < a.h - 0.01 ? b : a));
    c.items.push(p); c.h += ratioOf(p.category) + 0.45;
  }
  return <div className="masonry" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
    {columns.map((c, i) => <div key={i} className="mcol">{c.items.map(render)}</div>)}</div>;
}

/* Affiner en entonnoir (v60, deals/funnel.py) : une question à la fois — l'univers, le rayon, le type, un attribut, le
   budget —, chaque réponse avec son nombre de produits ; « Passer » passe à la suivante (l'app s'en souvient) ;
   quand il n'y a plus de question, c'est votre sélection. Les étapes franchies, en haut, se retirent d'un geste ; un
   rayon que la sélection dit d'elle-même (une marque qui ne fait que des téléviseurs) reste. at : funnelAt(…). */
function Funnel({ at, total, onAnswer, onBack, onSkip, onRestart, keep }) {
  if (!at || (!at.q && !at.done)) return null;                          // rien à demander, rien de choisi
  const { path, q, done } = at, steps = done + at.open.length;
  return <section className="funnel" aria-label="Affiner">
    <div className="k"><i />{q ? "AFFINER" : "VOTRE SÉLECTION"}{q && steps > 1 && <span className="prog" aria-hidden="true">
      {Array.from({ length: steps }, (_, i) => <b key={i} className={i < done ? "on" : i === done ? "at" : ""} />)}</span>}</div>
    {path.length > 0 && <div className="fpath">{path.map(s => s.fixed
      ? <span key={s.level + s.key} className="fstep fixed">{s.label}</span>
      : <button key={s.level + s.key} className="fstep" onClick={() => onBack(s)} aria-label={`Retirer ${s.label}`}>{s.label}
        <Icon d={UI.x} size={13} sw={2.6} /></button>)}</div>}
    {q ? <div className="fq" key={q.level + q.key}>
      <h3>{q.title}</h3>
      <div className="fopts">{q.options.map(o => <button key={o.label} className="fopt" onClick={() => onAnswer(o.set)}
        aria-label={`${o.label}, ${plural(o.count, "produit")}`}><span>{o.label}</span><em>{o.count}</em></button>)}</div>
      <button className="fskip pass" onClick={() => onSkip(q.key)}>Passer</button>
    </div> : total > 0 ? <div className="done">
      <span className="ok"><Icon d={UI.check} size={18} sw={2.6} /></span>
      <h2>{plural(total, "produit")}</h2>
      {keep}
      {onRestart && <button className="fskip" onClick={onRestart}>Recommencer</button>}
    </div> : <p className="fnone">Rien ici : retirez une étape.</p>}
  </section>;
}

export default function App() {
  const [tab, setTab] = useState("tops");          // tops (Top deals, au lancement) | home (Explorer) | search | me
  const [view, setView] = useState(null);          // null | item | brand | category | room | about — chacune garde `from` (« Retour »)
  const [q, setQ] = useState("");                  // Recherche : la phrase tapée
  const [crit, setCrit] = useState(NO_CRIT);       // Recherche : les critères choisis dans l'app (puces, entonnoir), qui l'emportent
  const [skip, setSkip] = useState([]);            // Recherche : les questions de l'entonnoir passées (« Passer »)
  const [all, setAll] = useState(null);            // remises du jour (bandeau, notre sélection)
  const [top, setTop] = useState(null);            // top deals (leur onglet)
  const [allCats, setAllCats] = useState([]);      // toutes les catégories (count : remises du jour)
  const [allBrands, setAllBrands] = useState([]);  // toutes les marques (count : remises du jour)
  const [picking, setPicking] = useState(null);    // feuille ouverte : off | sort | brands
  const [results, setResults] = useState(null);    // Recherche : la réponse (produits, critères compris, puces)
  const [searching, setSearching] = useState(false);  // une réponse est attendue : les résultats montrés pâlissent
  const [feed, setFeed] = useState(null);          // Recherche : le feed d'avant toute saisie
  const [recent, setRecent] = useState(() => recents.get());
  const [seen, setSeen] = useState([]);            // fiches ouvertes et clics de la visite (le serveur n'en garde rien)
  const [you, setYou] = useState(null);            // Explorer : « pour vous »
  const [taste, setTaste] = useState(null);        // Profil : ce que l'app retient et a compris
  const [guestVariant] = useState(() => Math.random() < 0.1 ? "t" : "p"); // sans compte : une visite sur dix est témoin
  const seq = useRef(0);                           // seule la réponse à la dernière saisie compte
  const [order, setOrder] = useState("pct");       // pages marque, catégorie, pièce : pct | asc | desc
  const [pc, setPc] = useState(NO_CRIT);           // pages : ce qui y est choisi dans l'entonnoir
  const [pskip, setPskip] = useState([]);          // pages : les questions passées
  const [pres, setPres] = useState(null);          // pages : la réponse (une Recherche fixée sur la marque, la catégorie, la pièce)
  const pseq = useRef(0);
  const [item, setItem] = useState(null);
  const [missions, setMissions] = useState(null);  // vos recherches sauvegardées (missions) : { missions, reached, fresh }
  const [alertOpen, setAlertOpen] = useState(false);
  const [session, setSession] = useState({ checked: false, email: null, guest: false, variant: "p" });
  const [saved, setSaved] = useState(new Set());
  const [followed, setFollowed] = useState(new Set());
  const [picks, setPicks] = useState([]);          // vos rayons
  const [raysOpen, setRaysOpen] = useState(false); // Profil : vos rayons, repliés tant qu'on ne les ouvre pas
  const [savedList, setSavedList] = useState(null);
  const [version, setVersion] = useState(0);
  const [emailFor, setEmailFor] = useState(null);  // ajouter son e-mail : pourquoi (feuille ouverte)
  const [erase, setErase] = useState(false);       // « Effacer mes données » : la confirmation est montrée
  const [toast, setToast] = useState(null);
  const [legal, setLegal] = useState(null);         // mentions légales : l'identité de l'éditeur, lue au serveur
  const [error, setError] = useState(null);
  const width = useWidth();
  const cols = width >= 1200 ? 5 : width >= 1000 ? 4 : width >= 700 ? 3 : 2;

  const flash = t => { setToast(t); setTimeout(() => setToast(null), 2400); };
  const known = !!(session.email || session.guest);                       // un compte (invité ou avec adresse) garde vos choix
  const refreshSession = () => api("auth/me")
    .then(d => setSession({ checked: true, email: d.email, guest: !!d.guest, variant: d.variant || "p" }))
    .catch(() => setSession({ checked: true, email: null, guest: false, variant: "p" }));
  // Garder quelque chose (favori, marque, rayon, recherche) : sans compte, le serveur crée un compte invité, sans e-mail.
  // Tant qu'il n'existe pas, les gestes passent l'un après l'autre : le premier crée le compte, les suivants y vont.
  const first = useRef(Promise.resolve());
  const keep = (path, body) => {
    if (known) return api(path, body);
    const run = first.current.then(() => api(path, body)).then(async d => { await refreshSession(); return d; });
    first.current = run.catch(() => {});
    return run;
  };
  const variant = known ? session.variant : guestVariant;                // p : vos goûts comptent ; t : témoin, sans
  // Ce que les lectures emportent de vos goûts : vos recherches récentes, les fiches de la visite (utiles sans compte, ou
  // quand le compte n'apprend pas des fiches) ; sans compte, si la visite est témoin.
  const tq = useMemo(() => {
    const ps = new URLSearchParams();
    if (recent.length) ps.set("recent", recent.join("|"));
    if (seen.length) ps.set("p", seenParam(seen));
    if (!known && variant === "t") ps.set("v", "t");
    const s = ps.toString();
    return s ? `?${s}` : "";
  }, [recent, seen, variant, known]);

  useEffect(() => {
    refreshSession();
    const url = new URL(window.location.href);
    if (url.searchParams.get("auth") === "expired") flash("Ce lien a expiré. Demandez-en un nouveau.");
    const shared = Number(url.searchParams.get("p"));                       // lien partagé, ou e-mail de mission : /?p=<produit>
    if (shared) setView({ kind: "item", id: shared, via: url.searchParams.get("from") === "mail" ? "mail" : undefined,
                          mission: Number(url.searchParams.get("m")) || undefined });
    if (Number(url.searchParams.get("mission"))) { setTab("me"); flash("Recherche sauvegardée : on vous prévient"); }
    if (["auth", "p", "mission"].some(k => url.searchParams.has(k))) window.history.replaceState({}, "", url.pathname);
    const again = () => { if (document.visibilityState === "visible") refreshSession(); };
    document.addEventListener("visibilitychange", again);
    return () => document.removeEventListener("visibilitychange", again);
  }, []);

  // Des lectures relancées coup sur coup (goûts, version) : seule la réponse à la dernière demande s'applique.
  const asked = useRef({});
  const latest = key => { const n = (asked.current[key] || 0) + 1; asked.current[key] = n; return f => d => { if (asked.current[key] === n) f(d); }; };

  useEffect(() => {                                                         // ce que vous gardez : favoris, marques, rayons, recherches
    if (!session.checked) return;
    const ok = latest("kept");
    if (!known) { setSaved(new Set()); setFollowed(new Set()); setSavedList(null); setPicks([]); setMissions(null); return; }
    api("follows").then(ok(d => setFollowed(new Set(d.brands)))).catch(() => {});
    api("saves").then(ok(d => { setSavedList(d.products); setSaved(new Set(d.products.map(p => p.id))); })).catch(() => {});
    api("missions").then(ok(setMissions)).catch(() => {});
    api("profile").then(ok(d => setPicks(d.picks || []))).catch(() => {});
  }, [session.checked, known, version, tab]);

  useEffect(() => {                                                         // v55 : des rayons gardés par le navigateur passent sur un compte
    if (!session.checked) return;
    const old = cleanPicks(PICKS.get()), learned = LEARN.get() === true;
    if (!old.length && !learned) return;
    (async () => {
      try {
        if (old.length) await keep("interests", { categories: old });
        if (learned) await keep("profile", { learn: true });
      } catch { /* réessayé à la prochaine visite */ return; }
      PICKS.set(null); LEARN.set(null); SEEN.set(null); PICKER.set(null);
      setVersion(v => v + 1);
    })();
  }, [session.checked]);

  useEffect(() => {                                                         // fiche ouverte, et d'où : le taux de clic
    if (view?.kind !== "item") return;
    api("view", { product_id: view.id, from: view.via || "item", m: view.mission, v: variant }).catch(() => {});
    note("v", view.id);                                                     // la visite s'en souvient (envoyé avec les lectures)
  }, [view]);

  useEffect(() => {                                                         // Profil : ce que l'app retient et a compris
    if (tab !== "me" || view) return;
    api(`profile${tq}`).then(latest("taste")(setTaste)).catch(() => {});
  }, [tab, view, tq, session.email, session.guest, version]);

  useEffect(() => {
    api("categories?all=1").then(setAllCats).catch(() => setError("Impossible de charger les catégories."));
    api("brands?all=1").then(setAllBrands).catch(() => {});
  }, [version]);

  useEffect(() => {                                                         // top deals ; Explorer : pour vous, sélection — selon vos goûts
    if (!session.checked) return;
    const ok = latest("home");
    api(`today${tq}`).then(ok(d => { setAll(d); setError(null); })).catch(() => setError("Impossible de charger les remises."));
    api(`top${tq}`).then(ok(setTop)).catch(() => {});
    api(`foryou${tq}`).then(ok(setYou)).catch(() => {});
  }, [version, tq, session.checked, known]);

  useEffect(() => {                                                         // le feed de la Recherche, prêt avant d'y aller
    if (!session.checked) return;
    api(`search${tq}`).then(latest("feed")(setFeed)).catch(() => {});
  }, [tq, version, session.checked, known]);

  useEffect(() => {                                                         // Recherche : une phrase, des critères
    const term = q.trim(), any = term || hasCrit(crit);
    const n = ++seq.current;
    if (view || tab !== "search") return;                                   // une fiche ouverte : les résultats attendent le retour
    if (!any) { setResults(null); setSearching(false); return; }            // plus rien de demandé : le feed
    setSearching(true);
    const t = setTimeout(() => api(`search?${searchParams(term, crit)}`)
      .then(d => { if (n === seq.current) { setResults({ ...d, _q: term }); setSearching(false); } })
      .catch(() => { if (n === seq.current) setSearching(false); }), term ? 120 : 0);
    return () => clearTimeout(t);
  }, [tab, q, crit, view, version]);

  useEffect(() => {
    if (!view) return;
    setError(null);
    if (view.kind === "item") api(`item/${view.id}`).then(setItem).catch(() => setError("Produit introuvable."));
  }, [view, version]);

  // Pages d'une marque, d'une catégorie, d'une pièce (v60) : une Recherche fixée sur elles (ctx), avec l'entonnoir et un
  // tri. Ce qu'on y choisit (pc), ce qu'on y passe (pskip) et le tri (order) les suivent quand on ouvre une fiche et revient.
  const isPage = v => v?.kind === "brand" || v?.kind === "category" || v?.kind === "room";
  const ctxOf = v => v.kind === "brand" ? { brand: v.name } : v.kind === "category" ? { category: v.key } : { room: v.room.key, off: 1 };
  const pageKey = v => isPage(v) ? `${v.kind}:${v.name || v.key || v.room.key}` : null;
  const pageParams = isPage(view) ? searchParams("", { ...pc, ...ctxOf(view), sort: PAGE_SORT[order] }).toString() : null;
  useEffect(() => {
    if (!pageParams) return;
    const n = ++pseq.current, k = pageKey(view);
    api(`search?${pageParams}`).then(d => { if (n === pseq.current) setPres({ ...d, _p: pageParams, _k: k }); })
      .catch(() => { if (n === pseq.current) setError("Impossible de charger cette page."); });
  }, [pageParams, version]);

  useEffect(() => { window.scrollTo(0, 0); setAlertOpen(false); setPicking(null); setErase(false); }, [view, tab]);

  const isSaved = id => saved.has(id);
  const isFollowed = b => followed.has(b);

  const toggleSave = async (id, e) => {
    if (e) e.stopPropagation();
    const on = !saved.has(id), first = !known;
    setSaved(s => on ? withIn(s, id) : withOut(s, id));
    try { await keep("save", { product_id: id, on }); setVersion(v => v + 1); if (on && first) flash("Gardé dans votre Profil, sans e-mail"); }
    catch (ex) { setSaved(s => on ? withOut(s, id) : withIn(s, id)); flash(ex.message); }
  };

  const toggleFollow = async brand => {
    const on = !followed.has(brand);
    setFollowed(s => on ? withIn(s, brand) : withOut(s, brand));
    try { await keep("brand/follow", { brand, on }); setVersion(v => v + 1); flash(on ? `${brand} est suivie` : `${brand} n'est plus suivie`); }
    catch (ex) { setFollowed(s => on ? withOut(s, brand) : withIn(s, brand)); flash(ex.message); }
  };

  const logout = async () => {
    await api("auth/logout", {}).catch(() => {});
    setSession({ checked: true, email: null, guest: false, variant: "p" });
    flash("Vous êtes déconnecté");
  };
  const eraseAll = async () => {
    try { await api("account/delete", {}); } catch (ex) { flash(ex.message); return; }
    setSeen([]); forget(); setSession({ checked: true, email: null, guest: false, variant: "p" }); setErase(false);
    flash("Vos données sont effacées");                                    // le compte, et ce que ce navigateur gardait
  };

  // Vos goûts : une fiche ouverte, une offre vue (la visite s'en souvient), vos rayons, ce qu'on retient.
  const note = (k, id) => setSeen(list => [...list.filter(e => !(e.k === k && e.id === id)), { k, id, t: Math.floor(Date.now() / 1000) }].slice(-SEEN_MAX));
  const togglePick = async key => {
    const before = picks, next = picks.includes(key) ? picks.filter(k => k !== key) : [...picks, key].slice(0, PICKS_MAX);
    setPicks(next);
    try { await keep("interests", { categories: next }); setVersion(v => v + 1); if (!before.length && next.length) flash("C'est noté : vos rayons passent en tête"); }
    catch (ex) { setPicks(before); flash(ex.message); }
  };
  const setLearn = async on => {
    setTaste(t => t && { ...t, learn: on });                                // l'interrupteur bascule aussitôt
    try { await keep("profile", { learn: on }); setVersion(v => v + 1); flash(on ? "Vos fiches ouvertes affineront vos deals" : "Vos fiches ouvertes ne comptent plus d'une visite à l'autre"); }
    catch { setTaste(t => t && { ...t, learn: !on }); flash("Impossible d'enregistrer ce choix"); }
  };
  const forgetTaste = async () => {
    setSeen([]);
    if (known) { try { await api("profile/reset", {}); } catch { flash("Impossible pour le moment"); return; } }
    setVersion(v => v + 1); flash("C'est oublié");
  };

  const share = async p => {
    const url = `${window.location.origin}/?p=${p.id}`, title = `${p.brand} — ${p.name || p.title}`;
    try {
      if (navigator.share) await navigator.share({ title, url });
      else { await navigator.clipboard.writeText(url); flash("Lien copié"); }
    } catch { /* partage annulé */ }
  };

  // Ce que la personne cherche, en mots : sa phrase, ou ses critères ; retenu quand elle ouvre une fiche trouvée ou valide.
  const intent = hasCrit(crit) && results?.chips ? results.chips.filter(c => c.id !== "sort" || results.criteria?.sort === "price")
    .map(c => c.label.replace(/[«»]/g, "").trim()).join(" · ") : q.trim();             // relue, la phrase redonne les mêmes critères
  const remember = text => {
    const t = (text || "").trim();
    if (t.length < 2) return;
    setRecent(list => {
      if (norm(list[0] || "") === norm(t)) return list;
      const next = [t, ...list.filter(x => norm(x) !== norm(t))].slice(0, RECENT_MAX);
      recents.set(next); return next;
    });
  };
  const forget = () => { setRecent([]); recents.set([]); };
  const goTab = t => { setView(null); setItem(null); setTab(t); setQ(""); setSkip([]);
    setCrit(NO_CRIT); if (t === tab && !view) window.scrollTo(0, 0); };   // l'onglet déjà ouvert : en haut
  // Chaque vue garde celle d'où l'on vient : « Retour » y ramène. via : d'où vient la fiche (mesure des clics sortants).
  const snap = v => isPage(v) ? { ...v, crit: pc, skip: pskip, order } : v;   // une page quittée garde ce qu'on y a choisi
  const open = (id, via, mission) => { if (via === "search") remember(intent); setItem(null); setView(v => ({ kind: "item", id, via, mission, from: snap(v) })); };
  const openAbout = () => setView(v => ({ kind: "about", from: v }));
  const openLegal = () => setView(v => ({ kind: "legal", from: v }));
  useEffect(() => { if (view?.kind === "legal" && !legal) api("legal").then(setLegal).catch(() => {}); }, [view, legal]);
  const openPage = page => { setPc(NO_CRIT); setPskip([]); setOrder("pct"); setView(v => ({ ...page, from: snap(v) })); };
  const openBrand = name => openPage({ kind: "brand", name });
  const openCategory = key => openPage({ kind: "category", key });
  const openRoom = room => openPage({ kind: "room", room });
  const goBack = () => {
    const b = view?.from || null;
    setItem(null);
    if (isPage(b)) { setPc(b.crit || NO_CRIT); setPskip(b.skip || []); setOrder(b.order || "pct"); }
    setView(b);
  };

  // Ce que la phrase dit (said, lu par le serveur pour cette phrase-là), complété par ce qui a été choisi dans l'app, qui
  // l'emporte (même règle que catalog.search). Quand on touche une puce, la phrase devient des critères de l'app et le
  // champ ne garde que les mots qui restent : rien n'est compris deux fois. Chaque geste part du dernier état voulu, sans
  // attendre la réponse du précédent.
  const phraseSaid = results && results._q === q.trim() && q.trim() ? results.said : null;
  const merged = (s, c) => !s ? c : { category: c.category || (c.domain ? null : s.category) || null,
    room: c.room || s.room || null,                                       // v60 : la pièce reste, au-dessus du rayon (l'entonnoir)
    brand: c.brand || s.brand || null, features: [...new Set([...c.features, ...(s.features || [])])], attrs: { ...(s.attrs || {}), ...c.attrs },
    min: c.min ?? s.min_price ?? null, max: c.max ?? s.max_price ?? null, off: c.off || s.off || null, low: c.low || !!s.low,
    sort: c.sort || (s.sort && s.sort !== "relevance" ? s.sort : null),
    domain: c.category ? null : c.domain || s.domain || null, sub: c.category ? null : c.sub || s.sub || null,
    props: c.category ? {} : { ...(s.props || {}), ...c.props } };
  const applied = () => merged(phraseSaid, crit);
  const edit = (fn, words) => {
    const s = phraseSaid;
    setCrit(c => fn(merged(s, c)));
    if (s || words) setQ((words || results?.words || []).join(" "));
  };
  const dropChip = id => edit(c => {
    if (id === "category" || id === "room" || id === "domain") return { ...c, category: null, room: null, features: [], attrs: {}, domain: null, sub: null, props: {} };
    if (id === "sub") return { ...c, sub: null };
    if (id.startsWith("prop:")) { const props = { ...c.props }; delete props[id.slice(5)]; return { ...c, props }; }
    if (id === "brand") return { ...c, brand: null };
    if (id.startsWith("feature:")) return { ...c, features: c.features.filter(f => f !== id.slice(8)) };
    if (id.startsWith("attr:")) { const attrs = { ...c.attrs }; delete attrs[id.slice(5)]; return { ...c, attrs }; }
    if (id === "price") return { ...c, min: null, max: null };
    if (id === "off") return { ...c, off: null };
    if (id === "low") return { ...c, low: false };
    if (id === "sort") return { ...c, sort: null };
    return c;
  }, id.startsWith("word:") ? (results?.words || []).filter(w => w !== id.slice(5)) : undefined);
  const clearAll = () => { setCrit(NO_CRIT); setQ(""); setSkip([]); };

  // Vos recherches sauvegardées (des missions : Promo Central les surveille ; le prix est facultatif).
  const sig = m => JSON.stringify([m.category || null, m.room || null, m.brand || null, [...(m.features || [])].sort(),
    Object.entries(m.attrs || {}).sort(), m.min_price ?? null, m.max_price ?? null, m.off || null, !!m.low, [...(m.words || [])],
    m.domain || null, m.sub || null, Object.entries(m.props || {}).sort()]);
  // Ce qu'une réponse de la Recherche ou d'une page demande, mots compris : la recherche que « Sauvegarder » garde.
  const wantOf = res => res?.criteria ? { ...res.criteria, words: res.words || [] } : null;
  const searches = (missions?.missions || []).filter(m => !m.product_id);
  const savedOf = res => { const c = wantOf(res); return c ? searches.find(m => sig(m) === sig(c)) : null; };
  const saveSearch = async res => {
    const hit = savedOf(res), c = wantOf(res);
    if (hit) { await dropSaved(hit); return; }
    if (!c) return;
    try {
      const made = await keep("missions", { category: c.category, room: c.room, brand: c.brand, features: c.features, attrs: c.attrs,
        min_price: c.min_price, max_price: c.max_price, off: c.off, low: c.low, words: c.words,
        domain: c.domain, sub: c.sub, props: c.props });
      setMissions(x => ({ reached: 0, fresh: 0, ...x, missions: [made, ...(x?.missions || []).filter(m => m.id !== made.id)] }));   // « Sauvegardée » aussitôt
      if (res === results) remember(intent);
      setVersion(v => v + 1);
      flash(c.max_price != null ? "Sauvegardée : on vous prévient sous votre prix" : "Recherche sauvegardée dans votre Profil");
    } catch (ex) { flash(ex.message); }
  };
  const saveBtn = (label, res, cls = "") => {
    const on = !!savedOf(res);
    return <button className={`savebtn ${on ? "on" : ""} ${cls}`} aria-pressed={on} onClick={() => saveSearch(res)}>
      <Icon d={UI.bookmark} size={17} sw={2.2} fill={on} />{on ? "Sauvegardée" : label}</button>;
  };
  const dropSaved = async m => {
    setMissions(x => x && { ...x, missions: x.missions.filter(y => y.id !== m.id) });
    try { await api("missions/delete", { id: m.id }); flash(m.product_id ? "Alerte arrêtée" : "Recherche retirée"); } catch { /* relue ensuite */ }
    setVersion(v => v + 1);
  };
  const openSaved = m => {
    if (m.product_id) open(m.product_id, "mission", m.id);
    else {
      setView(null); setItem(null); setTab("search"); setQ((m.words || []).join(" ")); setSkip([]);
      setCrit({ category: m.category || null, room: m.room || null, brand: m.brand || null, features: m.features || [], attrs: m.attrs || {},
        min: m.min_price ?? null, max: m.max_price ?? null, off: m.off || null, low: !!m.low, sort: null,
        domain: m.domain || null, sub: m.sub || null, props: m.props || {} });
    }
    if (m.fresh) api("missions/seen", { id: m.id }).then(() => setVersion(v => v + 1)).catch(() => {});
  };
  const toggleAlert = async m => {
    if (!session.email) { setEmailFor("Recevoir vos alertes par e-mail"); return; }
    try { await api("missions/alert", { id: m.id, on: !m.alert }); setVersion(v => v + 1); flash(m.alert ? "Plus d'e-mail pour cette recherche" : "Un e-mail la nuit où il y a du nouveau"); }
    catch (ex) { flash(ex.message); }
  };
  const launchAlert = async spec => {                                      // « Me prévenir sous un prix », depuis la fiche
    try { await keep("missions", spec); flash("Alerte posée : on vous prévient"); setVersion(v => v + 1); return true; }
    catch (ex) { flash(ex.message); return false; }
  };
  const dropOf = p => p.saved_price ? Math.round(p.saved_price - p.price) : 0;
  const drops = (savedList || []).filter(p => dropOf(p) >= 1).length;
  const said = p => `${p.brand}, ${p.name || p.title}, ${p.pct > 0 ? `moins ${p.pct} %, ` : ""}${eur(p.price)}`;

  const card = (via, mission) => p => <article key={p.id} className="card" role="button" tabIndex={0} aria-label={said(p)}
    onClick={() => open(p.id, via, mission)} onKeyDown={e => { if (e.key === "Enter") open(p.id, via, mission); }}>
    <div className="vis" style={{ aspectRatio: `1 / ${ratioOf(p.category)}` }}>
      <Vignette category={p.category} seed={p.id} />
      {p.saving >= 1 ? <span className="badge good">{eur(p.saving)} de moins</span> : p.pct > 0 ? <span className="badge">−{p.pct} %</span>
        : p.why?.low && <span className="badge good">Prix bas</span>}
      <button className={`heart ${isSaved(p.id) ? "on" : ""}`} aria-pressed={isSaved(p.id)}
        aria-label={isSaved(p.id) ? "Retirer des favoris" : "Ajouter aux favoris"} onClick={e => toggleSave(p.id, e)}>
        <span><Icon d={UI.heart} size={18} fill={isSaved(p.id)} /></span></button>
    </div>
    <div className="meta">
      <div className="brand">{p.brand}</div>
      <div className="name">{p.name || p.title}</div>
      <div className="price"><b className={p.pct > 0 ? "deal" : ""}>{eur(p.price)}</b>{p.pct > 0 && p.was && <s>{eur(p.was)}</s>}</div>
      {dropOf(p) >= 1 && <div className="drop">Baisse de {eur(dropOf(p))}</div>}
      {p.why?.low && <div className="why"><Icon d={UI.check} size={13} sw={3} />{p.why.low === "lowest" ? "Au plus bas" : "Parmi les plus bas"}</div>}
    </div>
  </article>;
  const grid = (items, via) => <Masonry items={items} cols={cols} render={card(via)} />;

  const searchBar = <form role="search" onSubmit={e => { e.preventDefault(); remember(intent); e.currentTarget.querySelector("input")?.blur(); }}>
    <label className="sbar big"><Icon d={UI.search} size={20} />
    <input value={q} onChange={e => { setQ(e.target.value); setSkip([]); }} placeholder="« aspirateur balai sous 300 € », une marque…" aria-label="Rechercher" enterKeyHint="search" />
    {q && <button type="button" className="sx" aria-label="Effacer le texte" onClick={() => { setQ(""); setSkip([]); }}><Icon d={UI.x} size={18} /></button>}</label></form>;
  const back = <button className="back" onClick={goBack}><Icon d={UI.back} size={18} sw={2.2} />Retour</button>;
  const tabsList = [["tops", "Top deals", UI.flame], ["home", "Explorer", UI.compass], ["search", "Recherche", UI.search],
    ["me", "Profil", UI.user]];                                                      // vos recherches et missions sont dans le Profil
  const fresh = missions?.fresh || 0;
  const badge = { me: fresh + drops };
  const freshSaid = fresh > 1 ? `${fresh} recherches avec du nouveau` : fresh === 1 ? "1 recherche avec du nouveau" : "";
  const tabSaid = (k, l) => k === "me" && badge.me ? `${l}, ${[freshSaid, drops ? `${plural(drops, "baisse")} de prix sur vos favoris` : ""].filter(Boolean).join(", ")}` : undefined;
  const nearRow = (p, label, mission) => <button className="near" onClick={() => open(p.id, "mission", mission)} aria-label={`${label} : ${said(p)}`}>
    <span className="th"><Vignette category={p.category} seed={p.id} ratio={1} /></span>
    <span className="tx"><small>{label}</small><span>{p.brand} {p.name || p.title}</span></span><b>{eur(p.price)}</b>
    <Icon d={UI.next} size={16} sw={2.2} /></button>;
  const searchItem = m => {
    const hit = m.matches?.[0], target = m.max_price != null;
    const state = m.product_id ? (m.reached ? `ATTEINTE · ${eur(hit.price)}` : "EN VEILLE")
      : target ? (m.reached ? `ATTEINTE · ${plural(m.total, "produit").toUpperCase()}` : "EN VEILLE") : plural(m.total, "produit").toUpperCase();
    return <article key={m.id} className={`mi ${m.reached ? "ok" : ""}`}>
      <div className="row"><button className="mopen" onClick={() => openSaved(m)} aria-label={`Ouvrir ${m.title}`}>
        <span className="st"><i />{state}{m.fresh > 0 && <em className="new">{m.fresh > 1 ? `${m.fresh} NOUVEAUX` : "1 NOUVEAU"}</em>}</span>
        <h3>{m.title}</h3>
        <span className="nums">{target && <span>Objectif <b>{eur(m.max_price)}</b></span>}
          {!m.reached && m.nearest && <span>Le plus proche <b>{eur(m.nearest.price)}</b></span>}
          {m.reached && hit && <span>Dès <b className="ok">{eur(hit.price)}</b></span>}</span></button>
        <span className="macts">
          <button className={`ibtn ${m.alert && session.email ? "on" : ""}`} aria-pressed={!!(m.alert && session.email)} onClick={() => toggleAlert(m)}
            aria-label={m.alert && session.email ? `Plus d'e-mail pour ${m.title}` : `Recevoir un e-mail pour ${m.title}`}><Icon d={UI.bell} size={18} /></button>
          <button className="ibtn" aria-label={`Retirer ${m.title}`} onClick={() => dropSaved(m)}><Icon d={UI.x} size={18} /></button></span></div>
      {m.reached && hit && target && <a className="mbuy" href={`/api/r/out/${hit.offer_id}?from=mission&m=${m.id}&v=${variant}`} target="_blank" rel="noopener"
        aria-label={`Voir l'offre : ${said(hit)}, chez ${hit.merchant}`}>
        <span>Voir l'offre · <b>{eur(hit.price)}</b> chez {hit.merchant}</span><Icon d={UI.ext} size={18} sw={2.2} /></a>}
      {!m.reached && m.product_id && m.nearest && nearRow(m.nearest, "Voir la fiche", m.id)}
    </article>;
  };
  const categories = allCats.filter(c => c.count > 0);                    // celles qui ont des remises aujourd'hui
  const promoBrands = allBrands.filter(b => b.count > 0 && b.top).slice(0, 12);
  // Des cartes au format des pièces : un visuel (le produit de la meilleure remise), la marque, « Jusqu'à −20 % ».
  const bigCard = (key, label, best, sub, art, seed, onClick, cls = "") => <button key={key} className={`room ${cls}`} onClick={onClick}
    aria-label={`${label}, jusqu'à moins ${best} %, ${sub}`}>
    <Vignette category={art} seed={seed} ratio={1.32} floor={0.7} zoom={ratioOf(art) > 1 ? 0.9 : 1.04} /><span className="shade" />
    <span className="rt"><b>{label}</b><span>Jusqu'à −{best} %</span><small>{sub}</small></span></button>;
  const sortBar = <div className="chips" role="group" aria-label="Trier">{[["pct", "Remises d'abord"], ["asc", "Prix croissant"], ["desc", "Prix décroissant"]].map(([k, l]) =>
    <button key={k} className={order === k ? "on" : ""} aria-pressed={order === k} onClick={() => setOrder(k)}>{l}</button>)}</div>;
  const liked = new Set((you?.taste?.cats || []).map(c => c.key));        // vos rayons : leurs pièces d'abord
  const rooms = ROOMS.map(r => {
    const here = categories.filter(c => r.cats.includes(c.key));
    return here.length ? { ...r, best: Math.max(...here.map(c => c.best)), sub: here.map(c => c.label).join(", "),
      art: here.some(c => c.key === r.art) ? r.art : here[0].key, mine: here.some(c => liked.has(c.key)) } : null;
  }).filter(Boolean).sort((a, b) => b.mine - a.mine);
  // Vos rayons à choisir : ceux qui ont des produits, les plus riches en remises d'abord.
  const pickable = allCats.filter(c => c.products > 0).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "fr"));
  const pickChips = cls => pickable.map(c => <button key={c.key} className={`${cls} ${picks.includes(c.key) ? "on" : ""}`}
    aria-pressed={picks.includes(c.key)} onClick={() => togglePick(c.key)}>{picks.includes(c.key) && <Icon d={UI.check} size={15} sw={2.8} />}{c.label}</button>);

  let body;
  if (view?.kind === "legal") {                    // qui édite, qui héberge, quelles données et quels droits (LCEN, RGPD)
    const L = legal || {}, v = (x, name) => x || <em className="todo">à compléter ({name})</em>;
    body = <div className="about">
      {back}
      <h1>Mentions légales</h1>
      <h2>Éditeur</h2>
      <p>{v(L.editor, "DEALS_LEGAL_EDITOR")}<br />{v(L.registration, "DEALS_LEGAL_REGISTRATION")}<br />{v(L.address, "DEALS_LEGAL_ADDRESS")}</p>
      <h2>Directeur de la publication</h2>
      <p>{v(L.director, "DEALS_LEGAL_DIRECTOR")}</p>
      <h2>Hébergeur</h2>
      <p>{v(L.host, "DEALS_LEGAL_HOST")}</p>
      <h2>Contact</h2>
      <p>{v(L.contact, "DEALS_LEGAL_CONTACT")}</p>
      <h2>Données personnelles</h2>
      <p>Responsable du traitement : {v(L.editor, "DEALS_LEGAL_EDITOR")}.</p>
      <ul>
        <li><b>Sans compte</b> : vos recherches récentes et les fiches ouvertes pendant la visite restent dans votre
          navigateur ; il les joint à chaque lecture pour ordonner ce qui vous est montré, nos serveurs n'en gardent rien.</li>
        <li><b>Ce que vous gardez</b> (favoris, marques, rayons, recherches, alertes) : un compte sans e-mail, propre à
          cet appareil, le garde pour vous rendre ce service ; il tient à un cookie de session, valable un an après le dernier
          choix gardé, et un compte que plus personne ne peut ouvrir est effacé.</li>
        <li><b>Votre e-mail</b>, facultatif : il sert à vous envoyer vos alertes et vos liens de connexion, et à
          retrouver vos choix sur un autre appareil. Il n'est transmis qu'à notre prestataire d'envoi.</li>
        <li><b>Mesures</b> : les fiches vues et les clics vers les enseignes sont comptés pour savoir ce qui est utile ;
          une enseigne ne reçoit qu'un identifiant de clic, qui ne dit pas qui vous êtes.</li>
        <li><b>Cookies</b> : un seul cookie, celui de votre session, nécessaire au service ; aucun traceur publicitaire,
          aucune mesure d'audience par un tiers.</li>
        <li><b>Vos droits</b> : accès, rectification, effacement, opposition, portabilité. « Effacer mes
          données », dans Profil, efface tout aussitôt ; pour le reste, écrivez à {v(L.contact, "DEALS_LEGAL_CONTACT")}.
          Vous pouvez aussi saisir la CNIL (cnil.fr).</li>
      </ul>
    </div>;
  } else if (view?.kind === "about") {             // référencement, classement, rémunération : ce que la loi demande de dire
    body = <div className="about">
      {back}
      <h1>Comment ça marche</h1>
      <p className="lead">Promo Central repère chaque jour les bonnes affaires d'électroménager, d'électronique, d'ameublement et de literie : des
        remises réelles, et les prix au plus bas depuis longtemps.</p>
      <h2>Quelles offres ?</h2>
      <p>Uniquement celles de nos enseignes partenaires. Leurs prix sont relus chaque nuit ; un prix qui n'a pas été relu depuis
        trois jours n'est plus montré. Une remise n'est affichée que si elle est réelle : nous la comparons aux prix des mois
        précédents et au « prix le plus bas des 30 derniers jours » que l'enseigne doit indiquer ; une remise exagérée n'est
        pas affichée.</p>
      <h2>Dans quel ordre ?</h2>
      <ul>
        <li><b>Top deals</b> : les plus fortes remises réelles et les produits dont le prix est parmi les plus bas depuis
          au moins deux mois (au moins 10 % sous leur prix habituel), à tour de rôle. <b>Explorer</b> : <b>Pour vous</b>, les
          remises et les prix bas de vos rayons et de vos marques ; <b>Notre sélection</b>, les autres remises, les plus fortes
          d'abord.</li>
        <li><b>Vos goûts</b> : vos rayons (choisis, ou ceux des fiches que vous ouvrez), vos marques suivies, vos favoris et vos
          recherches sauvegardées font passer un deal devant, au plus une fois et demie : l'intérêt du deal reste premier, et un emplacement
          sur quatre revient au meilleur deal du moment, quels que soient vos goûts. Une visite sur dix (un compte sur dix,
          toujours le même) montre l'ordre sans vos goûts : c'est ainsi que nous mesurons ce qu'ils apportent.</li>
        <li><b>Recherche</b> : votre phrase est comprise (« aspirateur balai sans fil sous 300 € » : le rayon, les fonctions, le
          budget), chaque critère se modifie ; d'abord les produits que vos mots nomment, puis les remises, puis le prix ; ou le
          tri que vous choisissez. Rien sous votre budget : les plus proches au-dessus. Avant toute recherche : vos recherches
          récentes, puis vos rayons, puis une catégorie à tour de rôle.</li>
        <li><b>Chaque rayon</b> : le type (OLED ou QLED, balai ou robot, d'angle…) et un ou deux attributs (sans fil, 5G, No Frost ;
          une taille d'écran, une capacité) se lisent dans ce que l'enseigne donne de son offre, son titre et sa catégorie ; ce
          qu'elle ne dit pas reste inconnu, jamais deviné (un robot aspirateur, lui, est toujours sans fil). Affiner les
          demande, une question à la fois, chaque réponse avec son nombre de produits.</li>
        <li><b>Moins cher, comparable</b> : sur la fiche, des produits du même type, de la même taille (un téléviseur 55 pouces,
          un autre 55 pouces), qui ont au moins ce que le produit a (4K, 5G, réduction de bruit, autant de stockage) et coûtent au
          moins 10 % de moins.</li>
        <li><b>Marque, catégorie, pièce</b> : les remises d'abord, ou le tri que vous choisissez ; Affiner y est aussi.</li>
        <li><b>Fiche</b> : l'offre la moins chère parmi nos partenaires.</li>
      </ul>
      <h2>Comment Promo Central est rémunéré ?</h2>
      <p>Quand vous achetez après avoir touché « Voir l'offre », l'enseigne nous verse une commission. Votre prix ne change pas,
        et le montant de la commission n'entre dans aucun classement.</p>
      <h2>Vos données</h2>
      <p>Sans compte, vos recherches récentes restent dans votre navigateur, qui les joint à chaque lecture avec les fiches
        ouvertes pendant la visite, pour ordonner ce qui vous est montré ; nos serveurs n'en gardent rien. Dès que vous gardez
        quelque chose (un favori, une marque, un rayon, une recherche), un compte sans e-mail est créé pour cet appareil : il
        garde ces choix, et, si vous le demandez dans Profil, les fiches que vous ouvrez. Il tient à un cookie valable un an
        après le dernier choix gardé ; sans e-mail, effacer les données du navigateur le perd, et un compte que plus personne
        ne peut ouvrir est effacé. Votre e-mail est facultatif : il sert à recevoir vos alertes et à retrouver vos choix sur un
        autre appareil. Profil montre ce que l'app a compris ;
        « Oublier » l'efface, « Effacer mes données » efface tout.</p>
    </div>;
  } else if (view?.kind === "item" && item) {
    const best = item.offers.find(o => o.best);
    const mine = (missions?.missions || []).find(m => m.product_id === item.id);
    const when = timing(item);
    const source = view.via || "item";
    body = <div className="item">
      <div className="hero">
        <div className="vis" style={{ aspectRatio: `1 / ${Math.min(1.05, ratioOf(item.category))}` }}><Vignette category={item.category} seed={item.id} label={item.kind} /></div>
        <div className="float"><button className="fbtn" onClick={goBack} aria-label="Retour"><Icon d={UI.back} size={20} sw={2.2} /></button>
          <div><button className="fbtn" onClick={() => share(item)} aria-label="Partager"><Icon d={UI.share} size={19} /></button>
            <button className={`fbtn ${isSaved(item.id) ? "on" : ""}`} onClick={() => toggleSave(item.id)} aria-pressed={isSaved(item.id)}
              aria-label={isSaved(item.id) ? "Retirer des favoris" : "Ajouter aux favoris"}><Icon d={UI.heart} size={20} fill={isSaved(item.id)} /></button></div></div>
        <div className="crumbs">
          {item.brand && <button onClick={() => openBrand(item.brand)} aria-label={`Voir tous les produits ${item.brand}`}>{item.brand}<Icon d={UI.next} size={14} sw={2.6} /></button>}
          <button onClick={() => openCategory(item.category)} aria-label={`Voir la catégorie ${item.kind}`}>{item.kind}<Icon d={UI.next} size={14} sw={2.6} /></button>
        </div>
      </div>
      <div>
        <div className="info">
          <h1 className="title">{item.name || item.title}</h1>
          <div className="prices">{item.pct > 0 && <span className="pct">−{item.pct} %</span>}<span className="now">{eur(item.price)}</span>
            {item.pct > 0 && item.was && <s>{eur(item.was)}</s>}</div>
          {when && <div className="when"><Icon d={UI.cal} size={20} />{when}</div>}
          {best && <a className="buy" href={`/api/r/out/${best.offer_id}?from=${source}${view.mission ? `&m=${view.mission}` : ""}&v=${variant}`}
            target="_blank" rel="noopener" onClick={() => note("c", item.id)}>
            Voir l'offre chez {best.merchant}<Icon d={UI.ext} size={18} sw={2.2} /></a>}
          {best && <p className="aff">Enseigne partenaire : si vous achetez, nous touchons une commission, sans surcoût pour vous.{" "}
            <button className="lnk" onClick={openAbout}>Comment ça marche</button></p>}
          <button className={`alertbtn ${mine ? "on" : ""}`} onClick={() => setAlertOpen(true)}>
            <Icon d={mine ? UI.check : UI.bell} size={19} sw={2.1} />{mine ? `Alerte à ${eur(mine.max_price)}` : "Me prévenir sous un prix"}</button>
        </div>
        {item.alternatives.length > 0 && <>
          <div className="sechead"><h2>Moins cher, comparable</h2></div>
          <div className="scroller">{item.alternatives.map(card("alternative"))}</div>
        </>}
        {item.alternatives.length === 0 && item.similar.length > 0 && <>
          <div className="sechead"><h2>Produits similaires</h2></div>
          <div className="scroller">{item.similar.map(card("similar"))}</div>
        </>}
      </div>
      {alertOpen && <AlertSheet item={item} current={mine} onClose={() => setAlertOpen(false)} onLaunch={launchAlert} onStop={dropSaved} />}
    </div>;
  } else if (isPage(view)) {                     // une marque, une catégorie, une pièce : l'entonnoir, un tri, leurs produits
    const res = pres?._k === pageKey(view) ? pres : null, stale = !!res && res._p !== pageParams;
    const at = funnelAt(res?.funnel, pskip, view.kind === "category" ? ["category"] : view.kind === "room" ? ["room"] : []);
    const fin = !!(at && !at.q && at.done > 0 && res?.total > 0);
    const entry = view.kind === "brand" ? allBrands.find(x => x.name === view.name) : view.kind === "category" ? allCats.find(x => x.key === view.key) : null;
    const title = view.kind === "brand" ? view.name : view.kind === "room" ? view.room.label : entry?.label || "…";
    const sub = view.kind === "room" ? `${plural(allCats.filter(x => view.room.cats.includes(x.key)).reduce((n, x) => n + x.count, 0), "remise")} · ${view.room.sub}`
      : entry ? `${entry.count ? `${plural(entry.count, "remise")} aujourd'hui · ` : ""}${plural(entry.products, "produit")}` : "";
    const on = view.kind === "brand" ? isFollowed(view.name) : picks.includes(view.key);
    body = <>
      {back}
      <div className="pagehead"><div><h1>{title}</h1>{sub && <div className="sub">{sub}</div>}</div>
        {view.kind === "brand" && <button className={`pill ${on ? "on" : ""}`} onClick={() => toggleFollow(view.name)} aria-pressed={on}>
          <Icon d={on ? UI.check : UI.plus} size={17} sw={2.4} />{on ? "Suivie" : "Suivre"}</button>}
        {view.kind === "category" && <button className={`pill ${on ? "on" : ""}`} onClick={() => togglePick(view.key)} aria-pressed={on}>
          <Icon d={on ? UI.check : UI.plus} size={17} sw={2.4} />{on ? "Dans vos rayons" : "Mes rayons"}</button>}</div>
      <Funnel at={at} total={res?.total ?? 0} onAnswer={set => setPc(x => applyPatch(x, set))}
        onBack={s => { setPc(x => applyPatch(x, s.back)); if (s.level === "room" || s.level === "category") setPskip([]); }}
        onSkip={key => setPskip(x => [...x, key])} onRestart={() => { setPc(NO_CRIT); setPskip([]); }} keep={res ? saveBtn("Sauvegarder", res) : null} />
      {sortBar}
      {res && res.total > 0 && (fin ? <div style={{ height: 16 }} />
        : <div className="sechead"><h2>{plural(res.total, view.kind === "room" ? "remise" : "produit")}</h2></div>)}
      {res && <div className={`flow ${stale ? "dim" : ""}`}>{grid(res.products, view.kind)}</div>}
      {res && res.total === 0 && <div className="empty">{view.kind === "room" ? "Aucune remise dans cette pièce aujourd'hui." : "Aucun produit pour l'instant."}</div>}
    </>;
  } else if (tab === "tops") {                    // Top deals : les plus fortes remises réelles et les prix bas, à tour de rôle
    const tops = top?.products || [];
    body = <>
      <div className="pagehead"><div><h1>Top deals</h1><div className="sub">Remises et prix bas</div></div></div>
      <div style={{ height: 16 }} />
      {top && tops.length === 0 && <div className="empty">Aucun top deal aujourd'hui.</div>}
      {grid(tops, "top")}
    </>;
  } else if (tab === "home") {                    // Explorer : des pièces, des marques, une sélection ; chercher, c'est l'onglet Recherche
    const items = all?.products || [];
    // Pour vous : tous vos deals, top deals compris : ils ne sont plus sur cet écran, et ils suivent vos goûts eux aussi
    // (les en retirer vidait la section). Notre sélection : les autres remises, ni top deals ni « pour vous ».
    const inTop = new Set((top?.products || []).map(p => p.id));
    const yours = you?.products || [];
    const shown = new Set([...inTop, ...yours.map(p => p.id)]);
    const rest = items.filter(p => !shown.has(p.id));
    body = <>
      <Ticker items={items} publishedAt={all?.published_at} />
      <div className="intro"><h1>De bonnes affaires, pour vos envies.</h1></div>
      {yours.length > 0 && <>
        <div className="sechead"><div><h2>Pour vous</h2><span className="n">{tasteLine(you?.taste, picks)}</span></div>
          <button className="forget" onClick={() => goTab("me")} aria-label="Modifier vos goûts, dans Profil">Modifier</button></div>
        <div className="scroller tops">{yours.map(card("foryou"))}</div>
      </>}
      {rooms.length > 0 && <>
        <div className="sechead"><h2>Inspirations du moment</h2></div>
        <div className="rooms">{rooms.map(r => bigCard(r.key, r.label, r.best, r.sub, r.art, r.key, () => openRoom(r)))}</div>
      </>}
      {promoBrands.length > 0 && <>
        <div className="sechead"><h2>Les marques en promo</h2></div>
        <div className="rooms">{promoBrands.map(b => bigCard(b.name, b.name, b.best, b.categories.join(", "), b.top.category, b.top.id,
          () => openBrand(b.name), "bcard"))}</div>
      </>}
      <div className="sechead"><h2>Notre sélection</h2></div>
      {all && items.length === 0 && <div className="empty">Aucune remise aujourd'hui.</div>}
      {grid(rest.slice(0, cols * 2), "home")}
      {rest.length > cols * 2 && <div style={{ height: 18 }} />}
      {grid(rest.slice(cols * 2), "home")}
    </>;
  } else if (tab === "search") {                  // une phrase comprise, l'entonnoir, un feed que chaque saisie adapte
    const term = q.trim(), t = norm(term), any = term || hasCrit(crit);
    const shownRes = any ? results : null;
    const src = any ? shownRes : feed;                                       // l'entonnoir de la réponse, ou du feed (l'univers)
    const at = funnelAt(src?.funnel, skip);
    const covered = new Set((at?.path || []).flatMap(s => s.chips));
    const chips = (shownRes?.chips || []).filter(c => !covered.has(c.id));   // ce que l'entonnoir ne montre pas : marque, promo, tri, mots
    const fin = !!(at && !at.q && at.done > 0 && shownRes?.total > 0 && !shownRes.relaxed);   // votre sélection : l'entonnoir la dit
    const brandHit = t.length >= 2 && !hasCrit(crit) ? allBrands.find(b => norm(b.name) === t) || allBrands.find(b => norm(b.name).startsWith(t)) : null;
    const offs = (shownRes || feed)?.offs || {};
    const base = applied();
    const sheets = {
      off: ["Promo", OFFS.filter(([k]) => !k || offs[k] > 0).map(([k, l]) => k ? [k, l, offs[k] ?? 0] : [k, l]), base.low ? "low" : String(base.off || ""),
        v => edit(c => ({ ...c, off: v && v !== "low" ? Number(v) : null, low: v === "low" }))],
      sort: ["Trier", SORTS, base.sort || "relevance", v => edit(c => ({ ...c, sort: v === "relevance" ? null : v }))],
    };
    const sheetOf = id => id === "off" || id === "low" ? "off" : id === "sort" ? "sort" : null;
    const quick = (key, name) => <button key={key} className="fchip" onClick={() => setPicking(key)} aria-haspopup="dialog">{name}<Icon d={UI.down} size={15} sw={2.4} /></button>;
    const mine = feed?.recent?.length > 0 || feed?.personal;   // le feed suit vos dernières recherches, vos goûts
    const feedHead = <div className="sechead"><h2>{mine ? "Pour vous" : "À découvrir"}</h2>
      <span className="n">{feed?.recent?.length > 0 ? "D'après vos recherches" : mine ? "D'après vos goûts" : feed ? plural(feed.total, "produit") : ""}</span></div>;
    const every = shownRes?.chips || [];
    body = <>
      <div className="pagehead"><h1>Recherche</h1></div>
      {searchBar}
      <div className="filters" role="group" aria-label="Critères de la recherche">
        {chips.map(c => <span key={c.id} className="crit">
          {sheetOf(c.id) ? <button className="cl" onClick={() => setPicking(sheetOf(c.id))} aria-label={`${c.label} : modifier`}>{c.label}</button>
            : <span className="cl">{c.label}</span>}
          <button className="cx" onClick={() => dropChip(c.id)} aria-label={`Retirer ${c.label}`}><Icon d={UI.x} size={14} sw={2.6} /></button></span>)}
        {!chips.some(c => c.id === "off" || c.id === "low") && quick("off", "Promo")}
        {!chips.some(c => c.id === "sort") && quick("sort", "Trier")}
        {(chips.length > 0 || (at?.done || 0) > 0) && <button className="fchip clear" onClick={clearAll}><Icon d={UI.x} size={15} sw={2.4} />Tout effacer</button>}
      </div>
      <Funnel at={at} total={shownRes?.relaxed ? 0 : src?.total ?? 0} onAnswer={set => edit(c => applyPatch(c, set))}
        onBack={s => { edit(c => applyPatch(c, s.back)); if (s.level === "room" || s.level === "category") setSkip([]); }}
        onSkip={k => setSkip(x => [...x, k])} keep={shownRes ? saveBtn("Sauvegarder", shownRes) : null} />
      {!any && <div className="tryit">
        {recent.length > 0
          ? <><div className="th"><h3>Vos recherches récentes</h3><button className="forget" onClick={forget} aria-label="Effacer vos recherches">Effacer</button></div>
            <div className="ctags row">{recent.map(x => <button key={x} className="ctag" onClick={() => { setQ(x); setSkip([]); remember(x); }}>{x}</button>)}</div></>
          : <><h3>Essayez</h3>
            <div className="ctags row">{TRY.map(x => <button key={x} className="ctag" onClick={() => { setQ(x); setSkip([]); remember(x); }}>{x}</button>)}</div></>}
      </div>}
      {!any || !shownRes ? <>{feedHead}<div className={`flow ${any ? "dim" : ""}`}>{grid(feed?.products || [], "feed")}</div></>
        : shownRes.unsupported ? <>
          <div className="sechead"><h2>Les {shownRes.unsupported.toLowerCase()} ne sont pas encore suivis</h2></div>
          <p className="note">Électroménager, électronique, ameublement et literie seulement, pour l'instant.</p>
          {feedHead}{grid(feed?.products || [], "feed")}
        </> : shownRes.total === 0 ? <>{/* rien trouvé : on le dit, on propose de sauvegarder, et le feed reste là */}
          <div className="sechead"><h2>{term && every.every(c => c.id.startsWith("word:")) ? `Rien pour « ${term} »` : "Rien pour cette recherche"}</h2></div>
          {every.length > 0 && <div className="savebar"><span>Pas encore là ? On surveille pour vous.</span>{saveBtn("Sauvegarder", shownRes)}</div>}
          {feedHead}{grid(feed?.products || [], "feed")}
        </> : <>
        {brandHit && <button className="brow" onClick={() => openBrand(brandHit.name)} aria-label={`La marque ${brandHit.name}`}>
          <small>Marque</small><b>{brandHit.name}</b><span>{plural(brandHit.products, "produit")}</span><Icon d={UI.next} size={18} sw={2.2} /></button>}
        {shownRes.relaxed ? <>
          <div className="sechead"><div><h2>Rien à moins de {eur(shownRes.relaxed.max_price)}</h2>
            <span className="n">Les plus proches, dès {eur(shownRes.relaxed.from)}</span></div></div>
          <div className="savebar"><span>On vous prévient dès qu'un produit passe sous {eur(shownRes.relaxed.max_price)}.</span>{saveBtn("Me prévenir", shownRes)}</div>
        </> : fin ? <div style={{ height: 18 }} /> : <div className="sechead"><h2>{plural(shownRes.total, "produit")}</h2>{saveBtn("Sauvegarder", shownRes)}</div>}
        {shownRes.ignored?.length > 0 && <p className="note">« {shownRes.ignored.join(" ")} » : aucun produit ; voici le reste de votre recherche.</p>}
        <div className={`flow ${searching ? "dim" : ""}`}>{grid(shownRes.products, "search")}</div>
      </>}
      {picking && sheets[picking] && <ChoiceSheet title={sheets[picking][0]} options={sheets[picking][1]} value={sheets[picking][2]} onPick={sheets[picking][3]}
        onClose={() => setPicking(null)} />}
    </>;
  } else {                                        // Profil : le centre de commande — vos recherches, favoris, marques, rayons, ce qui est compris
    const understood = [...(taste?.taste?.cats || []).filter(c => !c.chosen).map(c => ({ key: c.key, label: c.label, go: () => openCategory(c.key) })),
      ...(taste?.taste?.brands || []).filter(b => !b.chosen).map(b => ({ key: b.name, label: b.name, go: () => openBrand(b.name) }))];
    const learning = !!taste?.learn;
    const alerts = (missions?.missions || []).filter(m => m.product_id);
    // Des titres seuls, beaucoup d'air entre les sections ; une section vide le dit d'un mot, sur la ligne du titre.
    body = <div className="center profile">
      <div className="pagehead"><div><h1>Profil</h1></div></div>
      {session.checked && <div className="idline">{session.email
        ? <><span>Connecté avec <b>{session.email}</b></span></>
        : <><span>{known ? "Gardé sur cet appareil, sans e-mail." : "Rien n'est gardé pour l'instant."}</span>
          <button className="lnk" onClick={() => setEmailFor(known ? "Ajouter votre e-mail" : "Retrouver votre compte")}>
            {known ? "Ajouter mon e-mail" : "J'ai déjà un compte"}</button></>}</div>}
      <section className="psec" id="vos-recherches">
        <div className="sechead"><h2>Vos recherches</h2>{searches.length === 0 && <span className="n">Aucune</span>}</div>
        {searches.length > 0 && <div className="mlist">{searches.map(searchItem)}</div>}
      </section>
      {alerts.length > 0 && <section className="psec">
        <div className="sechead"><h2>Vos alertes de prix</h2></div>
        <div className="mlist">{alerts.map(searchItem)}</div>
      </section>}
      <section className="psec">
        <div className="sechead"><h2>Vos favoris</h2>{drops > 0 ? <span className="n drop">{plural(drops, "baisse")} de prix</span>
          : !savedList?.length && <span className="n">Aucun</span>}</div>
        {savedList?.length > 0 && grid(savedList, "saved")}
      </section>
      <section className="psec">
        <div className="sechead"><h2>Vos marques</h2><button className="forget" onClick={() => setPicking("brands")}>Ajouter</button></div>
        {followed.size > 0 && <div className="bchips">{[...followed].map(b => <button key={b} onClick={() => openBrand(b)}>{b}</button>)}</div>}
      </section>
      <section className="psec">
        <h2 className="fold"><button aria-expanded={raysOpen} aria-controls="vos-rayons" onClick={() => setRaysOpen(o => !o)}>
          <span>Vos rayons</span><small>{picks.length ? plural(picks.length, "choisi") : "Aucun"}</small>
          <Icon d={UI.down} size={22} sw={2.2} /></button></h2>
        {raysOpen && <div className="bchips" id="vos-rayons">{pickChips("")}</div>}
      </section>
      {understood.length > 0 && <section className="psec">
        <div className="sechead"><h2>Ce que l'app a compris</h2><button className="forget" onClick={forgetTaste}>Oublier</button></div>
        <div className="bchips">{understood.map(u => <button key={u.key} className="soft" onClick={u.go}>{u.label}</button>)}</div>
      </section>}
      <section className="psec">
      <button className="sw" role="switch" aria-checked={learning} onClick={() => setLearn(!learning)}>
        <span>{session.email ? "Tenir compte des fiches que j'ouvre" : "Me reconnaître à mon retour"}
          <small>{session.email ? "Vos fiches ouvertes et vos clics affinent vos deals." : "Les fiches que vous ouvrez affinent vos deals d'une visite à l'autre."}</small></span>
        <span className="knob" aria-hidden="true" /></button>
      </section>
      {known && <div className="out">
        {session.email && <button className="ghost" onClick={logout}>Se déconnecter</button>}
        {!erase ? <button className="ghost" onClick={() => setErase(true)}>Effacer mes données</button>
          : <div className="confirm" role="alert"><span>Vos recherches, favoris, marques et rayons seront effacés.</span>
            <button className="danger" onClick={eraseAll}>Tout effacer</button><button className="ghost" onClick={() => setErase(false)}>Annuler</button></div>}
      </div>}
      {picking === "brands" && <BrandSheet brands={allBrands} followed={followed} onToggle={toggleFollow} onClose={() => setPicking(null)} />}
    </div>;
  }

  return <div className="d"><style>{CSS}</style><div className="app">
    {!(view?.kind === "item" && width < 1000) && <header className="top">
      <button className="logo" onClick={() => goTab("tops")} aria-label="Promo Central, top deals">Promo Central<b>.</b></button>
      <div className="tabs">{tabsList.map(([k, l, d]) => <button key={k} className={tab === k && !view ? "on" : ""} onClick={() => goTab(k)} aria-label={tabSaid(k, l)}>
        <Icon d={d} size={18} />{l}{badge[k] > 0 && <span className="dot">{badge[k]}</span>}</button>)}</div>
      <button className="ibtn" aria-label={fresh ? freshSaid : "Vos recherches"} onClick={() => goTab("me")}>
        <Icon d={UI.bell} size={22} />{fresh > 0 && <span className="dot">{fresh}</span>}</button>
    </header>}
    {error && <div className="empty">{error}</div>}
    {body}
    {view?.kind !== "about" && view?.kind !== "legal" && <footer className="legal">Offres d'enseignes partenaires, remises vérifiées.{" "}
      <button className="lnk" onClick={openAbout}>Comment ça marche</button>{" · "}
      <button className="lnk" onClick={openLegal}>Mentions légales</button></footer>}
    <nav className="d-nav" aria-label="Navigation">{tabsList.map(([k, l, d]) =>
      <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} onClick={() => goTab(k)} aria-label={tabSaid(k, l)}>
        <span className="ic"><Icon d={d} size={23} fill={tab === k && k !== "search"} />
          {badge[k] > 0 && <span className="dot" aria-hidden="true">{badge[k]}</span>}</span>{l}</button>)}</nav>
    {emailFor && <EmailSheet reason={emailFor} onClose={() => setEmailFor(null)}
      onDone={() => { setEmailFor(null); refreshSession(); setVersion(v => v + 1); }} />}
    <Toast text={toast} />
  </div></div>;
}
