/* DEALS — application grand public, branchée sur /api/r/. Interface v47 : un flux vivant de remises, à la croisée d'un
   Pinterest (des visuels, une mosaïque, l'inspiration par pièce) et d'un Bloomberg (un bandeau qui défile, l'heure de
   mise à jour, la courbe du prix sur 90 jours, « au plus bas depuis 90 jours »).

   Les visuels sont des illustrations originales par catégorie (art.jsx) : aucune image extérieure, aucune requête vers un
   tiers, aucun droit de tiers. Gardé des versions précédentes : le produit comme entrée, un deal identique pour tous, des
   remises réelles seulement (la qualité est implicite), les durées dans la fiche seulement, « Moins cher, comparable »,
   la recherche dans tout le catalogue, la connexion au moment de l'action, contrastes et zones à toucher aux normes. */
import { useState, useEffect } from "react";
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
  sliders: ["M4 7h9", "M17 7h3", C(15, 7, 2), "M4 17h3", "M11 17h9", C(9, 17, 2)],
  share: ["M12 15V4.5", "M8 8l4-4 4 4", "M6 12.5V19a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-6.5"],
  cal: ["M5.5 6h13a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z", "M4.5 10h15", "M8.5 4v4", "M15.5 4v4"],
  next: ["M9.5 5.5L16 12l-6.5 6.5"],
  ruler: ["M3.5 15.5l12-12 5 5-12 12z", "M8 11l1.6 1.6", "M10.6 8.4l1.6 1.6", "M13.2 5.8l1.6 1.6"],
  bolt: ["M13 3.5L6 13.5h5l-1 7 7-10h-5z"],
  weight: ["M7 8.5h10l2 11.5H5z", C(12, 6, 2.3)],
  plate: [C(12, 12, 7.5), C(12, 12, 4)],
  sound: ["M4.5 9.5h3l4-3.5v12l-4-3.5h-3z", "M15 9a4 4 0 0 1 0 6", "M17.5 6.5a7.5 7.5 0 0 1 0 11"],
  battery: ["M4.5 8h13a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z", "M20.5 10.5v3", "M6.5 10.5v3", "M9.5 10.5v3"],
  box: ["M4.5 7.5L12 4l7.5 3.5v9L12 20l-7.5-3.5z", "M4.5 7.5L12 11l7.5-3.5", "M12 11v9"],
  flame: ["M12 20.5c-3.6 0-6-2.4-6-5.6 0-3.9 3.6-5.7 4.4-10.4 2.6 1.9 3.3 4.3 3 6.2 1-.7 1.8-1.9 2-3 1.7 1.8 2.6 4.3 2.6 6.9 0 3.4-2.4 5.9-6 5.9z"],
  seat: ["M6.5 11V7.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2V11", "M4.5 13a2 2 0 0 1 4 0v1.5h7V13a2 2 0 0 1 4 0v4.5h-15z", "M6.5 17.5v2", "M17.5 17.5v2"],
};
const Icon = ({ d, size = 20, sw = 1.8, fill }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className="i"
  fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
  {d.map((p, i) => <path key={i} d={p} />)}{fill && <path d={d[0]} fill="currentColor" stroke="none" />}</svg>;
const specIcon = s => /×|^Largeur/.test(s) ? UI.ruler : /^Classe/.test(s) ? UI.bolt : /kg$/.test(s) ? UI.weight : /couverts/.test(s) ? UI.plate
  : /dB$/.test(s) ? UI.sound : /^Autonomie/.test(s) ? UI.battery : / L$/.test(s) ? UI.box : /foyers/.test(s) ? UI.flame
  : /places/.test(s) ? UI.seat : UI.check;

/* ---------------------------------------------------------------- formats */
const eur = n => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " €";
const iso = d => new Date(`${d}T12:00:00`);
const dayLabel = d => new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short" }).format(iso(d));
const daysBetween = (a, b) => Math.round((iso(b) - iso(a)) / 86400000);
const clock = ts => new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(new Date(ts * 1000));
const shortDay = ts => new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" }).format(new Date(ts * 1000));
const FAMILY = { electromenager: "Électroménager", ameublement: "Ameublement", literie: "Literie" };
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

const withOut = (set, id) => { const n = new Set(set); n.delete(id); return n; };
const withIn = (set, id) => { const n = new Set(set); n.add(id); return n; };
const useWidth = () => {
  const [w, setW] = useState(typeof window === "undefined" ? 390 : window.innerWidth);
  useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener("resize", f); return () => window.removeEventListener("resize", f); }, []);
  return w;
};

