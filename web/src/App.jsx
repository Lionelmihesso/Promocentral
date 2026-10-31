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
  user: [C(12, 8.5, 3.8), "M4.8 20c.8-3.6 3.6-5.6 7.2-5.6s6.4 2 7.2 5.6"],
  share: ["M12 15V4.5", "M8 8l4-4 4 4", "M6 12.5V19a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-6.5"],
  cal: ["M5.5 6h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z", "M4.5 10h15", "M8.5 4v4", "M15.5 4v4"],
  next: ["M9.5 5.5L16 12l-6.5 6.5"],
  target: [C(12, 12, 8), C(12, 12, 4.2), "M12 12h.01"],
  minus: ["M6.5 12h11"],
  down: ["M7 10l5 5 5-5"],
  up: ["M12 18.5v-12", "M6.5 12l5.5-5.5 5.5 5.5"],
  bookmark: ["M7.5 4.5h9a1 1 0 0 1 1 1v14.5l-5.5-3.6-5.5 3.6V5.5a1 1 0 0 1 1-1z"],
  sliders: ["M4 7.5h9", "M18.5 7.5H20", C(15.8, 7.5, 2.2), "M4 16.5h2.5", "M11 16.5h9", C(8.7, 16.5, 2.2)],
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
const spanOf = days => days >= 30 ? `${Math.floor(days / 30)} mois` : `${days} jours`;      // « depuis 2 mois » : arrondi en dessous
const FAMILY = { electromenager: "Électroménager", electronique: "Électronique", ameublement: "Ameublement", literie: "Literie" };
// Recherche : des exemples pour démarrer, les filtres (budget maximum, remise minimale) et les tris.
const TRY = ["aspirateur balai sans fil", "TV OLED 55 pouces", "smartphone 5G", "lave-linge 9 kg", "canapé d'angle"];
const BUDGETS = [["", "Tous les budgets"], ["200", "Moins de 200 €"], ["500", "Moins de 500 €"], ["1000", "Moins de 1 000 €"], ["2000", "Moins de 2 000 €"]];
// Promo : un palier de remise, ou un prix parmi les plus bas depuis longtemps (catalog.cheap) ; seuls les choix qui
// donnent quelque chose sont proposés, avec leur nombre de produits.
const OFFS = [["", "Toutes"], ["1", "En promo"], ["10", "−10 % et plus"], ["20", "−20 % et plus"], ["30", "−30 % et plus"],
  ["40", "−40 % et plus"], ["50", "−50 % et plus"], ["low", "Prix parmi les plus bas"]];
const SORTS = [["relevance", "Pertinence"], ["price", "Prix croissant"], ["discount", "Plus forte promo"]];
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

