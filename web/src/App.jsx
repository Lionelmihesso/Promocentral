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

   Les visuels sont des illustrations originales par catégorie (art.jsx) : aucune image extérieure, aucune requête vers un
   tiers, aucun droit de tiers. Gardé des versions précédentes : le produit comme entrée, un deal identique pour tous, des
   remises réelles seulement (la qualité est implicite), les durées dans la fiche seulement, « Moins cher, comparable »,
   la recherche dans tout le catalogue, la connexion au moment de l'action, contrastes et zones à toucher aux normes. */
import { useState, useEffect, useRef } from "react";
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
  user: [C(12, 8.5, 3.8), "M4.8 20c.8-3.6 3.6-5.6 7.2-5.6s6.4 2 7.2 5.6"],
  share: ["M12 15V4.5", "M8 8l4-4 4 4", "M6 12.5V19a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-6.5"],
  cal: ["M5.5 6h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z", "M4.5 10h15", "M8.5 4v4", "M15.5 4v4"],
  next: ["M9.5 5.5L16 12l-6.5 6.5"],
  target: [C(12, 12, 8), C(12, 12, 4.2), "M12 12h.01"],
  minus: ["M6.5 12h11"],
  down: ["M7 10l5 5 5-5"],
  up: ["M12 18.5v-12", "M6.5 12l5.5-5.5 5.5 5.5"],
};
const Icon = ({ d, size = 20, sw = 1.8, fill }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className="i"
  fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
  {d.map((p, i) => <path key={i} d={p} />)}{fill && <path d={d[0]} fill="currentColor" stroke="none" />}</svg>;

/* ---------------------------------------------------------------- formats */
const eur = n => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " €";
const iso = d => new Date(`${d}T12:00:00`);
const dayLabel = d => new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short" }).format(iso(d));
const daysBetween = (a, b) => Math.round((iso(b) - iso(a)) / 86400000);
const clock = ts => new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(new Date(ts * 1000));
const shortDay = ts => new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" }).format(new Date(ts * 1000));
const plural = (n, w) => `${n} ${w}${n > 1 ? "s" : ""}`;
const norm = s => (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const spanOf = days => days >= 30 ? `${Math.floor(days / 30)} mois` : `${days} jours`;      // « depuis 2 mois » : arrondi en dessous
const FAMILY = { electromenager: "Électroménager", ameublement: "Ameublement", literie: "Literie" };
const EXAMPLES = ["Aspirateur balai sous 300 €", "Lave-linge 9 kg sous 500 €", "Matelas 160x200 sous 600 €", "Canapé d'angle sous 900 €"];
// Recherche : des exemples pour démarrer, les filtres (budget maximum, remise minimale) et les tris.
const TRY = ["aspirateur balai", "lave-linge 9 kg", "matelas 160x200", "canapé d'angle", "réfrigérateur"];
const BUDGETS = [["", "Tous les budgets"], ["200", "Moins de 200 €"], ["500", "Moins de 500 €"], ["1000", "Moins de 1 000 €"], ["2000", "Moins de 2 000 €"]];
const OFFS = [["", "Toutes"], ["1", "En remise"], ["10", "−10 % et plus"], ["20", "−20 % et plus"]];
const SORTS = [["relevance", "Pertinence"], ["price", "Prix croissant"], ["discount", "Remise"]];
const NO_FILTERS = { category: "", budget: "", off: "" };
/* Vos dernières recherches (4, la plus récente d'abord), gardées par ce navigateur seulement : elles orientent le feed
   de la Recherche (« Pour vous ») ; le serveur ne les garde pas. */
const RECENT = "deals.recent", RECENT_MAX = 4;
const recents = {
  get() { try { const v = JSON.parse(localStorage.getItem(RECENT) || "[]"); return Array.isArray(v) ? v.filter(x => typeof x === "string").slice(0, RECENT_MAX) : []; } catch { return []; } },
  set(list) { try { localStorage.setItem(RECENT, JSON.stringify(list)); } catch { /* stockage indisponible */ } },
};
// L'inspiration par pièce : des catégories regroupées comme on pense son intérieur.
const ROOMS = [
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

/* Une mission lancée avant la connexion attend ici le retour du lien (30 minutes au plus) ; le serveur ne garde
   qu'une mission par cible : deux onglets qui la lancent n'en font qu'une. */
const PENDING = "deals.mission";
const pending = {
  get() { try { const p = JSON.parse(localStorage.getItem(PENDING) || "null"); return p && Date.now() - p.at < 1800000 ? p.spec : null; } catch { return null; } },
  set(spec) { try { localStorage.setItem(PENDING, JSON.stringify({ spec, at: Date.now() })); } catch { /* stockage indisponible */ } },
  clear() { try { localStorage.removeItem(PENDING); } catch { /* idem */ } },
};
/* Prix proposés pour une alerte : le plus bas des derniers mois s'il est sous le prix du jour, puis −10 % et −20 %. */
function suggestions(p) {
  const out = [], low = p.position?.low;
  if (low != null && low < Math.round(p.price)) out.push([low, "le plus bas"]);
  for (const f of [0.9, 0.8]) { const v = Math.floor(p.price * f); if (!out.some(([x]) => x === v)) out.push([v, `−${Math.round((1 - f) * 100)} %`]); }
  return out;
}
const specOf = d => ({ product_id: d.product_id, category: d.category, brand: d.brand, features: d.features, attrs: d.attrs });

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
/* le prix du jour sur les derniers mois : un verdict, une jauge */
.d .pos{margin-top:14px;border:1px solid var(--line);border-radius:16px;padding:13px 16px 12px}
.d .pos .vd{display:flex;align-items:center;gap:9px;font-size:15.5px;font-weight:800;letter-spacing:-.01em}
.d .pos .vi{flex:0 0 auto;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--icon);color:#fff}
.d .pos.good .vd{color:var(--good)}.d .pos.good .vi{background:var(--good)}
.d .pos.warn .vd{color:var(--warn)}.d .pos.warn .vi{background:var(--warn)}
.d .gauge{margin-top:12px}
.d .gauge .now{position:relative;height:23px;font-size:11.5px;font-weight:800;color:var(--ink);line-height:14px}
.d .gauge .now span{position:absolute;white-space:nowrap;transform:translateX(-50%)}
.d .gauge .now span.l{transform:none}.d .gauge .now span.r{transform:translateX(-100%)}
.d .track{position:relative;height:8px;border-radius:4px;background:linear-gradient(90deg,#2E8B57 0%,#74B55A 24%,#E6C34D 40%,#E6C34D 60%,#E68B3F 76%,#DC6A36 100%)}
.d .track i{position:absolute;top:50%;width:18px;height:18px;border-radius:50%;background:#fff;border:3px solid var(--ink);transform:translate(-50%,-50%);box-shadow:0 1px 3px rgba(0,0,0,.25)}
.d .ends{display:flex;justify-content:space-between;margin-top:8px;font-size:12.5px;color:var(--mid);font-weight:600}
.d .ends b{color:var(--ink);font-weight:800}
.d .pos .pn{margin:8px 0 0;font-size:13.5px;color:var(--mid);font-weight:600}
/* comptes, marques */
.d .login{margin:16px 16px 0;background:var(--tint);border-radius:22px;padding:20px}
.d .login h3{font-size:19px;font-weight:800;letter-spacing:-.03em;margin:0}
.d .login p{color:var(--mid);margin:8px 0 0;font-size:14px}
.d .cta{display:block;width:100%;margin-top:16px;border:0;background:var(--ink);color:#fff;border-radius:16px;min-height:50px;font-size:15px;font-weight:800}
.d .cta:disabled{opacity:.5}
.d .ghost{border:0;background:none;color:var(--mid);font-size:14px;font-weight:800;min-height:44px;padding:0 16px;margin-top:12px;display:block}
.d .pill{flex:0 0 auto;display:flex;align-items:center;gap:6px;border:0;background:var(--ink);color:#fff;border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:800}
.d .pill.on{background:var(--accent-soft);color:var(--accent)}
.d .me{padding:6px 16px 0;color:var(--mid);font-size:14.5px}
.d .me b{color:var(--ink)}
.d .bchips{display:flex;flex-wrap:wrap;gap:8px;padding:0 16px}
.d .bchips button{border:0;background:var(--tint);border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:800}
.d .bchips button.on{background:var(--accent-soft);color:var(--accent)}
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
.d .brow{display:flex;align-items:center;gap:10px;width:calc(100% - 32px);margin:16px 16px 0;min-height:56px;border:0;border-radius:16px;background:var(--tint);padding:0 14px 0 16px;text-align:left}
.d .brow small{font-size:11.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--mid)}
.d .brow b{font-family:var(--serif);font-weight:400;font-size:24px;line-height:1}
.d .brow span{flex:1;font-size:13.5px;font-weight:700;color:var(--mid)}
.d .fchip.clear{border-color:transparent;background:none;color:var(--mid);padding:0 12px;gap:4px}
.d .fchip.sort{border-color:transparent;background:var(--tint);font-size:14px;padding:0 12px 0 14px}
/* missions : une envie et un prix, en une phrase */
.d .mbox{margin:16px 16px 0;background:var(--terminal);color:#F2F0EC;border-radius:22px;padding:18px}
.d .mbox.feed{margin-top:24px}
.d .mbox .k{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:11.5px;font-weight:700;letter-spacing:.08em;color:#FF9A70}
.d .mbox .k i{width:7px;height:7px;border-radius:50%;background:#FF6A3D;box-shadow:0 0 0 3px rgba(255,106,61,.2)}
.d .mbox h2{color:#fff;margin-top:8px}
.d .mbox p{margin:6px 0 0;color:#BDBBB6;font-size:14px;line-height:1.45}
.d .mform{display:flex;gap:8px;margin-top:14px}
.d .mform input{flex:1;min-width:0;height:52px;border-radius:14px;border:1px solid #3A3C40;background:#1E2023;color:#fff;padding:0 14px;font-size:16px;outline:0}
.d .mform input::placeholder{color:#9A9CA1}
.d .mform input:focus{border-color:#FF9A70}
.d .mform button{flex:0 0 auto;width:52px;height:52px;border-radius:14px;border:0;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center}
.d .mform button:disabled{opacity:.6}
.d .merr{color:#FFB599;font-size:14px;font-weight:700;margin-top:10px;line-height:1.4}
.d .draft{margin:12px 16px 0;border:1px solid var(--line);border-radius:22px;padding:18px}
.d .draft h2{margin-top:6px}
.d .draft .scroller{padding:14px 0 2px;margin:0 -18px;padding-left:18px;padding-right:18px}
.d .draft .cta{margin-top:18px}
.d .draft .ghost{margin:6px auto 0}
.d .draft .near{width:100%}
.d .draft .hint,.d .note{color:var(--mid);font-size:13.5px;margin:10px 0 0;line-height:1.45}
.d .note{padding:0 16px}
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
.d .mline{display:flex;align-items:center;gap:10px;width:calc(100% - 32px);margin:0 16px 16px;min-height:52px;border:0;border-radius:16px;background:var(--terminal);color:#F2F0EC;padding:0 14px;text-align:left;font-size:14.5px;font-weight:600}
.d .mline span{flex:1}.d .mline b{color:#FF9A70;font-weight:800}
.d .toast{position:fixed;bottom:104px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 18px;border-radius:999px;font-size:14px;font-weight:700;z-index:11;white-space:nowrap}
nav.d-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:520px;display:grid;grid-template-columns:repeat(5,1fr);gap:4px;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid var(--line);z-index:5;padding:6px 8px calc(10px + env(safe-area-inset-bottom))}
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
  .d .brow{margin-left:0;margin-right:0;width:100%;max-width:640px}
  .d .ctags.row{flex-wrap:wrap;margin:0;padding:0}
  .d .mbox,.d .draft,.d .mline{margin-left:0;margin-right:0}
  .d .mline{width:100%;max-width:640px}
  .d .mbox{padding:26px 28px}.d .mbox .mform{max-width:640px}
  .d .mwrap{max-width:760px}
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
@media (hover:hover){.d .card:hover .vis{filter:brightness(.97)}.d .chips button:hover,.d .ctag:hover,.d .brow:hover{background:var(--tint2)}.d .chips button.on:hover{background:var(--ink)}}
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

function LoginSheet({ message, onClose, onDone }) {
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
    <form className="sheet" onClick={e => e.stopPropagation()} onSubmit={submit}>
      {!sent ? <>
        <div className="eyebrow">Connexion</div>
        <h2>{message}</h2>
        <p className="hint">Votre e-mail suffit. Un lien vous est envoyé : aucun mot de passe.</p>
        <input type="email" required autoFocus value={email} onChange={e => setEmail(e.target.value)} placeholder="vous@exemple.fr" aria-label="Adresse e-mail" />
        {err && <div className="err">{err}</div>}
        <button className="cta" disabled={busy}>Recevoir le lien</button>
      </> : <>
        <div className="eyebrow">Lien envoyé</div>
        <h2>Ouvrez le lien reçu sur cet appareil.</h2>
        <p className="hint">Il est valable 15 minutes. Revenez ensuite ici : vous êtes connecté.</p>
        <button type="button" className="cta" onClick={onDone}>J'ai ouvert le lien</button>
      </>}
    </form>
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
    ? (item.price <= n ? { ok: true, text: `Déjà à ${eur(item.price)} aujourd'hui` } : { text: `Aujourd'hui ${eur(item.price)} : encore ${eur(item.price - n)}` })
    : like && (like.total > 0 ? { ok: true, text: `${plural(like.total, "comparable")} déjà sous ${eur(n)} aujourd'hui` }
      : like.nearest ? { text: `Le moins cher aujourd'hui : ${eur(like.nearest.price)}` } : { text: "Aucun comparable pour l'instant : la mission guette les nouveaux" });
  const launch = async () => {
    setBusy(true);
    const done = await onLaunch(mode === "like" ? { like: item.id, max_price: n } : { product_id: item.id, max_price: n });
    setBusy(false);
    if (done) onClose();
  };
  return <div className="sheet-wrap" onClick={onClose}>
    <div className="sheet" ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="alert-h" onClick={e => e.stopPropagation()}>
      <div className="eyebrow">Mission</div>
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
      <p className="hint">Un e-mail la nuit où c'est le cas. Vos missions sont dans l'onglet Missions.</p>
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
    <b className="pc">−{p.pct} %</b>{eur(p.price)}</span>);
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

/* Le prix du jour sur les derniers mois, pour décider vite : un verdict en mots, une jauge du plus bas au plus haut
   relevés, un point pour aujourd'hui (règle côté serveur : catalog.position). */
// band : la zone de la jauge où tombe chaque verdict (vert, jaune, orange) ; le point y suit le rang du jour.
const VERDICT = {
  lowest: { tone: "good", icon: UI.check, band: [0, 0], say: span => `Au plus bas depuis ${span}` },
  low: { tone: "good", icon: UI.check, band: [0.04, 0.3], say: span => `Un des prix les plus bas depuis ${span}` },
  usual: { tone: "", icon: UI.minus, band: [0.38, 0.62], say: () => "Son prix habituel" },
  high: { tone: "warn", icon: UI.up, band: [0.7, 0.96], say: () => "Plus cher que d'habitude" },
};
function PricePosition({ pos, price }) {
  if (!pos) return null;
  const v = VERDICT[pos.level], span = spanOf(pos.days), range = pos.high - pos.low;
  const at = Math.min(v.band[1], Math.max(v.band[0], pos.rank));         // place parmi les jours, dans la zone du verdict
  const left = `calc(9px + (100% - 18px) * ${at.toFixed(3)})`;
  return <div className={`pos ${v.tone}`}>
    <div className="vd"><span className="vi"><Icon d={v.icon} size={14} sw={2.8} /></span>{v.say(span)}</div>
    {range > 0 && <div className="gauge" role="img" aria-label={`Depuis ${span}, de ${eur(pos.low)} à ${eur(pos.high)} ; aujourd'hui ${eur(price)}`}>
      <div className="now" aria-hidden="true"><span className={at < 0.12 ? "l" : at > 0.88 ? "r" : ""} style={{ left: at < 0.12 ? 0 : at > 0.88 ? "100%" : left }}>aujourd'hui</span></div>
      <div className="track"><i style={{ left }} /></div>
      <div className="ends" aria-hidden="true"><span>Le plus bas <b>{eur(pos.low)}</b></span><span>Le plus haut <b>{eur(pos.high)}</b></span></div>
    </div>}
    {pos.level === "high" && <p className="pn">Souvent à {eur(pos.usual)} {pos.days >= 60 ? `ces ${Math.floor(pos.days / 30)} derniers mois`
      : pos.days >= 30 ? "ce dernier mois" : `ces ${pos.days} derniers jours`}.</p>}
  </div>;
}

export default function App() {
  const [tab, setTab] = useState("home");
  const [view, setView] = useState(null);          // null | item | brand | category | room — chacune garde `from` (« Retour »)
  const [q, setQ] = useState("");                  // Recherche
  const [all, setAll] = useState(null);            // remises du jour (bandeau, notre sélection)
  const [allCats, setAllCats] = useState([]);      // toutes les catégories (count : remises du jour)
  const [allBrands, setAllBrands] = useState([]);  // toutes les marques (count : remises du jour)
  const [filters, setFilters] = useState(NO_FILTERS);  // Recherche : catégorie, budget maximum, remise minimale
  const [sortBy, setSortBy] = useState("relevance");
  const [picking, setPicking] = useState(null);    // filtre en cours de choix : category | budget | off | sort
  const [results, setResults] = useState(null);    // Recherche : produits trouvés (une requête ou un filtre)
  const [searching, setSearching] = useState(false);  // une réponse est attendue : les résultats montrés pâlissent
  const [feed, setFeed] = useState(null);          // Recherche : le feed d'avant toute saisie
  const [recent, setRecent] = useState(() => recents.get());
  const seq = useRef(0);                           // seule la réponse à la dernière saisie compte
  const [order, setOrder] = useState("pct");       // pages marque et catégorie : pct | asc | desc
  const [list, setList] = useState(null);          // pièce
  const [item, setItem] = useState(null);
  const [brandPage, setBrandPage] = useState(null);
  const [catPage, setCatPage] = useState(null);
  const [missions, setMissions] = useState(null);  // { missions, reached } de la personne connectée
  const [mtext, setMtext] = useState("");          // la phrase de la mission
  const [draft, setDraft] = useState(null);        // ce qui est compris, avant de lancer
  const [mprice, setMprice] = useState("");
  const [mbusy, setMbusy] = useState(false);
  const [merr, setMerr] = useState(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const mfield = useRef(null);
  const mpriceNow = useRef("");
  mpriceNow.current = mprice;
  const [session, setSession] = useState({ checked: false, email: null });
  const [saved, setSaved] = useState(new Set());
  const [followed, setFollowed] = useState(new Set());
  const [savedList, setSavedList] = useState(null);
  const [version, setVersion] = useState(0);
  const [login, setLogin] = useState(null);
  const [toast, setToast] = useState(null);
  const [error, setError] = useState(null);
  const width = useWidth();
  const cols = width >= 1200 ? 5 : width >= 1000 ? 4 : width >= 700 ? 3 : 2;

  const flash = t => { setToast(t); setTimeout(() => setToast(null), 2200); };
  const askLogin = message => setLogin({ message });
  const loadMissions = () => api("missions").then(setMissions).catch(() => {});
  const refreshSession = () => api("auth/me")
    .then(d => setSession({ checked: true, email: d.email }))
    .catch(() => setSession({ checked: true, email: null }));

  useEffect(() => {
    refreshSession();
    const url = new URL(window.location.href);
    if (url.searchParams.get("auth") === "expired") flash("Ce lien a expiré. Demandez-en un nouveau.");
    const shared = Number(url.searchParams.get("p"));                       // lien partagé : /?p=<produit>
    if (shared) setView({ kind: "item", id: shared });
    if (url.searchParams.has("auth") || url.searchParams.has("p")) window.history.replaceState({}, "", url.pathname);
    const again = () => { if (document.visibilityState === "visible") refreshSession(); };
    document.addEventListener("visibilitychange", again);
    return () => document.removeEventListener("visibilitychange", again);
  }, []);

  useEffect(() => {
    if (!session.checked) return;
    if (!session.email) { setSaved(new Set()); setFollowed(new Set()); setSavedList(null); return; }
    api("follows").then(d => setFollowed(new Set(d.brands))).catch(() => {});
    api("saves").then(d => { setSavedList(d.products); setSaved(new Set(d.products.map(p => p.id))); }).catch(() => {});
  }, [session.checked, session.email, version]);

  useEffect(() => {
    if (tab !== "saved" || !session.email) return;
    api("saves").then(d => setSavedList(d.products)).catch(() => {});
  }, [tab, session.email]);

  useEffect(() => {                                                         // missions : l'état du jour de chacune
    if (!session.checked) return;
    if (!session.email) { setMissions(null); return; }
    loadMissions();
  }, [session.checked, session.email, version, tab]);

  useEffect(() => {                                                         // la mission lancée avant la connexion
    if (!session.email) return;
    const spec = pending.get();
    if (!spec) return;
    pending.clear();
    api("missions", spec).then(() => { flash("Mission lancée : on vous prévient"); setDraft(null); setMtext(""); loadMissions(); })
      .catch(ex => flash(ex.message));
  }, [session.email]);

  useEffect(() => {                                                         // le prix change : ce qui y répond déjà
    if (!draft) return;
    const n = mprice === "" ? null : Number(mprice);
    if (n === draft.max_price || (n !== null && !(n >= 1))) return;
    const t = setTimeout(() => api("missions/preview", { ...specOf(draft), max_price: n })
      .then(v => { const now = mpriceNow.current === "" ? null : Number(mpriceNow.current); if (v.max_price === now) setDraft(d => d && v); })
      .catch(ex => setMerr(ex.message)), 300);
    return () => clearTimeout(t);
  }, [mprice, draft]);

  useEffect(() => {
    api("categories?all=1").then(setAllCats).catch(() => setError("Impossible de charger les catégories."));
    api("brands?all=1").then(setAllBrands).catch(() => {});
    api("today").then(d => { setAll(d); setError(null); }).catch(() => setError("Impossible de charger les remises."));
  }, [version]);

  useEffect(() => {                                                         // le feed de la Recherche, prêt avant d'y aller
    api(recent.length ? `search?recent=${encodeURIComponent(recent.join("|"))}` : "search").then(setFeed).catch(() => {});
  }, [recent, version]);

  useEffect(() => {                                                         // Recherche : une requête, des filtres, un tri
    const term = q.trim(), any = term || filters.category || filters.budget || filters.off;
    const n = ++seq.current;
    if (view || tab !== "search") return;                                   // une fiche ouverte : les résultats attendent le retour
    if (!any) { setResults(null); setSearching(false); return; }            // plus rien de tapé : le feed
    const params = new URLSearchParams({ q: term, category: filters.category, max: filters.budget, off: filters.off, sort: sortBy });
    for (const [k, v] of [...params]) if (!v) params.delete(k);
    setSearching(true);
    const t = setTimeout(() => api(`search?${params}`)
      .then(d => { if (n === seq.current) { setResults(d); setSearching(false); } })
      .catch(() => { if (n === seq.current) setSearching(false); }), term ? 200 : 0);
    return () => clearTimeout(t);
  }, [tab, q, filters, sortBy, view, version]);

  useEffect(() => {
    if (!view) return;
    setError(null);
    if (view.kind === "item") api(`item/${view.id}`).then(setItem).catch(() => setError("Produit introuvable."));
    if (view.kind === "brand") api(`brand/${encodeURIComponent(view.name)}`).then(setBrandPage).catch(() => setError("Marque introuvable."));
    if (view.kind === "category") api(`category/${view.key}`).then(setCatPage).catch(() => setError("Catégorie introuvable."));
    if (view.kind === "room") api(`today?category=${view.room.cats.join(",")}`).then(setList).catch(() => setError("Pièce introuvable."));
  }, [view, version]);

  useEffect(() => { window.scrollTo(0, 0); setAlertOpen(false); setPicking(null); }, [view, tab]);

  const isSaved = id => saved.has(id);
  const isFollowed = b => followed.has(b);

  const toggleSave = async (id, e) => {
    if (e) e.stopPropagation();
    if (!session.email) return askLogin("Connectez-vous pour garder ce produit");
    const on = !saved.has(id);
    setSaved(s => on ? withIn(s, id) : withOut(s, id));
    try { await api("save", { product_id: id, on }); }
    catch (ex) {
      setSaved(s => on ? withOut(s, id) : withIn(s, id));
      if (ex.status === 401) askLogin("Connectez-vous pour garder ce produit");
    }
  };

  const toggleFollow = async brand => {
    if (!session.email) return askLogin(`Connectez-vous pour suivre ${brand}`);
    const on = !followed.has(brand);
    setFollowed(s => on ? withIn(s, brand) : withOut(s, brand));
    try { await api("brand/follow", { brand, on }); setVersion(v => v + 1); flash(on ? `${brand} est suivie` : `${brand} n'est plus suivie`); }
    catch (ex) {
      setFollowed(s => on ? withOut(s, brand) : withIn(s, brand));
      if (ex.status === 401) askLogin(`Connectez-vous pour suivre ${brand}`);
    }
  };

  const logout = async () => {
    await api("auth/logout", {}).catch(() => {});
    setSession({ checked: true, email: null });
    flash("Vous êtes déconnecté");
  };

  const share = async p => {
    const url = `${window.location.origin}/?p=${p.id}`, title = `${p.brand} — ${p.name || p.title}`;
    try {
      if (navigator.share) await navigator.share({ title, url });
      else { await navigator.clipboard.writeText(url); flash("Lien copié"); }
    } catch { /* partage annulé */ }
  };

  // Ce que la personne cherche : sa requête, ou la catégorie choisie ; retenu quand elle ouvre une fiche trouvée, valide
  // au clavier ou touche un exemple.
  const intent = q.trim() || (allCats.find(c => c.key === filters.category)?.label || "").toLowerCase();
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
  const goTab = t => { setView(null); setItem(null); setBrandPage(null); setCatPage(null); setList(null); setTab(t); setQ("");
    setFilters(NO_FILTERS); setSortBy("relevance"); if (t === tab && !view) window.scrollTo(0, 0); };   // l'onglet déjà ouvert : en haut
  // Chaque vue garde celle d'où l'on vient : « Retour » y ramène. via : d'où vient la fiche (mesure des clics sortants).
  const open = (id, via) => { if (via === "search") remember(intent); setItem(null); setView(v => ({ kind: "item", id, via, from: v })); };
  const openBrand = name => { setBrandPage(null); setOrder("pct"); setView(v => ({ kind: "brand", name, from: v })); };
  const openCategory = key => { setCatPage(null); setOrder("pct"); setView(v => ({ kind: "category", key, from: v })); };
  const openRoom = room => { setList(null); setView(v => ({ kind: "room", room, from: v })); };
  const goBack = () => { setItem(null); setBrandPage(null); setCatPage(null); setList(null); setView(view?.from || null); };

  // Missions : une phrase → ce qui est compris et ce qui y répond déjà → lancer (connexion au moment de l'action).
  const parseMission = async text => {
    const t = (text || "").trim();
    if (!t) return;
    setMbusy(true); setMerr(null);
    try { const d = await api("missions/parse", { text: t }); setDraft(d); setMprice(d.max_price == null ? "" : String(Math.round(d.max_price))); }
    catch (ex) { setDraft(null); setMerr(ex.message); }
    finally { setMbusy(false); }
  };
  const goMission = (text, focus) => {
    goTab("missions"); setMtext(text); setMerr(null);
    if (focus) { setDraft(null); setTimeout(() => { const el = mfield.current; if (el) { el.focus(); el.setSelectionRange(text.length, text.length); } }, 60); }
    else parseMission(text);
  };
  const launch = async spec => {
    if (!session.email) { pending.set(spec); askLogin("Connectez-vous pour lancer la mission"); return false; }
    try { await api("missions", spec); flash("Mission lancée : on vous prévient"); loadMissions(); return true; }
    catch (ex) {
      if (ex.status === 401) { pending.set(spec); askLogin("Connectez-vous pour lancer la mission"); }
      else flash(ex.message);
      return false;
    }
  };
  const stopMission = async m => {
    setMissions(x => x && { ...x, missions: x.missions.filter(y => y.id !== m.id), reached: x.reached - (m.total > 0 ? 1 : 0) });
    try { await api("missions/delete", { id: m.id }); flash("Mission arrêtée"); } catch { loadMissions(); }
  };
  const dropOf = p => p.saved_price ? Math.round(p.saved_price - p.price) : 0;
  const drops = (savedList || []).filter(p => dropOf(p) >= 1).length;
  const said = p => `${p.brand}, ${p.name || p.title}, ${p.pct > 0 ? `moins ${p.pct} %, ` : ""}${eur(p.price)}`;

  const card = via => p => <article key={p.id} className="card" role="button" tabIndex={0} aria-label={said(p)}
    onClick={() => open(p.id, via)} onKeyDown={e => { if (e.key === "Enter") open(p.id, via); }}>
    <div className="vis" style={{ aspectRatio: `1 / ${ratioOf(p.category)}` }}>
      <Vignette category={p.category} seed={p.id} />
      {p.saving >= 1 ? <span className="badge good">{eur(p.saving)} de moins</span> : p.pct > 0 && <span className="badge">−{p.pct} %</span>}
      <button className={`heart ${isSaved(p.id) ? "on" : ""}`} aria-pressed={isSaved(p.id)}
        aria-label={isSaved(p.id) ? "Retirer des favoris" : "Ajouter aux favoris"} onClick={e => toggleSave(p.id, e)}>
        <span><Icon d={UI.heart} size={18} fill={isSaved(p.id)} /></span></button>
    </div>
    <div className="meta">
      <div className="brand">{p.brand}</div>
      <div className="name">{p.name || p.title}</div>
      <div className="price"><b className={p.pct > 0 ? "deal" : ""}>{eur(p.price)}</b>{p.pct > 0 && p.was && <s>{eur(p.was)}</s>}</div>
      {dropOf(p) >= 1 && <div className="drop">Baisse de {eur(dropOf(p))}</div>}
    </div>
  </article>;
  const grid = (items, via) => <Masonry items={items} cols={cols} render={card(via)} />;

  const searchBar = <form role="search" onSubmit={e => { e.preventDefault(); remember(q); e.currentTarget.querySelector("input")?.blur(); }}>
    <label className="sbar big"><Icon d={UI.search} size={20} />
    <input value={q} onChange={e => setQ(e.target.value)} placeholder="Une marque, un produit, une envie…" aria-label="Rechercher" enterKeyHint="search" />
    {q && <button type="button" className="sx" aria-label="Effacer" onClick={() => setQ("")}><Icon d={UI.x} size={18} /></button>}</label></form>;
  const back = <button className="back" onClick={goBack}><Icon d={UI.back} size={18} sw={2.2} />Retour</button>;
  const tabsList = [["home", "Accueil", UI.home], ["search", "Recherche", UI.search], ["missions", "Missions", UI.target],
    ["saved", "Favoris", UI.heart], ["me", "Profil", UI.user]];
  const reached = missions?.reached || 0;
  const badge = { missions: reached, saved: drops };
  const reachedSaid = reached > 1 ? `${reached} missions atteintes` : reached === 1 ? "1 mission atteinte" : "";
  const tabSaid = (k, l) => k === "missions" && reached ? `${l}, ${reachedSaid}` : k === "saved" && drops ? `${l}, ${plural(drops, "baisse")} de prix` : undefined;
  // « Pas au bon prix ? » : la mission reprend la requête (ou la catégorie choisie) et le budget.
  const missionWhat = intent;
  const missionText = missionWhat && `${missionWhat}${filters.budget ? ` sous ${filters.budget} €` : ""}`;
  const missionLine = (none = false) => missionWhat.length >= 3 && <button className="mline" onClick={() => goMission(missionText)}>
    <Icon d={UI.target} size={20} /><span>{none ? "Pas encore là ?" : "Pas au bon prix ?"} <b>Lancer une mission</b></span><Icon d={UI.next} size={18} sw={2.2} /></button>;
  const composer = (home) => <form className={`mbox ${home ? "feed" : ""}`} onSubmit={e => { e.preventDefault(); home ? goMission(mtext) : parseMission(mtext); }}>
    <div className="k"><i />{home ? "MISSION" : "NOUVELLE MISSION"}</div>
    {home && <><h2>Une envie précise ?</h2><p>Dites-la avec votre prix : on guette chaque nuit et on vous prévient.</p></>}
    <div className="mform">
      <input ref={home ? undefined : mfield} value={mtext} onChange={e => setMtext(e.target.value)} placeholder="aspirateur balai sous 300 €"
        aria-label="Votre mission en une phrase : le produit et votre prix" enterKeyHint="go" />
      <button aria-label={home ? "Lancer la mission" : "Voir la mission"} disabled={mbusy}><Icon d={UI.next} size={22} sw={2.4} /></button></div>
    {!home && merr && <div className="merr" role="alert">{merr}</div>}
  </form>;
  const nearRow = (p, label) => <button className="near" onClick={() => open(p.id, "mission")} aria-label={`${label} : ${said(p)}`}>
    <span className="th"><Vignette category={p.category} seed={p.id} ratio={1} /></span>
    <span className="tx"><small>{label}</small><span>{p.brand} {p.name || p.title}</span></span><b>{eur(p.price)}</b>
    <Icon d={UI.next} size={16} sw={2.2} /></button>;
  const missionItem = m => {
    const ok = m.total > 0, now = ok ? m.matches[0].price : m.nearest?.price;
    return <article key={m.id} className={`mi ${ok ? "ok" : ""}`}>
      <div className="row"><div style={{ minWidth: 0 }}>
        <div className="st"><i />{ok ? `ATTEINTE · ${plural(m.total, "produit").toUpperCase()}` : "EN VEILLE"}</div>
        <h3>{m.title}</h3>
        <div className="nums"><span>Objectif <b>{eur(m.max_price)}</b></span>
          {now != null && <span>Aujourd'hui <b className={ok ? "ok" : ""}>{eur(now)}</b></span>}
          {!ok && now != null && <span>Encore <b>{eur(now - m.max_price)}</b></span>}
          {!ok && now == null && <span>{m.product_id ? "Indisponible aujourd'hui" : "Rien de suivi pour l'instant"}</span>}</div>
      </div>
      <button className="ibtn" aria-label={`Arrêter la mission ${m.title}`} onClick={() => stopMission(m)}><Icon d={UI.x} size={18} /></button></div>
      {ok && <div className="scroller">{m.matches.map(card("mission"))}</div>}
      {!ok && m.nearest && nearRow(m.nearest, m.product_id ? "Voir la fiche" : "Le plus proche")}
    </article>;
  };
  const loginCard = (title, msg) => <div className="login"><h3>{title}</h3><p>Votre e-mail suffit, sans mot de passe.</p>
    <button className="cta" onClick={() => askLogin(msg)}>Me connecter</button></div>;
  const categories = allCats.filter(c => c.count > 0);                    // celles qui ont des remises aujourd'hui
  const promoBrands = allBrands.filter(b => b.count > 0 && b.top).slice(0, 12);
  // Des cartes au format des pièces : un visuel (le produit de la meilleure remise), la marque, « Jusqu'à −20 % ».
  const bigCard = (key, label, best, sub, art, seed, onClick, cls = "") => <button key={key} className={`room ${cls}`} onClick={onClick}
    aria-label={`${label}, jusqu'à moins ${best} %, ${sub}`}>
    <Vignette category={art} seed={seed} ratio={1.32} floor={0.7} zoom={ratioOf(art) > 1 ? 0.9 : 1.04} /><span className="shade" />
    <span className="rt"><b>{label}</b><span>Jusqu'à −{best} %</span><small>{sub}</small></span></button>;
  const sortBar = <div className="chips" role="group" aria-label="Trier">{[["pct", "Remises d'abord"], ["asc", "Prix croissant"], ["desc", "Prix décroissant"]].map(([k, l]) =>
    <button key={k} className={order === k ? "on" : ""} aria-pressed={order === k} onClick={() => setOrder(k)}>{l}</button>)}</div>;
  const ordered = items => order === "pct" ? items : [...items].sort((a, b) => order === "asc" ? a.price - b.price : b.price - a.price);
  const rooms = ROOMS.map(r => {
    const here = categories.filter(c => r.cats.includes(c.key));
    return here.length ? { ...r, best: Math.max(...here.map(c => c.best)), sub: here.map(c => c.label).join(", "),
      art: here.some(c => c.key === r.art) ? r.art : here[0].key } : null;
  }).filter(Boolean);

  let body;
  if (view?.kind === "item" && item) {
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
          <div className="prices">{item.pct > 0 && <span className="pct">−{item.pct} %</span>}<span className="now">{eur(item.price)}</span>
            {item.pct > 0 && item.was && <s>{eur(item.was)}</s>}</div>
          <PricePosition pos={item.position} price={item.price} />
          {when && <div className="when"><Icon d={UI.cal} size={20} />{when}</div>}
          {best && <a className="buy" href={`/api/r/out/${best.offer_id}?from=${source}`} target="_blank" rel="noopener">
            Voir l'offre chez {best.merchant}<Icon d={UI.ext} size={18} sw={2.2} /></a>}
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
      {alertOpen && <AlertSheet item={item} current={mine} onClose={() => setAlertOpen(false)} onLaunch={launch} onStop={stopMission} />}
    </div>;
  } else if (view?.kind === "brand" && brandPage) {
    const on = isFollowed(brandPage.brand);
    body = <>
      {back}
      <div className="pagehead"><div><h1>{brandPage.brand}</h1>
        <div className="sub">{brandPage.deals ? `${plural(brandPage.deals, "remise")} aujourd'hui · ` : ""}{plural(brandPage.products.length, "produit")}</div></div>
        <button className={`pill ${on ? "on" : ""}`} onClick={() => toggleFollow(brandPage.brand)} aria-pressed={on}>
          <Icon d={on ? UI.check : UI.plus} size={17} sw={2.4} />{on ? "Suivie" : "Suivre"}</button></div>
      {sortBar}
      <div style={{ height: 16 }} />
      {grid(ordered(brandPage.products), "brand")}
    </>;
  } else if (view?.kind === "category" && catPage) {
    body = <>
      {back}
      <div className="pagehead"><div><h1>{catPage.label}</h1>
        <div className="sub">{catPage.deals ? `${plural(catPage.deals, "remise")} aujourd'hui · ` : ""}{plural(catPage.products.length, "produit")}</div></div>
        <button className="pill" onClick={() => goMission(`${catPage.kind.toLowerCase()} `, true)}><Icon d={UI.target} size={17} sw={2.2} />Mission</button></div>
      {sortBar}
      <div style={{ height: 16 }} />
      {grid(ordered(catPage.products), "category")}
    </>;
  } else if (view?.kind === "room") {
    body = <>
      {back}
      <div className="pagehead"><div><h1>{view.room.label}</h1>
        <div className="sub">{list ? `${plural(list.total, "remise")} · ${view.room.sub}` : "…"}</div></div></div>
      <div style={{ height: 18 }} />
      {list && grid(list.products)}
      {list && list.total === 0 && <div className="empty">Aucune remise dans cette pièce aujourd'hui.</div>}
    </>;
  } else if (tab === "home") {                    // éditorial : des pièces, des marques, une sélection ; chercher, c'est l'onglet Recherche
    const items = all?.products || [];
    body = <>
      <Ticker items={items} publishedAt={all?.published_at} />
      <div className="intro"><h1>De bonnes affaires, pour vos envies.</h1></div>
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
      {grid(items.slice(0, cols * 2))}{/* le module mission, après deux rangées de remises */}
      {all && composer(true)}
      {items.length > cols * 2 && <div style={{ height: 18 }} />}
      {grid(items.slice(cols * 2))}
    </>;
  } else if (tab === "search") {                  // un champ, trois filtres, un tri, et un feed que chaque saisie adapte
    const term = q.trim(), t = norm(term);
    const active = filters.category || filters.budget || filters.off, any = term || active;
    const brandHit = t.length >= 2 ? allBrands.find(b => norm(b.name) === t) || allBrands.find(b => norm(b.name).startsWith(t)) : null;
    const catOptions = (results && term ? results.categories : allCats.map(c => ({ key: c.key, label: c.label, count: c.products })))
      .slice().sort((a, b) => a.label.localeCompare(b.label, "fr"));
    const label = (list, v) => list.find(([k]) => k === v)?.[1];
    const catName = allCats.find(c => c.key === filters.category)?.label;
    const chip = (key, name, value) => <button key={key} className={`fchip ${value ? "on" : ""}`} onClick={() => setPicking(key)} aria-haspopup="dialog"
      aria-label={value ? `${name} : ${value}` : name}>{value || name}<Icon d={UI.down} size={15} sw={2.4} /></button>;
    const sheets = {
      category: ["Catégorie", [["", "Toutes les catégories"], ...catOptions.map(c => [c.key, c.label, c.count])], filters.category,
        v => setFilters(f => ({ ...f, category: v }))],
      budget: ["Budget", BUDGETS, filters.budget, v => setFilters(f => ({ ...f, budget: v }))],
      off: ["Remise", OFFS, filters.off, v => setFilters(f => ({ ...f, off: v }))],
      sort: ["Trier", SORTS, sortBy, setSortBy],
    };
    const mine = feed?.recent?.length > 0;                // le feed suit vos dernières recherches
    const feedHead = <div className="sechead"><h2>{mine ? "Pour vous" : "À découvrir"}</h2>
      <span className="n">{mine ? "D'après vos recherches" : feed ? plural(feed.total, "produit") : ""}</span></div>;
    body = <>
      <div className="pagehead"><h1>Recherche</h1></div>
      {searchBar}
      <div className="filters" role="group" aria-label="Filtres">
        {chip("category", "Catégorie", catName)}{chip("budget", "Budget", filters.budget && label(BUDGETS, filters.budget))}
        {chip("off", "Remise", filters.off && label(OFFS, filters.off))}
        {active && <button className="fchip clear" onClick={() => setFilters(NO_FILTERS)}><Icon d={UI.x} size={15} sw={2.4} />Effacer</button>}
      </div>
      {!any && <div className="tryit">{recent.length > 0
        ? <><div className="th"><h3>Vos recherches</h3><button className="forget" onClick={forget} aria-label="Effacer vos recherches">Effacer</button></div>
          <div className="ctags row">{recent.map(x => <button key={x} className="ctag" onClick={() => { setQ(x); remember(x); }}>{x}</button>)}</div></>
        : <><h3>Essayez</h3>
          <div className="ctags row">{TRY.map(x => <button key={x} className="ctag" onClick={() => { setQ(x); remember(x); }}>{x}</button>)}</div></>}
      </div>}
      {!any || !results ? <>{feedHead}<div className={`flow ${any ? "dim" : ""}`}>{grid(feed?.products || [], "feed")}</div></>
        : results.total === 0 ? <>{/* rien trouvé : on le dit, on propose de guetter, et le feed reste là */}
          <div className="sechead"><h2>{term ? `Rien pour « ${term} »` : "Rien avec ces filtres"}</h2></div>
          {missionLine(true)}
          {feedHead}{grid(feed?.products || [], "feed")}
        </> : <>
        {brandHit && <button className="brow" onClick={() => openBrand(brandHit.name)} aria-label={`La marque ${brandHit.name}`}>
          <small>Marque</small><b>{brandHit.name}</b><span>{plural(brandHit.products, "produit")}</span><Icon d={UI.next} size={18} sw={2.2} /></button>}
        <div className="sechead"><h2>{plural(results.total, "produit")}</h2>
          <button className="fchip sort" onClick={() => setPicking("sort")} aria-haspopup="dialog" aria-label={`Trier : ${label(SORTS, sortBy)}`}>
            {label(SORTS, sortBy)}<Icon d={UI.down} size={15} sw={2.4} /></button></div>
        {missionLine()}
        <div className={`flow ${searching ? "dim" : ""}`}>{grid(results.products, "search")}</div>
      </>}
      {picking && <ChoiceSheet title={sheets[picking][0]} options={sheets[picking][1]} value={sheets[picking][2]} onPick={sheets[picking][3]}
        onClose={() => setPicking(null)} />}
    </>;
  } else if (tab === "missions") {
    const mine = missions?.missions || [];
    const n = Number(mprice), priced = mprice !== "" && n >= 1;
    let draftBox = null;
    if (draft) {
      const cheapest = draft.total > 0 ? draft.matches[0].price : draft.nearest?.price;
      const sugg = !priced && cheapest ? [0.9, 0.8].map(f => [Math.floor(cheapest * f), `−${Math.round((1 - f) * 100)} %`]) : [];
      const state = draft.total > 0
        ? { ok: priced, text: priced ? `${plural(draft.total, "produit")} déjà sous ${eur(n)} aujourd'hui`
          : `${plural(draft.total, "produit")} ${draft.total > 1 ? "correspondent" : "correspond"}, dès ${eur(cheapest)}` }
        : draft.nearest ? { text: priced ? `Aujourd'hui dès ${eur(draft.nearest.price)} : encore ${eur(draft.nearest.price - n)}`
          : `Le moins cher aujourd'hui : ${eur(draft.nearest.price)}` }
          : { text: "Rien de suivi n'y répond encore : la mission guette les nouveaux produits" };
      draftBox = <div className="draft">
        <div className="eyebrow">Vous cherchez</div>
        <h2>{draft.title}</h2>
        <label className="pinput"><span>Prix maximum</span>
          <input type="number" inputMode="numeric" min="1" value={mprice} onChange={e => setMprice(e.target.value)} placeholder="—"
            aria-label="Votre prix maximum, en euros" /><b>€</b></label>
        {sugg.length > 0 && <div className="pchips" style={{ marginTop: 10 }}>{sugg.map(([v, l]) =>
          <button key={v} onClick={() => setMprice(String(v))}><b>{eur(v)}</b><span>{l}</span></button>)}</div>}
        <div className={`state ${state.ok ? "ok" : ""}`} role="status"><i />{state.text}</div>
        {draft.total > 0 && <div className="scroller">{draft.matches.map(card("mission"))}</div>}
        {draft.total === 0 && draft.nearest && nearRow(draft.nearest, "Le plus proche")}
        <button className="cta" disabled={!priced} onClick={async () => { if (await launch({ ...specOf(draft), max_price: n })) { setDraft(null); setMtext(""); } }}>
          {priced ? `Lancer la mission · ${eur(n)} max` : "Indiquez votre prix"}</button>
        <button className="ghost" onClick={() => { setDraft(null); setMerr(null); }}>Annuler</button>
        <p className="hint">Un e-mail la nuit où c'est le cas, jamais deux fois pour le même prix.</p>
      </div>;
    }
    body = <div className="mwrap">
      <div className="pagehead"><div><h1>Missions</h1><div className="sub">Votre envie, votre prix : on guette pour vous.</div></div></div>
      {composer(false)}
      {!draft && <div className="chips" role="group" aria-label="Exemples de missions">{EXAMPLES.map(x =>
        <button key={x} onClick={() => { setMtext(x); parseMission(x); }}>{x}</button>)}</div>}
      {draftBox}
      {session.email && mine.length > 0 && <>
        <div className="sechead"><h2>Vos missions</h2><span className="n">{reached}/{mine.length} atteinte{reached > 1 ? "s" : ""}</span></div>
        <div className="mlist">{mine.map(missionItem)}</div>
      </>}
      {session.email && missions && mine.length === 0 && !draft && <p className="note" style={{ marginTop: 18 }}>Aucune mission en cours. Une phrase suffit : le produit, et votre prix.</p>}
      {session.checked && !session.email && !draft && <p className="note" style={{ marginTop: 18 }}>Essayez sans compte : on vous montre ce qui y répond déjà. Votre e-mail n'est demandé qu'au lancement.</p>}
    </div>;
  } else if (tab === "saved") {
    body = <>
      <div className="pagehead"><h1>Favoris</h1></div>
      {!session.checked && <div className="empty">Chargement…</div>}
      {session.checked && !session.email && loginCard("Gardez vos coups de cœur.", "Connectez-vous pour retrouver vos favoris")}
      {session.email && <>
        <div style={{ height: 18 }} />
        {savedList && savedList.length === 0 && <div className="empty" style={{ paddingTop: 0 }}>Touchez le cœur d'un produit pour le garder ici.</div>}
        {grid(savedList || [])}
      </>}
    </>;
  } else {
    body = <>
      <div className="pagehead"><h1>Profil</h1></div>
      {!session.checked && <div className="empty">Chargement…</div>}
      {session.checked && !session.email && loginCard("Vos favoris et vos marques, partout.", "Connectez-vous à Deals")}
      {session.email && <>
        <div className="me">Connecté avec <b>{session.email}</b></div>
        <div className="sechead"><h2>Marques suivies</h2></div>
        {followed.size === 0 && <div className="empty" style={{ paddingTop: 0 }}>Suivez une marque depuis sa page : ses remises passent en tête.</div>}
        {followed.size > 0 && <div className="bchips">{[...followed].map(b => <button key={b} onClick={() => openBrand(b)}>{b}</button>)}</div>}
        <button className="ghost" onClick={logout}>Se déconnecter</button>
      </>}
    </>;
  }

  return <div className="d"><style>{CSS}</style><div className="app">
    {!(view?.kind === "item" && width < 1000) && <header className="top">
      <button className="logo" onClick={() => goTab("home")} aria-label="Deals, accueil">Deals<b>.</b></button>
      <div className="tabs">{tabsList.map(([k, l, d]) => <button key={k} className={tab === k && !view ? "on" : ""} onClick={() => goTab(k)} aria-label={tabSaid(k, l)}>
        <Icon d={d} size={18} />{l}{badge[k] > 0 && <span className="dot">{badge[k]}</span>}</button>)}</div>
      <button className="ibtn" aria-label={reached ? reachedSaid : "Missions"} onClick={() => goTab("missions")}>
        <Icon d={UI.bell} size={22} />{reached > 0 && <span className="dot">{reached}</span>}</button>
    </header>}
    {error && <div className="empty">{error}</div>}
    {body}
    <nav className="d-nav" aria-label="Navigation">{tabsList.map(([k, l, d]) =>
      <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} onClick={() => goTab(k)} aria-label={tabSaid(k, l)}>
        <span className="ic"><Icon d={d} size={23} fill={tab === k && k !== "search" && k !== "missions"} />
          {badge[k] > 0 && <span className="dot" aria-hidden="true">{badge[k]}</span>}</span>{l}</button>)}</nav>
    {login && <LoginSheet message={login.message} onClose={() => setLogin(null)}
      onDone={() => { setLogin(null); refreshSession(); setVersion(v => v + 1); }} />}
    <Toast text={toast} />
  </div></div>;
}