const CSS = `
.d{--ink:#141414;--paper:#FFFFFF;--tint:#F4F2EF;--tint2:#EAE7E2;--mid:#5E6166;--soft:#6B6E73;--icon:#8A8D92;--line:#ECE9E4;
  --accent:#D63A0D;--accent-soft:#FCEDE6;--good:#1F7A52;--terminal:#121315;
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
.d .ibtn{position:relative;border:0;background:none;width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center}
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
@media (prefers-reduced-motion:reduce){.d .run{animation:none}.d .tape{overflow-x:auto}}
/* titres */
.d .intro{padding:18px 16px 0}
.d h1{font-family:var(--serif);font-weight:400;font-size:42px;line-height:1;letter-spacing:-.015em;margin:0}
.d .intro p{margin:10px 0 0;color:var(--mid);font-size:15px;line-height:1.45}
.d .intro p b{color:var(--ink)}
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
.d .rooms{display:flex;gap:10px;overflow-x:auto;padding:0 16px 4px;scroll-snap-type:x mandatory;scrollbar-width:none}
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
.d .info .brand{font-size:12px;font-weight:800;color:var(--mid);text-transform:uppercase;letter-spacing:.09em}
.d .info .title{font-family:inherit;font-size:21px;font-weight:700;letter-spacing:-.02em;line-height:1.2;margin:4px 0 0}
.d .prices{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 14px;margin-top:12px}
.d .prices .pct{font-size:46px;font-weight:800;letter-spacing:-.05em;color:var(--accent);line-height:1}
.d .prices .now{font-size:34px;font-weight:800;letter-spacing:-.04em;line-height:1}
.d .prices s{font-size:17px;color:var(--mid)}
.d .when{display:flex;align-items:center;gap:10px;margin-top:14px;background:var(--accent-soft);border-radius:14px;padding:12px 14px;font-size:14px;font-weight:600}
.d .when .i{color:var(--accent)}
.d .buy{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:14px;min-height:54px;border-radius:15px;background:var(--ink);color:#fff;font-size:16px;font-weight:800;text-decoration:none}
.d .chart{padding:0 16px}
.d .chart svg{display:block;width:100%;height:auto}
.d .verdict{font-size:15px;font-weight:700;margin:0 0 10px}
.d .verdict.low{color:var(--good)}
.d .legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:8px;font-family:var(--mono);font-size:12px;color:var(--mid)}
.d .legend b{color:var(--ink);font-weight:700}
.d .about{padding:0 16px}
.d .about p{margin:0;font-size:15.5px;line-height:1.45}
.d .specs{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.d .specs li{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:8px 14px 8px 11px;font-size:14px;font-weight:600}
.d .specs li .i{color:var(--mid)}
.d .offers{padding:0 16px}
.d .offer{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}
.d .offer:first-child{border-top:1px solid var(--line)}
.d .offer .m{font-size:16px;font-weight:700;letter-spacing:-.01em}
.d .offer .e{font-size:12.5px;color:var(--mid);margin-top:2px;font-weight:700}
.d .offer .r{display:flex;align-items:center;gap:12px}
.d .offer .r b{font-size:18px;font-weight:800;letter-spacing:-.03em}
.d .offer .go{display:flex;align-items:center;gap:4px;min-height:44px;border:0;background:var(--tint);border-radius:12px;padding:0 14px;font-size:13.5px;font-weight:800;text-decoration:none;color:var(--ink)}
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
.d .toast{position:fixed;bottom:104px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 18px;border-radius:999px;font-size:14px;font-weight:700;z-index:11;white-space:nowrap}
nav.d-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:520px;display:grid;grid-template-columns:repeat(4,1fr);gap:4px;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid var(--line);z-index:5;padding:6px 8px calc(10px + env(safe-area-inset-bottom))}
.d-nav button{position:relative;border:0;background:none;min-height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;font-size:12px;font-weight:700;color:var(--soft);border-radius:16px}
.d-nav button.on{color:var(--ink);font-weight:800}
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
  .d .chips,.d .rooms,.d .masonry,.d .scroller,.d .bchips,.d .about,.d .offers,.d .chart,.d .me{padding-left:0;padding-right:0}
  .d h1{font-size:64px}
  .d .intro p{font-size:17px;max-width:640px}
  .d .room{width:228px;height:292px}
  .d .masonry{gap:20px}
  .d .item{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:44px;align-items:start;padding-top:8px}
  .d .item .hero{position:sticky;top:96px;border-radius:24px;overflow:hidden}
  .d .item .hero .vis{max-height:none}
  .d .item .info{padding-left:0;padding-right:0;padding-top:0}
  .d .sheet-wrap{align-items:center}.d .sheet{border-radius:26px}
}
@media (hover:hover){.d .card:hover .vis{filter:brightness(.97)}.d .chips button:hover{background:var(--tint2)}.d .chips button.on:hover{background:var(--ink)}}
`;