/* Prix proposés pour une alerte : le plus bas des derniers mois s'il est sous le prix du jour, puis −10 % et −20 %. */
function suggestions(p) {
  const out = [], low = p.position?.low;
  if (low != null && low < Math.round(p.price)) out.push([low, "le plus bas"]);
  for (const f of [0.9, 0.8]) { const v = Math.floor(p.price * f); if (!out.some(([x]) => x === v)) out.push([v, `−${Math.round((1 - f) * 100)} %`]); }
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
/* la recherche en une phrase, depuis l'accueil */
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
/* recherche v56 : les critères compris, en puces modifiables ; affiner ; sauvegarder */
.d .fchip.refine{gap:7px;padding:0 14px}
.d .fchip.refine.on{background:var(--tint);border-color:var(--tint);color:var(--ink)}
.d .crit{flex:0 0 auto;display:flex;align-items:center;background:var(--ink);color:#fff;border-radius:999px;min-height:44px}
.d .crit .cl{border:0;background:none;color:inherit;min-height:44px;min-width:44px;padding:0 2px 0 15px;font-size:14.5px;font-weight:700;white-space:nowrap}
.d .crit .cx{border:0;background:none;color:inherit;width:44px;height:44px;display:grid;place-items:center;border-radius:999px;opacity:.85}
.d .savebtn{flex:0 0 auto;display:flex;align-items:center;gap:7px;border:1.5px solid var(--ink);background:var(--paper);border-radius:999px;min-height:44px;padding:0 15px;font-size:14px;font-weight:800}
.d .savebtn.on{background:var(--ink);color:#fff}
.d .savebar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 16px 14px;padding:10px 10px 10px 16px;border-radius:18px;background:var(--tint);font-size:14px;font-weight:700;color:var(--mid)}
.d .ctag em{font-style:normal;font-size:12.5px;font-weight:700;color:var(--mid)}
.d .ctag.on em{color:#D9D7D2}
.d .ctag em.new,.d .st em.new{font-style:normal;background:var(--accent);color:#fff;border-radius:999px;font-size:11px;font-weight:800;padding:2px 7px;line-height:1.3;letter-spacing:.02em}
.d .tryit .saved{margin-bottom:22px}
.d .sheet.refine h3{margin:18px 0 8px}
.d .sheet.refine .ctags .ctag{min-height:44px}
.d .range{display:flex;gap:10px}.d .range .pinput{flex:1;min-width:0;margin-top:0}
.d .sechead > div .n{display:block;margin-top:4px}
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
nav.d-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:520px;display:grid;grid-template-columns:repeat(3,1fr);gap:4px;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid var(--line);z-index:5;padding:6px 8px calc(10px + env(safe-area-inset-bottom))}
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
  .d .profile .psec{margin-top:48px}.d .fold{padding:0}
  .d .profile .sw{margin-left:0;margin-right:0}.d .profile .out > .ghost{padding-left:0;padding-right:0}
  .d .center{max-width:900px}
  .d .brow{margin-left:0;margin-right:0;width:100%;max-width:640px}
  .d .ctags.row{flex-wrap:wrap;margin:0;padding:0}
  .d .mbox{margin-left:0;margin-right:0}
  .d .legal,.d .about{padding-left:0;padding-right:0}
  .d .mbox{padding:26px 28px}.d .mbox .mform{max-width:640px}
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

/* Affiner une recherche : tout ce qu'elle demande, modifiable à tout moment — le rayon, les fonctions et les tailles qui
   existent dans ce rayon (avec leur nombre de produits), la marque, le budget, la promo, le tri. Chaque choix s'applique
   aussitôt ; la feuille dit combien de produits répondent. */
function RefineSheet({ results, base, cats, brands, onEdit, onClose }) {
  const dom = results?.domain?.key || base.domain;          // un domaine à ontologie : le type, puis sans fil, sans sac
  useEscape(onClose);
  const box = useRef(null);
  useEffect(() => { box.current?.focus(); }, []);
  const c = base, opts = results?.options, offs = results?.offs || {};
  const [lo, setLo] = useState(c.min ?? ""), [hi, setHi] = useState(c.max ?? "");
  useEffect(() => { setLo(c.min ?? ""); setHi(c.max ?? ""); }, [c.min, c.max]);
  const num = v => v === "" || v == null ? null : Number(v) >= 1 ? Number(v) : null;
  const chip = (key, label, on, onClick, count) => <button key={key} className={`ctag ${on ? "on" : ""}`} aria-pressed={on} onClick={onClick}
    aria-label={count != null ? `${label}, ${plural(count, "produit")}` : undefined}>{on && <Icon d={UI.check} size={15} sw={2.8} />}{label}
    {count != null && <em>{count}</em>}</button>;
  const brandList = opts ? opts.brands.map(b => ({ name: b.name, count: b.count }))          // dans le rayon ou la pièce, selon la recherche
    : brands.filter(b => b.products > 0).map(b => ({ name: b.name, count: b.products }));
  // Le rayon choisi seul, la liste entière sur demande : ses fonctions et ses tailles viennent juste dessous.
  const [wide, setWide] = useState(!c.category && !c.room && !c.domain);
  const rayons = useRef(null), moved = useRef(false);
  useEffect(() => {
    const box = rayons.current;
    if (moved.current && box) (wide ? box.querySelector(".ctag.on") || box.querySelector(".ctag") : box.querySelector(".ctag.more"))?.focus();
  }, [wide]);
  const none = x => ({ ...x, category: null, room: null, features: [], attrs: {}, domain: null, sub: null, props: {} });
  const pickCat = key => { const was = c.category === key || (inDomain.length === 1 && inDomain[0] === key);
    onEdit(x => was ? none(x) : { ...none(x), category: key }); moved.current = true; setWide(was); };
  const unpick = () => { onEdit(none); moved.current = true; setWide(true); };
  const inDomain = !c.category && c.domain ? results?.domain?.categories || [] : [];   // un rayon dit par la phrase (son domaine)
  const isOn = key => c.category === key || inDomain.includes(key);
  const picked = cats.find(k => k.key === c.category) || (inDomain.length === 1 ? cats.find(k => k.key === inDomain[0]) : null);
  const promos = OFFS.filter(([k]) => k && (offs[k] > 0 || (k === "low" ? c.low : String(c.off || "") === k)));
  const chosenLabel = picked?.label || (c.domain && results?.domain?.label) || results?.chips?.find(x => ["category", "room", "domain", "sub"].includes(x.id))?.label
    || "Rayon choisi";
  return <div className="sheet-wrap" onClick={onClose}>
    <div className="sheet refine" ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="refine-h" onClick={e => e.stopPropagation()}>
      <div className="eyebrow">Recherche</div>
      <h2 id="refine-h">Affiner</h2>
      <h3>Rayon</h3>
      <div className="ctags" ref={rayons}>{wide ? <>{chip("all", "Tous", !c.category && !c.room && !c.domain, unpick)}
        {cats.map(k => chip(k.key, k.label, isOn(k.key), () => pickCat(k.key), k.products))}</>
        : <>{chip("chosen", chosenLabel, true, unpick, picked?.products)}
          <button className="ctag more" aria-expanded="false" onClick={() => { moved.current = true; setWide(true); }}>Changer de rayon
            <Icon d={UI.down} size={15} sw={2.4} /></button></>}</div>
      {opts?.subs?.length > 0 && <><h3>Type</h3>
        <div className="ctags">{opts.subs.map(t => chip(t.key, t.label, c.sub === t.key, () => onEdit(x => ({ ...x, domain: x.domain || dom,
          sub: x.sub === t.key ? null : t.key })), t.count))}</div></>}
      {opts?.props?.length > 0 && <><h3>Caractéristiques</h3>
        <div className="ctags">{opts.props.map(p => chip(`${p.key}:${p.value}`, p.label, c.props[p.key] === p.value, () => onEdit(x => {
          const props = { ...x.props };
          if (props[p.key] === p.value) delete props[p.key]; else props[p.key] = p.value;
          return { ...x, domain: x.domain || dom, props };
        }), p.count))}</div></>}
      {opts?.features?.length > 0 && <><h3>Fonctions</h3>
        <div className="ctags">{opts.features.map(f => chip(f.key, f.label, c.features.includes(f.key), () => onEdit(x => ({ ...x,
          features: x.features.includes(f.key) ? x.features.filter(y => y !== f.key) : [...x.features, f.key] })), f.count))}</div></>}
      {opts && Object.entries(opts.attrs).map(([k, a]) => <div key={k}><h3>{a.title}</h3>
        <div className="ctags">{a.values.map(v => chip(String(v.value), v.label, c.attrs[k] === v.value, () => onEdit(x => {
          const attrs = { ...x.attrs };
          if (attrs[k] === v.value) delete attrs[k]; else attrs[k] = v.value;
          return { ...x, attrs };
        }), v.count))}</div></div>)}
      {brandList.length > 0 && <><h3>Marque</h3>
        <div className="ctags">{brandList.slice(0, 16).map(b => chip(b.name, b.name, c.brand === b.name,
          () => onEdit(x => ({ ...x, brand: x.brand === b.name ? null : b.name })), b.count))}</div></>}
      <h3>Budget</h3>
      <div className="range">
        <label className="pinput"><span>De</span><input type="number" inputMode="numeric" min="1" value={lo} placeholder="—" aria-label="Prix minimum, en euros"
          onChange={e => setLo(e.target.value)} onBlur={() => onEdit(x => ({ ...x, min: num(lo) }))} /><b>€</b></label>
        <label className="pinput"><span>À</span><input type="number" inputMode="numeric" min="1" value={hi} placeholder="—" aria-label="Prix maximum, en euros"
          onChange={e => setHi(e.target.value)} onBlur={() => onEdit(x => ({ ...x, max: num(hi) }))} /><b>€</b></label>
      </div>
      <div className="ctags" style={{ marginTop: 10 }}>{BUDGETS.filter(([v]) => v).map(([v, l]) => chip(v, l, c.max === Number(v) && c.min == null,
        () => onEdit(x => ({ ...x, min: null, max: x.max === Number(v) && x.min == null ? null : Number(v) }))))}</div>
      {promos.length > 0 && <><h3>Promo</h3>
        <div className="ctags">{promos.map(([k, l]) => {
          const on = k === "low" ? c.low : String(c.off || "") === k;
          return chip(k, l, on, () => onEdit(x => k === "low" ? { ...x, low: !x.low } : { ...x, off: on ? null : Number(k) }), offs[k] ?? 0);
        })}</div></>}
      <h3>Trier</h3>
      <div className="ctags">{SORTS.map(([k, l]) => chip(k, l, (c.sort || "relevance") === k, () => onEdit(x => ({ ...x, sort: k === "relevance" ? null : k }))))}</div>
      <button className="cta" onClick={onClose}>{results ? `Voir ${plural(results.total, "produit")}` : "Voir les produits"}</button>
      <button className="ghost" onClick={() => { onEdit(() => ({ ...NO_CRIT }), []); onClose(); }}>Tout effacer</button>
    </div>
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
    {range > 0 && <div className="gauge" role="img" aria-label={`Depuis ${span}, de ${eur(pos.low)} à ${eur(pos.high)} ; aujourd'hui ${eur(price)}`}>
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
  const [view, setView] = useState(null);          // null | item | brand | category | room | about — chacune garde `from` (« Retour »)
  const [q, setQ] = useState("");                  // Recherche : la phrase tapée
  const [crit, setCrit] = useState(NO_CRIT);       // Recherche : les critères choisis dans l'app (puces, Affiner), qui l'emportent
  const [all, setAll] = useState(null);            // remises du jour (bandeau, notre sélection)
  const [top, setTop] = useState(null);            // top deals (accueil, en premier)
  const [allCats, setAllCats] = useState([]);      // toutes les catégories (count : remises du jour)
  const [allBrands, setAllBrands] = useState([]);  // toutes les marques (count : remises du jour)
  const [picking, setPicking] = useState(null);    // feuille ouverte : category | budget | off | refine | brands
  const [results, setResults] = useState(null);    // Recherche : la réponse (produits, critères compris, puces)
  const [searching, setSearching] = useState(false);  // une réponse est attendue : les résultats montrés pâlissent
  const [feed, setFeed] = useState(null);          // Recherche : le feed d'avant toute saisie
  const [recent, setRecent] = useState(() => recents.get());
  const [seen, setSeen] = useState([]);            // fiches ouvertes et clics de la visite (le serveur n'en garde rien)
  const [you, setYou] = useState(null);            // accueil : « pour vous »
  const [taste, setTaste] = useState(null);        // Profil : ce que l'app retient et a compris
  const [guestVariant] = useState(() => Math.random() < 0.1 ? "t" : "p"); // sans compte : une visite sur dix est témoin
  const seq = useRef(0);                           // seule la réponse à la dernière saisie compte
  const [order, setOrder] = useState("pct");       // pages marque et catégorie : pct | asc | desc
  const [list, setList] = useState(null);          // pièce
  const [item, setItem] = useState(null);
  const [brandPage, setBrandPage] = useState(null);
  const [catPage, setCatPage] = useState(null);
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

  useEffect(() => {                                                         // accueil : top deals, pour vous, sélection — selon vos goûts
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
    if (view.kind === "brand") api(`brand/${encodeURIComponent(view.name)}`).then(setBrandPage).catch(() => setError("Marque introuvable."));
    if (view.kind === "category") api(`category/${view.key}`).then(setCatPage).catch(() => setError("Catégorie introuvable."));
    if (view.kind === "room") api(`today?category=${view.room.cats.join(",")}`).then(setList).catch(() => setError("Pièce introuvable."));
  }, [view, version]);

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
  const goTab = t => { setView(null); setItem(null); setBrandPage(null); setCatPage(null); setList(null); setTab(t); setQ("");
    setCrit(NO_CRIT); if (t === tab && !view) window.scrollTo(0, 0); };   // l'onglet déjà ouvert : en haut
  // Chaque vue garde celle d'où l'on vient : « Retour » y ramène. via : d'où vient la fiche (mesure des clics sortants).
  const open = (id, via, mission) => { if (via === "search") remember(intent); setItem(null); setView(v => ({ kind: "item", id, via, mission, from: v })); };
  const openAbout = () => setView(v => ({ kind: "about", from: v }));
  const openBrand = name => { setBrandPage(null); setOrder("pct"); setView(v => ({ kind: "brand", name, from: v })); };
  const openCategory = key => { setCatPage(null); setOrder("pct"); setView(v => ({ kind: "category", key, from: v })); };
  const openRoom = room => { setList(null); setView(v => ({ kind: "room", room, from: v })); };
  const goBack = () => { setItem(null); setBrandPage(null); setCatPage(null); setList(null); setView(view?.from || null); };
  const search = text => { goTab("search"); setQ(text); };              // depuis l'accueil : la phrase va dans la Recherche

  // Ce que la phrase dit (said, lu par le serveur pour cette phrase-là), complété par ce qui a été choisi dans l'app, qui
  // l'emporte (même règle que catalog.search). Quand on touche une puce, la phrase devient des critères de l'app et le
  // champ ne garde que les mots qui restent : rien n'est compris deux fois. Chaque geste part du dernier état voulu, sans
  // attendre la réponse du précédent.
  const phraseSaid = results && results._q === q.trim() && q.trim() ? results.said : null;
  const merged = (s, c) => !s ? c : { category: c.category || (c.domain ? null : s.category) || null,
    room: c.category || c.domain ? null : c.room || s.room || null,
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
  const clearAll = () => { setCrit(NO_CRIT); setQ(""); };

  // Vos recherches sauvegardées (des missions : Deals les surveille ; le prix est facultatif).
  const sig = m => JSON.stringify([m.category || null, m.room || null, m.brand || null, [...(m.features || [])].sort(),
    Object.entries(m.attrs || {}).sort(), m.min_price ?? null, m.max_price ?? null, m.off || null, !!m.low, [...(m.words || [])],
    m.domain || null, m.sub || null, Object.entries(m.props || {}).sort()]);
  const current = results?.criteria ? { ...results.criteria, words: results.words || [] } : null;
  const searches = (missions?.missions || []).filter(m => !m.product_id);
  const savedMatch = current && searches.find(m => sig(m) === sig(current));
  const saveSearch = async () => {
    if (savedMatch) { await dropSaved(savedMatch); return; }
    const c = current;
    try {
      const made = await keep("missions", { category: c.category, room: c.room, brand: c.brand, features: c.features, attrs: c.attrs,
        min_price: c.min_price, max_price: c.max_price, off: c.off, low: c.low, words: c.words,
        domain: c.domain, sub: c.sub, props: c.props });
      setMissions(x => ({ reached: 0, fresh: 0, ...x, missions: [made, ...(x?.missions || []).filter(m => m.id !== made.id)] }));   // « Sauvegardée » aussitôt
      remember(intent); setVersion(v => v + 1);
      flash(c.max_price != null ? "Sauvegardée : on vous prévient sous votre prix" : "Recherche sauvegardée dans votre Profil");
    } catch (ex) { flash(ex.message); }
  };
  const dropSaved = async m => {
    setMissions(x => x && { ...x, missions: x.missions.filter(y => y.id !== m.id) });
    try { await api("missions/delete", { id: m.id }); flash(m.product_id ? "Alerte arrêtée" : "Recherche retirée"); } catch { /* relue ensuite */ }
    setVersion(v => v + 1);
  };
  const openSaved = m => {
    if (m.product_id) open(m.product_id, "mission", m.id);
    else {
      setView(null); setItem(null); setTab("search"); setQ((m.words || []).join(" "));
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
    <input value={q} onChange={e => setQ(e.target.value)} placeholder="« aspirateur balai sous 300 € », une marque…" aria-label="Rechercher" enterKeyHint="search" />
    {q && <button type="button" className="sx" aria-label="Effacer le texte" onClick={() => setQ("")}><Icon d={UI.x} size={18} /></button>}</label></form>;
  const back = <button className="back" onClick={goBack}><Icon d={UI.back} size={18} sw={2.2} />Retour</button>;
  const tabsList = [["home", "Accueil", UI.home], ["search", "Recherche", UI.search], ["me", "Profil", UI.user]];   // vos recherches et missions sont dans le Profil
  const fresh = missions?.fresh || 0;
  const badge = { me: fresh + drops };
  const freshSaid = fresh > 1 ? `${fresh} recherches avec du nouveau` : fresh === 1 ? "1 recherche avec du nouveau" : "";
  const tabSaid = (k, l) => k === "me" && badge.me ? `${l}, ${[freshSaid, drops ? `${plural(drops, "baisse")} de prix sur vos favoris` : ""].filter(Boolean).join(", ")}` : undefined;
  const entry = <form className="mbox feed" onSubmit={e => { e.preventDefault(); const t = e.currentTarget.querySelector("input").value; if (t.trim()) search(t); }}>
    <div className="k"><i />RECHERCHE</div>
    <h2>Une envie précise ?</h2><p>Dites-la comme vous la pensez, avec votre prix : on vous montre ce qui y répond, et on surveille pour vous.</p>
    <div className="mform">
      <input placeholder="aspirateur balai sous 300 €" aria-label="Votre envie en une phrase" enterKeyHint="search" />
      <button aria-label="Chercher"><Icon d={UI.next} size={22} sw={2.4} /></button></div>
  </form>;
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
  const ordered = items => order === "pct" ? items : [...items].sort((a, b) => order === "asc" ? a.price - b.price : b.price - a.price);
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
  if (view?.kind === "about") {                    // référencement, classement, rémunération : ce que la loi demande de dire
    body = <div className="about">
      {back}
      <h1>Comment ça marche</h1>
      <p className="lead">Deals repère chaque jour les bonnes affaires d'électroménager, d'électronique, d'ameublement et de literie, et vous dit si
        c'est le bon moment d'acheter.</p>
      <h2>Quelles offres ?</h2>
      <p>Uniquement celles de nos enseignes partenaires. Leurs prix sont relus chaque nuit ; un prix qui n'a pas été relu depuis
        trois jours n'est plus montré. Une remise n'est affichée que si elle est réelle : nous la comparons aux prix des mois
        précédents et au « prix le plus bas des 30 derniers jours » que l'enseigne doit indiquer ; une remise exagérée n'est
        pas affichée.</p>
      <h2>Dans quel ordre ?</h2>
      <ul>
        <li><b>Accueil, top deals</b> : les plus fortes remises réelles et les produits dont le prix est parmi les plus bas depuis
          au moins deux mois (au moins 10 % sous leur prix habituel), à tour de rôle. <b>Pour vous</b> : les remises et les prix
          bas de vos rayons et de vos marques. <b>Notre sélection</b> : les autres remises, les plus fortes d'abord.</li>
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
          propose.</li>
        <li><b>Moins cher, comparable</b> : sur la fiche, des produits du même type, de la même taille (un téléviseur 55 pouces,
          un autre 55 pouces), qui ont au moins ce que le produit a (4K, 5G, réduction de bruit, autant de stockage) et coûtent au
          moins 10 % de moins.</li>
        <li><b>Marque, catégorie</b> : les remises d'abord, ou le tri que vous choisissez.</li>
        <li><b>Fiche</b> : l'offre la moins chère parmi nos partenaires.</li>
      </ul>
      <h2>Comment Deals est rémunéré ?</h2>
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
          <PricePosition pos={item.position} price={item.price} />
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
    const on = picks.includes(catPage.key);
    body = <>
      {back}
      <div className="pagehead"><div><h1>{catPage.label}</h1>
        <div className="sub">{catPage.deals ? `${plural(catPage.deals, "remise")} aujourd'hui · ` : ""}{plural(catPage.products.length, "produit")}</div></div>
        <button className={`pill ${on ? "on" : ""}`} onClick={() => togglePick(catPage.key)} aria-pressed={on}>
          <Icon d={on ? UI.check : UI.plus} size={17} sw={2.4} />{on ? "Dans vos rayons" : "Mes rayons"}</button></div>
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
      {list && grid(list.products, "room")}
      {list && list.total === 0 && <div className="empty">Aucune remise dans cette pièce aujourd'hui.</div>}
    </>;
  } else if (tab === "home") {                    // éditorial : des pièces, des marques, une sélection ; chercher, c'est l'onglet Recherche
    const items = all?.products || [];
    const tops = top?.products || [], inTop = new Set(tops.map(p => p.id));
    const yours = (you?.products || []).filter(p => !inTop.has(p.id));   // pour vous : sans répéter les top deals
    const shown = new Set([...inTop, ...yours.map(p => p.id)]);
    const rest = items.filter(p => !shown.has(p.id));              // notre sélection : sans répéter ce qui est au-dessus
    body = <>
      <Ticker items={items} publishedAt={all?.published_at} />
      <div className="intro"><h1>De bonnes affaires, pour vos envies.</h1></div>
      {tops.length > 0 && <>
        <div className="sechead"><h2>Top deals</h2><span className="n">Remises et prix bas</span></div>
        <div className="scroller tops">{tops.map(card("top"))}</div>
      </>}
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
      {grid(rest.slice(0, cols * 2), "home")}{/* la recherche en une phrase, après deux rangées de remises */}
      {all && entry}
      {rest.length > cols * 2 && <div style={{ height: 18 }} />}
      {grid(rest.slice(cols * 2), "home")}
    </>;
  } else if (tab === "search") {                  // une phrase comprise, des critères modifiables, un feed que chaque saisie adapte
    const term = q.trim(), t = norm(term), any = term || hasCrit(crit);
    const shownRes = any ? results : null;
    const chips = shownRes?.chips || [];
    const brandHit = t.length >= 2 && !hasCrit(crit) ? allBrands.find(b => norm(b.name) === t) || allBrands.find(b => norm(b.name).startsWith(t)) : null;
    const offs = (shownRes || feed)?.offs || {};
    const base = applied();
    const catOptions = (shownRes && term ? shownRes.categories : allCats.map(c => ({ key: c.key, label: c.label, count: c.products })))
      .slice().sort((a, b) => a.label.localeCompare(b.label, "fr"));
    const sheets = {
      category: ["Catégorie", [["", "Toutes les catégories"], ...catOptions.map(c => [c.key, c.label, c.count])], base.category || "",
        v => edit(c => ({ ...c, category: v || null, room: null, features: [], attrs: {} }))],
      budget: ["Budget", BUDGETS, base.max != null ? String(base.max) : "", v => edit(c => ({ ...c, min: null, max: v ? Number(v) : null }))],
      off: ["Promo", OFFS.filter(([k]) => !k || offs[k] > 0).map(([k, l]) => k ? [k, l, offs[k] ?? 0] : [k, l]), base.low ? "low" : String(base.off || ""),
        v => edit(c => ({ ...c, off: v && v !== "low" ? Number(v) : null, low: v === "low" }))],
    };
    const quick = (key, name) => <button key={key} className="fchip" onClick={() => setPicking(key)} aria-haspopup="dialog">{name}<Icon d={UI.down} size={15} sw={2.4} /></button>;
    const mine = feed?.recent?.length > 0 || feed?.personal;   // le feed suit vos dernières recherches, vos goûts
    const feedHead = <div className="sechead"><h2>{mine ? "Pour vous" : "À découvrir"}</h2>
      <span className="n">{feed?.recent?.length > 0 ? "D'après vos recherches" : mine ? "D'après vos goûts" : feed ? plural(feed.total, "produit") : ""}</span></div>;
    const saveBtn = (label, cls = "") => <button className={`savebtn ${savedMatch ? "on" : ""} ${cls}`} aria-pressed={!!savedMatch} onClick={saveSearch}>
      <Icon d={UI.bookmark} size={17} sw={2.2} fill={!!savedMatch} />{savedMatch ? "Sauvegardée" : label}</button>;
    body = <>
      <div className="pagehead"><h1>Recherche</h1></div>
      {searchBar}
      <div className="filters" role="group" aria-label="Critères de la recherche">
        <button className={`fchip refine ${chips.length ? "on" : ""}`} onClick={() => setPicking("refine")} aria-haspopup="dialog">
          <Icon d={UI.sliders} size={16} sw={2.2} />Affiner</button>
        {chips.length ? chips.map(c => <span key={c.id} className="crit">
          <button className="cl" onClick={() => setPicking("refine")} aria-label={`${c.label} : modifier`}>{c.label}</button>
          <button className="cx" onClick={() => dropChip(c.id)} aria-label={`Retirer ${c.label}`}><Icon d={UI.x} size={14} sw={2.6} /></button></span>)
          : <>{quick("category", "Catégorie")}{quick("budget", "Budget")}{quick("off", "Promo")}</>}
        {chips.length > 0 && <button className="fchip clear" onClick={clearAll}><Icon d={UI.x} size={15} sw={2.4} />Tout effacer</button>}
      </div>
      {!any && <div className="tryit">
        {searches.length > 0 && <div className="saved">
          <div className="th"><h3>Vos recherches sauvegardées</h3><button className="forget" onClick={() => goTab("me")}>Tout voir</button></div>
          <div className="ctags row">{searches.map(m => <button key={m.id} className="ctag" onClick={() => openSaved(m)}
            aria-label={`${m.title}${m.fresh ? `, ${m.fresh > 1 ? `${m.fresh} nouveaux` : "1 nouveau"}` : ""}`}>
            <Icon d={UI.bookmark} size={15} sw={2.2} />{m.title}{m.fresh > 0 && <em className="new">{m.fresh}</em>}</button>)}</div></div>}
        {recent.length > 0
          ? <><div className="th"><h3>Vos recherches récentes</h3><button className="forget" onClick={forget} aria-label="Effacer vos recherches">Effacer</button></div>
            <div className="ctags row">{recent.map(x => <button key={x} className="ctag" onClick={() => { setQ(x); remember(x); }}>{x}</button>)}</div></>
          : searches.length === 0 && <><h3>Essayez</h3>
            <div className="ctags row">{TRY.map(x => <button key={x} className="ctag" onClick={() => { setQ(x); remember(x); }}>{x}</button>)}</div></>}
      </div>}
      {!any || !shownRes ? <>{feedHead}<div className={`flow ${any ? "dim" : ""}`}>{grid(feed?.products || [], "feed")}</div></>
        : shownRes.unsupported ? <>
          <div className="sechead"><h2>Les {shownRes.unsupported.toLowerCase()} ne sont pas encore suivis</h2></div>
          <p className="note">Électroménager, électronique, ameublement et literie seulement, pour l'instant.</p>
          {feedHead}{grid(feed?.products || [], "feed")}
        </> : shownRes.total === 0 ? <>{/* rien trouvé : on le dit, on propose de sauvegarder, et le feed reste là */}
          <div className="sechead"><h2>{term && chips.every(c => c.id.startsWith("word:")) ? `Rien pour « ${term} »` : "Rien pour cette recherche"}</h2></div>
          {chips.length > 0 && <div className="savebar"><span>Pas encore là ? On surveille pour vous.</span>{saveBtn("Sauvegarder")}</div>}
          {feedHead}{grid(feed?.products || [], "feed")}
        </> : <>
        {brandHit && <button className="brow" onClick={() => openBrand(brandHit.name)} aria-label={`La marque ${brandHit.name}`}>
          <small>Marque</small><b>{brandHit.name}</b><span>{plural(brandHit.products, "produit")}</span><Icon d={UI.next} size={18} sw={2.2} /></button>}
        {shownRes.relaxed ? <>
          <div className="sechead"><div><h2>Rien à moins de {eur(shownRes.relaxed.max_price)}</h2>
            <span className="n">Les plus proches, dès {eur(shownRes.relaxed.from)}</span></div></div>
          <div className="savebar"><span>On vous prévient dès qu'un produit passe sous {eur(shownRes.relaxed.max_price)}.</span>{saveBtn("Me prévenir")}</div>
        </> : <div className="sechead"><h2>{plural(shownRes.total, "produit")}</h2>{saveBtn("Sauvegarder")}</div>}
        {shownRes.ignored?.length > 0 && <p className="note">« {shownRes.ignored.join(" ")} » : aucun produit ; voici le reste de votre recherche.</p>}
        <div className={`flow ${searching ? "dim" : ""}`}>{grid(shownRes.products, "search")}</div>
      </>}
      {picking && sheets[picking] && <ChoiceSheet title={sheets[picking][0]} options={sheets[picking][1]} value={sheets[picking][2]} onPick={sheets[picking][3]}
        onClose={() => setPicking(null)} />}
      {picking === "refine" && <RefineSheet results={shownRes} base={base} cats={pickable} brands={allBrands} onEdit={edit} onClose={() => setPicking(null)} />}
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
      <button className="logo" onClick={() => goTab("home")} aria-label="Deals, accueil">Deals<b>.</b></button>
      <div className="tabs">{tabsList.map(([k, l, d]) => <button key={k} className={tab === k && !view ? "on" : ""} onClick={() => goTab(k)} aria-label={tabSaid(k, l)}>
        <Icon d={d} size={18} />{l}{badge[k] > 0 && <span className="dot">{badge[k]}</span>}</button>)}</div>
      <button className="ibtn" aria-label={fresh ? freshSaid : "Vos recherches"} onClick={() => goTab("me")}>
        <Icon d={UI.bell} size={22} />{fresh > 0 && <span className="dot">{fresh}</span>}</button>
    </header>}
    {error && <div className="empty">{error}</div>}
    {body}
    {view?.kind !== "about" && <footer className="legal">Offres d'enseignes partenaires, remises vérifiées.{" "}
      <button className="lnk" onClick={openAbout}>Comment ça marche</button></footer>}
    <nav className="d-nav" aria-label="Navigation">{tabsList.map(([k, l, d]) =>
      <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} onClick={() => goTab(k)} aria-label={tabSaid(k, l)}>
        <span className="ic"><Icon d={d} size={23} fill={tab === k && k !== "search"} />
          {badge[k] > 0 && <span className="dot" aria-hidden="true">{badge[k]}</span>}</span>{l}</button>)}</nav>
    {emailFor && <EmailSheet reason={emailFor} onClose={() => setEmailFor(null)}
      onDone={() => { setEmailFor(null); refreshSession(); setVersion(v => v + 1); }} />}
    <Toast text={toast} />
  </div></div>;
}