function Toast({ text }) {
  return text ? <div className="toast" role="status">{text}</div> : null;
}

function LoginSheet({ message, onClose, onDone }) {
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

/* Courbe du prix sur 90 jours : le prix du jour face au plus bas et au prix habituel (médiane) relevés. */
function PriceChart({ history, price }) {
  const pts = (history?.p || []).map((v, i) => [i, v]).filter(([, v]) => v != null);
  if (pts.length < 2) return null;
  const vals = pts.map(([, v]) => v), low = Math.min(...vals), high = Math.max(...vals);
  const sorted = [...vals].sort((a, b) => a - b), usual = sorted[Math.floor(sorted.length / 2)];
  const W = 360, H = 140, top = 16, bottom = 34, n = history.p.length;
  const x = i => 4 + (i / (n - 1)) * (W - 8);
  const y = v => high === low ? (H - bottom + top) / 2 : top + (1 - (v - low) / (high - low)) * (H - top - bottom);
  let d = "", prev = -2;                                    // en marches : un prix par jour, le changement se voit d'un jour à l'autre
  for (const [i, v] of pts) { d += i === prev + 1 ? `H${x(i).toFixed(1)}V${y(v).toFixed(1)}` : `M${x(i).toFixed(1)} ${y(v).toFixed(1)}`; prev = i; }
  const last = pts[pts.length - 1], lowAt = pts.find(([, v]) => v === low), today = Math.round(price);
  const verdict = today <= low ? "Au plus bas depuis 90 jours" : `${eur(today - low)} au-dessus du plus bas des 90 jours`;
  return <div className="chart">
    <p className={`verdict ${today <= low ? "low" : ""}`}>{verdict}</p>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Prix sur 90 jours : plus bas ${eur(low)}, habituel ${eur(usual)}, aujourd'hui ${eur(price)}`}>
      <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#D63A0D" stopOpacity=".16" /><stop offset="1" stopColor="#D63A0D" stopOpacity="0" /></linearGradient></defs>
      <path d={`M4 ${y(usual)}H${W - 4}`} stroke="#9AA0A6" strokeWidth="1" strokeDasharray="4 4" />
      <path d={`${d}V${H - bottom + 10}H${x(pts[0][0])}Z`} fill="url(#area)" />
      <path d={d} fill="none" stroke="#D63A0D" strokeWidth="2" strokeLinejoin="round" />
      <circle cx={x(lowAt[0])} cy={y(low)} r="3.5" fill="#fff" stroke="#1F7A52" strokeWidth="2" />
      <circle cx={x(last[0])} cy={y(last[1])} r="4.5" fill="#D63A0D" stroke="#fff" strokeWidth="2" />
      <path d={`M4 ${H - bottom + 10}H${W - 4}`} stroke="#E3E0DA" strokeWidth="1" />
      <text x="4" y={H - 6} fontFamily="JetBrains Mono, monospace" fontSize="10.5" fill="#6B6E73">{dayLabel(history.from)}</text>
      <text x={W - 4} y={H - 6} textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="10.5" fill="#6B6E73">aujourd'hui</text>
    </svg>
    <div className="legend"><span>Aujourd'hui <b>{eur(price)}</b></span><span>Plus bas <b>{eur(low)}</b></span><span>Habituel <b>{eur(usual)}</b></span></div>
  </div>;
}

export default function App() {
  const [tab, setTab] = useState("home");
  const [view, setView] = useState(null);          // null | item | brand | room — chacune garde `from` (« Retour »)
  const [family, setFamily] = useState("");        // univers choisi sur l'accueil ; "" = pour vous
  const [q, setQ] = useState("");
  const [all, setAll] = useState(null);            // remises du jour (bandeau, inspirations)
  const [feed, setFeed] = useState(null);          // accueil : sélection ou résultats de recherche
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [xcat, setXcat] = useState("");            // Explorer : catégorie ; "" = tout
  const [sort, setSort] = useState("pct");         // Explorer : pct | asc | desc
  const [xlist, setXlist] = useState(null);
  const [xsearch, setXsearch] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [list, setList] = useState(null);          // pièce
  const [item, setItem] = useState(null);
  const [brandPage, setBrandPage] = useState(null);
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

  useEffect(() => {
    api("categories").then(setCategories).catch(() => setError("Impossible de charger les catégories."));
    api("brands").then(setBrands).catch(() => {});
    api("today").then(d => { setAll(d); setError(null); }).catch(() => setError("Impossible de charger les remises."));
  }, [version]);

  const catsOf = f => categories.filter(c => c.family === f).map(c => c.key).join(",");
  useEffect(() => {                                                         // accueil : univers ou recherche
    if (view || tab !== "home") return;
    const t = setTimeout(() => {
      const path = q.trim() ? `search?q=${encodeURIComponent(q.trim())}` : family ? `today?category=${catsOf(family)}` : "today";
      api(path).then(setFeed).catch(() => setError("Impossible de charger les produits."));
    }, q ? 200 : 0);
    return () => clearTimeout(t);
  }, [tab, family, q, view, version, categories]);

  useEffect(() => {                                                         // Explorer : catégorie ou recherche
    if (view || tab !== "explore") return;
    const t = setTimeout(() => {
      const path = xsearch && q.trim() ? `search?q=${encodeURIComponent(q.trim())}` : xcat ? `today?category=${xcat}` : "today";
      api(path).then(setXlist).catch(() => {});
    }, q ? 200 : 0);
    return () => clearTimeout(t);
  }, [tab, xcat, q, xsearch, view, version]);

  useEffect(() => {
    if (!view) return;
    if (view.kind === "item") api(`item/${view.id}`).then(setItem).catch(() => setError("Produit introuvable."));
    if (view.kind === "brand") api(`brand/${encodeURIComponent(view.name)}`).then(setBrandPage).catch(() => setError("Marque introuvable."));
    if (view.kind === "room") api(`today?category=${view.room.cats.join(",")}`).then(setList).catch(() => setError("Pièce introuvable."));
  }, [view, version]);

  useEffect(() => { window.scrollTo(0, 0); }, [view, tab]);

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

  const goTab = t => { setView(null); setItem(null); setBrandPage(null); setList(null); setTab(t); setQ(""); setXsearch(false); };
  // Chaque vue garde celle d'où l'on vient : « Retour » y ramène. via : d'où vient la fiche (mesure des clics sortants).
  const open = (id, via) => { setItem(null); setView(v => ({ kind: "item", id, via, from: v })); };
  const openBrand = name => { setBrandPage(null); setView(v => ({ kind: "brand", name, from: v })); };
  const openRoom = room => { setList(null); setView(v => ({ kind: "room", room, from: v })); };
  const goBack = () => { setItem(null); setBrandPage(null); setList(null); setView(view?.from || null); };
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

  const searchBar = <label className="sbar"><Icon d={UI.search} size={19} />
    <input value={q} onChange={e => setQ(e.target.value)} placeholder="Une marque, un produit, une envie…" aria-label="Rechercher" enterKeyHint="search" />
    {q && <button className="sx" aria-label="Effacer" onClick={() => setQ("")}><Icon d={UI.x} size={18} /></button>}</label>;
  const back = <button className="back" onClick={goBack}><Icon d={UI.back} size={18} sw={2.2} />Retour</button>;
  const tabsList = [["home", "Accueil", UI.home], ["explore", "Explorer", UI.search], ["saved", "Favoris", UI.heart], ["me", "Profil", UI.user]];
  const plural = (n, w) => `${n} ${w}${n > 1 ? "s" : ""}`;
  const loginCard = (title, msg) => <div className="login"><h3>{title}</h3><p>Votre e-mail suffit, sans mot de passe.</p>
    <button className="cta" onClick={() => askLogin(msg)}>Me connecter</button></div>;
  const rooms = ROOMS.map(r => {
    const here = categories.filter(c => r.cats.includes(c.key));
    return here.length ? { ...r, best: Math.max(...here.map(c => c.best)), sub: here.map(c => c.label).join(", "),
      art: here.some(c => c.key === r.art) ? r.art : here[0].key } : null;
  }).filter(Boolean);

  let body;
  if (view?.kind === "item" && item) {
    const best = item.offers.find(o => o.best);
    const when = timing(item);
    const source = view.via || "item";
    body = <div className="item">
      <div className="hero">
        <div className="vis" style={{ aspectRatio: `1 / ${Math.min(1.05, ratioOf(item.category))}` }}><Vignette category={item.category} seed={item.id} label={item.kind} /></div>
        <div className="float"><button className="fbtn" onClick={goBack} aria-label="Retour"><Icon d={UI.back} size={20} sw={2.2} /></button>
          <div><button className="fbtn" onClick={() => share(item)} aria-label="Partager"><Icon d={UI.share} size={19} /></button>
            <button className={`fbtn ${isSaved(item.id) ? "on" : ""}`} onClick={() => toggleSave(item.id)} aria-pressed={isSaved(item.id)}
              aria-label={isSaved(item.id) ? "Retirer des favoris" : "Ajouter aux favoris"}><Icon d={UI.heart} size={20} fill={isSaved(item.id)} /></button></div></div>
      </div>
      <div>
        <div className="info">
          <div className="brand">{item.brand} · {item.kind}</div>
          <h1 className="title">{item.name || item.title}</h1>
          <div className="prices">{item.pct > 0 && <span className="pct">−{item.pct} %</span>}<span className="now">{eur(item.price)}</span>
            {item.pct > 0 && item.was && <s>{eur(item.was)}</s>}</div>
          {when && <div className="when"><Icon d={UI.cal} size={20} />{when}</div>}
          {best && <a className="buy" href={`/api/r/out/${best.offer_id}?from=${source}`} target="_blank" rel="noopener">
            Voir l'offre chez {best.merchant}<Icon d={UI.ext} size={18} sw={2.2} /></a>}
        </div>
        {item.history && <><div className="sechead"><h2>Prix sur 90 jours</h2></div><PriceChart history={item.history} price={item.price} /></>}
        {item.specs.length > 0 && <><div className="sechead"><h2>À propos</h2></div>
          <div className="about"><ul className="specs">{item.specs.map(s => <li key={s}><Icon d={specIcon(s)} size={18} />{s}</li>)}</ul></div></>}
        {item.alternatives.length > 0 && <>
          <div className="sechead"><h2>Moins cher, comparable</h2></div>
          <div className="scroller">{item.alternatives.map(card("alternative"))}</div>
        </>}
        {item.offers.length > 1 && <>
          <div className="sechead"><h2>Autres enseignes</h2></div>
          <div className="offers">
            {item.offers.filter(o => o !== best).map(o => <div key={o.offer_id} className="offer">
              <div><div className="m">{o.merchant}</div>{o.availability === "out_of_stock" && <div className="e">Indisponible</div>}</div>
              <div className="r"><b>{eur(o.price)}</b>
                <a className="go" href={`/api/r/out/${o.offer_id}?from=${source}`} target="_blank" rel="noopener">Voir<Icon d={UI.ext} size={16} sw={2.2} /></a></div></div>)}
          </div>
        </>}
        {item.alternatives.length === 0 && item.similar.length > 0 && <>
          <div className="sechead"><h2>Produits similaires</h2></div>
          <div className="scroller">{item.similar.map(card("similar"))}</div>
        </>}
      </div>
    </div>;
  } else if (view?.kind === "brand" && brandPage) {
    const on = isFollowed(brandPage.brand);
    body = <>
      {back}
      <div className="pagehead"><div><h1>{brandPage.brand}</h1><div className="sub">{plural(brandPage.products.length, "remise")} aujourd'hui</div></div>
        <button className={`pill ${on ? "on" : ""}`} onClick={() => toggleFollow(brandPage.brand)} aria-pressed={on}>
          <Icon d={on ? UI.check : UI.plus} size={17} sw={2.4} />{on ? "Suivie" : "Suivre"}</button></div>
      <div style={{ height: 18 }} />
      {grid(brandPage.products)}
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
  } else if (tab === "home") {
    const items = feed?.products || [];
    body = <>
      <Ticker items={all?.products || []} publishedAt={all?.published_at} />
      <div className="intro">
        <h1>De bonnes affaires, pour vos envies.</h1>
        <p>{all ? <><b>{plural(all.total, "remise")}</b> en ce moment sur les grandes marques. </> : null}Mise à jour chaque jour.</p>
      </div>
      {searchBar}
      {!q && <div className="chips" role="group" aria-label="Univers">
        <button className={!family ? "on" : ""} aria-pressed={!family} onClick={() => setFamily("")}>Pour vous</button>
        {Object.keys(FAMILY).filter(f => categories.some(c => c.family === f)).map(f =>
          <button key={f} className={family === f ? "on" : ""} aria-pressed={family === f} onClick={() => setFamily(x => x === f ? "" : f)}>{FAMILY[f]}</button>)}
      </div>}
      {!q && !family && rooms.length > 0 && <>
        <div className="sechead"><h2>Inspirations du moment</h2></div>
        <div className="rooms">{rooms.map(r => <button key={r.key} className="room" onClick={() => openRoom(r)}
          aria-label={`${r.label}, jusqu'à moins ${r.best} %, ${r.sub}`}>
          <Vignette category={r.art} seed={r.key} ratio={1.32} floor={0.7} zoom={ratioOf(r.art) > 1 ? 0.9 : 1.04} /><span className="shade" />
          <span className="rt"><b>{r.label}</b><span>Jusqu'à −{r.best} %</span><small>{r.sub}</small></span></button>)}</div>
      </>}
      <div className="sechead"><h2>{q ? (feed ? plural(feed.total, "résultat") : "…") : family ? FAMILY[family] : "Nos sélections pour vous"}</h2>
        {!q && feed && <span className="n">{plural(feed.total, "remise")}</span>}</div>
      {feed && items.length === 0 && <div className="empty">{q ? "Aucun produit ne correspond." : "Aucune remise dans cet univers aujourd'hui."}</div>}
      {grid(items)}
    </>;
  } else if (tab === "explore") {
    const items = [...(xlist?.products || [])];
    if (!(xsearch && q.trim())) items.sort((a, b) => sort === "asc" ? a.price - b.price : sort === "desc" ? b.price - a.price : 0);
    body = <>
      <div className="pagehead"><h1>Explorer</h1><div style={{ display: "flex" }}>
        <button className="ibtn" aria-label="Trier et marques" onClick={() => setSheet(true)}><Icon d={UI.sliders} size={22} /></button>
        <button className="ibtn" aria-label="Rechercher" aria-pressed={xsearch} onClick={() => { setXsearch(s => !s); setQ(""); }}>
          <Icon d={xsearch ? UI.x : UI.search} size={22} /></button></div></div>
      {xsearch && searchBar}
      {!(xsearch && q.trim()) && <div className="chips" role="group" aria-label="Catégories">
        <button className={!xcat ? "on" : ""} aria-pressed={!xcat} onClick={() => setXcat("")}>Tous</button>
        {categories.map(c => <button key={c.key} className={xcat === c.key ? "on" : ""} aria-pressed={xcat === c.key}
          onClick={() => setXcat(k => k === c.key ? "" : c.key)}>{c.label}</button>)}</div>}
      <div style={{ height: 16 }} />
      {xlist && items.length === 0 && <div className="empty">{xsearch && q.trim() ? "Aucun produit ne correspond." : "Aucune remise ici aujourd'hui."}</div>}
      {grid(items)}
      {sheet && <div className="sheet-wrap" onClick={() => setSheet(false)}><div className="sheet" onClick={e => e.stopPropagation()}>
        <div className="eyebrow">Explorer</div><h2>Trier</h2>
        <div className="opts" style={{ marginTop: 14 }}>{[["pct", "Meilleures remises"], ["asc", "Prix croissant"], ["desc", "Prix décroissant"]].map(([k, l]) =>
          <button key={k} className={sort === k ? "on" : ""} aria-pressed={sort === k} onClick={() => { setSort(k); setSheet(false); }}>{l}
            {sort === k && <Icon d={UI.check} size={18} sw={2.4} />}</button>)}</div>
        <h3>Marques</h3>
        <div className="bchips" style={{ padding: 0 }}>{brands.map(b => <button key={b.name} className={b.followed ? "on" : ""}
          onClick={() => { setSheet(false); openBrand(b.name); }}>{b.name}</button>)}</div>
      </div></div>}
    </>;
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
      <div className="tabs">{tabsList.map(([k, l, d]) => <button key={k} className={tab === k && !view ? "on" : ""} onClick={() => goTab(k)}>
        <Icon d={d} size={18} />{l}</button>)}</div>
      <button className="ibtn" aria-label={drops ? `${drops} baisse${drops > 1 ? "s" : ""} de prix sur vos favoris` : "Alertes de prix"} onClick={() => goTab("saved")}>
        <Icon d={UI.bell} size={22} />{drops > 0 && <span className="dot">{drops}</span>}</button>
    </header>}
    {error && <div className="empty">{error}</div>}
    {body}
    <nav className="d-nav" aria-label="Navigation">{tabsList.map(([k, l, d]) =>
      <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} onClick={() => goTab(k)}>
        <Icon d={d} size={23} fill={tab === k && k !== "explore"} />{l}</button>)}</nav>
    {login && <LoginSheet message={login.message} onClose={() => setLogin(null)}
      onDone={() => { setLogin(null); refreshSession(); setVersion(v => v + 1); }} />}
    <Toast text={toast} />
  </div></div>;
}
