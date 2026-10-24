/* DEALS — application grand public, branchée sur /api/r/. Interface v45 : minimaliste, sans friction ; la fiche d'un
   produit propose ce qui le remplace pour moins cher.

   Une liste se lit en un regard : marque, produit, prix, remise. Rien d'autre. La qualité est implicite (l'app ne montre
   que de vraies remises) : aucune mention « vérifiée ». Les durées (depuis quand, jusqu'à quand) ne sont que dans la
   fiche, avec l'offre à un geste. La recherche couvre tout le catalogue suivi (les remises d'abord) : on ouvre le
   produit qu'on regarde ailleurs, en remise ou non, et sa fiche montre « Moins cher, comparable ». Principes gardés des
   maquettes : le produit est l'entrée, un deal est le même pour tout le monde, pas d'image (V1), le signet sur chaque
   ligne, les marques suivies, la connexion demandée au moment de l'action. Gardé de la v43 : catégories sur l'accueil,
   pictogrammes dans Explorer, baisse de prix d'un favori, deux colonnes sur ordinateur, police servie avec la page,
   contrastes et zones à toucher aux normes. */
import { useState, useEffect } from "react";

/* ---------------------------------------------------------------- pictogrammes de catégorie (dessins originaux, 24 × 24) */
const C = (x, y, r) => `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
const WASHER = ["M5.5 3h13A1.5 1.5 0 0 1 20 4.5v15a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5v-15A1.5 1.5 0 0 1 5.5 3z",
  "M4 7.5h16", "M7 5.3h.01", "M10 5.3h4", C(12, 14.2, 4.3)];
const FRIDGE = "M7.5 2.5h9A1.5 1.5 0 0 1 18 4v16a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 20V4a1.5 1.5 0 0 1 1.5-1.5z";
const OVEN = ["M4.5 4h15A1.5 1.5 0 0 1 21 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5v-13A1.5 1.5 0 0 1 4.5 4z",
  "M3 8.5h18", "M6.5 6.3h.01", "M9.5 6.3h.01", "M14 6.3h3.5", "M7 11.5h10v5H7z"];
const CAT = {
  lave_linge: [...WASHER, "M9.6 14.8c.8.6 1.6.6 2.4 0s1.6-.6 2.4 0"],
  lave_linge_sechant: [...WASHER, "M9.6 14.8c.8.6 1.6.6 2.4 0s1.6-.6 2.4 0"],
  seche_linge: [...WASHER, "M9.8 13.2c.7-.5 1.5-.5 2.2 0s1.5.5 2.2 0", "M9.8 15.6c.7-.5 1.5-.5 2.2 0s1.5.5 2.2 0"],
  lave_vaisselle: [WASHER[0], "M4 7.5h16", "M9.5 10h5", "M7.5 17.5h9", "M9 17.5v-3", "M12 17.5v-4", "M15 17.5v-3"],
  refrigerateur: [FRIDGE, "M6 9.5h12", "M9 5.5v2", "M9 12v3.5"],
  congelateur: [FRIDGE, "M6 9h12", "M6 15h12", "M10.5 6h3", "M10.5 12h3", "M10.5 18h3"],
  four: OVEN,
  cuisiniere: OVEN,
  plaque_cuisson: ["M4.5 5h15A1.5 1.5 0 0 1 21 6.5v11a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5v-11A1.5 1.5 0 0 1 4.5 5z",
    C(9, 12, 3.2), C(16, 9.3, 1.8), C(16, 14.7, 1.8)],
  hotte: ["M10 2.5v6.5", "M14 2.5v6.5", "M10 9h4l6.5 6.5h-17z", "M3.5 15.5v2h17v-2"],
  micro_ondes: ["M4 5h16a1.5 1.5 0 0 1 1.5 1.5v11A1.5 1.5 0 0 1 20 19H4a1.5 1.5 0 0 1-1.5-1.5v-11A1.5 1.5 0 0 1 4 5z",
    "M5.5 8h9.5v8H5.5z", "M17.5 5v14", "M19.5 9h.01", "M19.5 12h.01"],
  machine_cafe: ["M6 3h12v4H6z", "M7 7v14h10V7", "M10 13h4v3.5a1.5 1.5 0 0 1-1.5 1.5h-1a1.5 1.5 0 0 1-1.5-1.5z", "M12 7v3.5"],
  canape: ["M5 11V8.5A2.5 2.5 0 0 1 7.5 6h9A2.5 2.5 0 0 1 19 8.5V11", "M3 13a2 2 0 0 1 4 0v1.5h10V13a2 2 0 0 1 4 0v4.5H3z",
    "M5 17.5v2", "M19 17.5v2"],
  fauteuil: ["M7 10.5V8a2.5 2.5 0 0 1 2.5-2.5h5A2.5 2.5 0 0 1 17 8v2.5", "M5 12.5a2 2 0 0 1 4 0V14h6v-1.5a2 2 0 0 1 4 0V18H5z",
    "M7 18v2", "M17 18v2"],
  lit: ["M3 5.5v14", "M3 13h18v4.5", "M3 17.5h18", "M21 17.5v2", "M6 10.5A1.5 1.5 0 0 1 7.5 9h3a1.5 1.5 0 0 1 1.5 1.5V13H6z"],
  armoire: ["M5.5 3h13a1 1 0 0 1 1 1v15.5h-15V4a1 1 0 0 1 1-1z", "M12 3v16.5", "M10 11.5v1.5", "M14 11.5v1.5", "M6.5 19.5V21", "M17.5 19.5V21"],
  table: ["M3 8.5h18", "M4.5 8.5v2h15v-2", "M6 10.5V19", "M18 10.5V19"],
  buffet: ["M3.5 7h17a1 1 0 0 1 1 1v8.5h-19V8a1 1 0 0 1 1-1z", "M9 7v9.5", "M15 7v9.5", "M7 11.5h.01", "M11 11.5h.01", "M17 11.5h.01",
    "M4.5 16.5v2", "M19.5 16.5v2"],
  meuble_tv: ["M6 3h12a1 1 0 0 1 1 1v6.5H5V4a1 1 0 0 1 1-1z", "M12 10.5v2", "M3.5 12.5h17a1 1 0 0 1 1 1V19h-19v-5.5a1 1 0 0 1 1-1z", "M12 12.5V19"],
  commode: ["M5 4h14a1 1 0 0 1 1 1v14H4V5a1 1 0 0 1 1-1z", "M4 9h16", "M4 14h16", "M10.5 6.5h3", "M10.5 11.5h3", "M10.5 16.5h3",
    "M5.5 19v1.5", "M18.5 19v1.5"],
  matelas: ["M6 8h12a3 3 0 0 1 3 3v2a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-2a3 3 0 0 1 3-3z", "M7.5 12h.01", "M12 12h.01", "M16.5 12h.01"],
  sommier: ["M4 8h16a1 1 0 0 1 1 1v4H3V9a1 1 0 0 1 1-1z", "M3 10.5h18", "M5 13v4", "M19 13v4", "M12 13v3"],
  luminaire: ["M8.5 3.5h7l3.5 7.5h-14z", "M12 11v8", "M8.5 20.5h7"],
  aspirateur: ["M14.5 3h4", "M16.5 3l-1.15 3.1", "M13.73 10.41L10.9 18", C(14.54, 8.25, 2.3), "M6 18h6.7a2 2 0 0 1 2 2v.5H5.5a1.25 1.25 0 0 1 0-2.5z"],
  robot_aspirateur: [C(12, 12, 8.5), "M6.6 8.8a6.6 6.6 0 0 1 10.8 0", "M12 15h.01"],
};
const UI = {
  search: [C(10.5, 10.5, 6.5), "M15.5 15.5L20 20"],
  back: ["M14.5 5.5L8 12l6.5 6.5"],
  next: ["M9.5 5.5L16 12l-6.5 6.5"],
  ext: ["M9 15l6.5-6.5", "M10 8.5h5.5V14"],
  check: ["M5.5 12.5l4 4 9-9"],
  x: ["M7 7l10 10", "M17 7L7 17"],
  tag: ["M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3-8.7 8.7z", "M8 7.5h.01"],
  today: ["M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3-8.7 8.7z", "M9.5 14.5l4.5-4.5", "M10 10.2h.01", "M13.6 14h.01"],
  compass: [C(12, 12, 8.5), "M15.5 8.5l-2 5-5 2 2-5z"],
  plus: ["M12 5v14", "M5 12h14"],
  mark: ["M6 3h12v18l-6-4-6 4z"],
};
const Icon = ({ d, size = 20, sw = 1.8, fill }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className="i"
  fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
  {d.map((p, i) => <path key={i} d={p} />)}{fill && <path d={d[0]} fill="currentColor" stroke="none" />}</svg>;
const CatIcon = ({ cat, size }) => <Icon d={CAT[cat] || UI.tag} size={size} sw={1.6} />;
const Mark = ({ on, size = 20 }) => <Icon d={UI.mark} size={size} fill={on} />;

/* ---------------------------------------------------------------- formats */
const eur = n => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " €";
const iso = d => new Date(`${d}T12:00:00`);
const dayLabel = d => new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short" }).format(iso(d));
const daysBetween = (a, b) => Math.round((iso(b) - iso(a)) / 86400000);
const FAMILY = { electromenager: "Électroménager", ameublement: "Ameublement", literie: "Literie" };

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

const CSS = `
.d{--ink:#101112;--paper:#FFFFFF;--tint:#F3F3F1;--tint2:#EAEAE6;--mid:#5E6166;--soft:#6B6E73;--icon:#8A8D92;--line:#E7E7E4;
  --red:#FF4D1A;--red-strong:#D63A0D;--red-ink:#C2330B;--red-soft:#FFEAE2;--good:#1F7A52;
  font-family:Manrope,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif;color:var(--ink);background:var(--paper);min-height:100vh;
  font-size:15px;line-height:1.4;-webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1}
.d *{box-sizing:border-box}.d button{font:inherit;color:inherit;cursor:pointer}.d input{font:inherit}
.d .i{display:block;flex:0 0 auto}
.d :focus-visible{outline:2px solid var(--red-ink);outline-offset:2px;border-radius:10px}
.d .app{max-width:480px;margin:0 auto;min-height:100vh;background:var(--paper);position:relative;padding-bottom:92px}
.d .pad{padding:0 16px}
.d .eyebrow{font-size:11.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--mid)}
.d .top{display:flex;justify-content:space-between;align-items:center;height:54px;padding:0 16px}
.d .logo{font-weight:800;font-size:21px;letter-spacing:-.045em;border:0;background:none;min-height:44px;padding:0 6px;margin-left:-6px}.d .logo b{color:var(--red)}
.d .tabs{display:none}
.d .intro{padding:6px 16px 0}
.d h1{font-size:28px;font-weight:800;letter-spacing:-.04em;line-height:1.08;margin:0}
.d h1 em{font-style:normal;color:var(--red)}
.d .sbar{display:flex;align-items:center;gap:10px;background:var(--tint);border-radius:16px;padding:0 6px 0 14px;height:50px;margin:14px 16px 0;color:var(--mid)}
.d .sbar input{flex:1;min-width:0;border:0;outline:0;background:transparent;font-size:16px;color:var(--ink);height:100%}
.d .sbar input::placeholder{color:var(--soft)}
.d .sx{border:0;background:none;color:var(--mid);width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:12px}
.d .cats{display:flex;gap:8px;overflow-x:auto;padding:12px 16px 2px;scrollbar-width:none}
.d .cats::-webkit-scrollbar{display:none}
.d .cats button{flex:0 0 auto;border:0;background:var(--tint);border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:700;white-space:nowrap}
.d .cats button.on{background:var(--ink);color:#fff}
.d .pic{flex:0 0 auto;width:48px;height:48px;border-radius:15px;background:var(--tint);color:var(--ink);display:flex;align-items:center;justify-content:center}
.d .hero{margin:16px 16px 0;width:calc(100% - 32px);background:var(--ink);color:#fff;border-radius:26px;padding:20px;cursor:pointer;display:block;border:0;text-align:left}
.d .hero .ht{display:flex;align-items:center;gap:14px}
.d .hero .pic,.d .pcard .pic{width:56px;height:56px;border-radius:17px;background:rgba(255,255,255,.1);color:#fff}
.d .hero .brand{display:block;font-size:24px;font-weight:800;letter-spacing:-.035em;line-height:1.1}
.d .hero .kind{display:block;font-size:15px;font-weight:700;color:#9EA1A6;margin-top:3px}
.d .hero .row{display:flex;justify-content:space-between;align-items:flex-end;margin-top:22px;gap:10px}
.d .hero .pct{font-size:56px;font-weight:800;letter-spacing:-.06em;color:var(--red);line-height:.85}
.d .hero .pct small{display:block;font-size:14px;font-weight:700;letter-spacing:0;color:#B5B8BC;line-height:1.2;margin-bottom:6px}
.d .hero .price{font-size:26px;font-weight:800;letter-spacing:-.04em;line-height:1}
.d .sechead{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:22px 16px 6px}
.d .sechead h2{font-size:19px;font-weight:800;letter-spacing:-.03em;margin:0}
.d .prow{display:grid;grid-template-columns:48px 1fr auto 44px;gap:0 14px;align-items:center;width:100%;border-top:1px solid var(--line);padding:14px 6px 14px 16px;text-align:left;cursor:pointer;background:var(--paper)}
.d .prow:last-child{border-bottom:1px solid var(--line)}
.d .prow .txt{min-width:0}
.d .prow .brand{display:block;font-size:17px;font-weight:800;letter-spacing:-.025em;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.d .prow .kind{display:block;margin-top:2px;font-size:14px;font-weight:600;color:var(--mid)}
.d .prow .drop{display:block;margin-top:2px;font-size:14px;font-weight:800;color:var(--good)}
.d .prow .p{text-align:right;white-space:nowrap}
.d .prow .p .off{display:block;font-size:21px;font-weight:800;letter-spacing:-.04em;line-height:1.1;color:var(--red-ink)}
.d .prow .p .off small{display:block;font-size:11.5px;font-weight:700;letter-spacing:0;color:var(--mid);line-height:1.2}
.d .prow .p .at{display:block;margin-top:1px;font-size:14px;font-weight:700;color:var(--ink)}
.d .prow .into{width:44px;height:44px;display:flex;align-items:center;justify-content:center;color:var(--icon)}
.d .ghead{display:flex;align-items:center;gap:14px;padding:4px 16px 16px}
.d .ghead .kind{font-size:15px;font-weight:600;color:var(--mid);margin-top:3px}
.d .prow .p .now{display:block;font-size:18px;font-weight:800;letter-spacing:-.03em}
.d .rfav{border:0;background:none;width:44px;height:44px;border-radius:12px;color:var(--icon);display:flex;align-items:center;justify-content:center}
.d .rfav.on{color:var(--red-ink)}
.d .tagl{display:inline-block;font-size:10.5px;font-weight:800;color:var(--red-ink);text-transform:uppercase;letter-spacing:.06em;margin-left:6px}
.d .empty{padding:28px 16px;color:var(--mid)}
.d .err{color:var(--red-ink);font-size:14px;font-weight:700;margin-top:10px}
.d .back{border:0;background:none;min-height:44px;padding:0 16px 0 10px;font-size:14px;font-weight:800;color:var(--mid);display:flex;align-items:center;gap:4px}
.d .pcard{margin:4px 16px 0;background:var(--ink);color:#fff;border-radius:28px;padding:20px}
.d .phead{display:flex;align-items:center;gap:14px}
.d .phead .who{flex:1;min-width:0}
.d .pcard .brand{font-size:28px;font-weight:800;letter-spacing:-.04em;line-height:1.05;color:#fff;margin:0}
.d .pcard .kind{font-size:15px;font-weight:700;color:#9EA1A6;margin-top:4px}
.d .pcard .deal{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin-top:24px}
.d .pcard .pct{font-size:68px;font-weight:800;letter-spacing:-.065em;line-height:.82;color:var(--red)}
.d .pcard .price{font-size:30px;font-weight:800;letter-spacing:-.04em;line-height:1;text-align:right}
.d .pcard .price s{display:block;font-size:14px;font-weight:600;color:#9EA1A6;letter-spacing:0;margin-top:6px}
.d .pcard .when{margin-top:16px;font-size:13.5px;font-weight:700;color:#B5B8BC}
.d .pcard .buy{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:16px;min-height:50px;border-radius:16px;background:#fff;color:var(--ink);font-size:15px;font-weight:800;text-decoration:none}
.d .fav{flex:0 0 auto;border:0;background:rgba(255,255,255,.12);color:#fff;width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.d .fav.on{background:var(--red-strong)}
.d .desc{padding:0 16px}
.d .desc p{margin:0;font-size:16px;font-weight:600;line-height:1.35;color:var(--ink)}
.d .specs{list-style:none;margin:12px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.d .specs li{background:var(--tint);border-radius:999px;padding:8px 13px;font-size:14px;font-weight:700}
.d .offers{padding:0 16px}
.d .offer{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}
.d .offer:first-child{border-top:1px solid var(--line)}
.d .offer .m{font-size:16px;font-weight:800;letter-spacing:-.02em}
.d .offer .e{font-size:12.5px;color:var(--mid);margin-top:2px;font-weight:700}
.d .offer .r{display:flex;align-items:center;gap:12px}
.d .offer .r b{font-size:18px;font-weight:800;letter-spacing:-.03em}
.d .offer .go{display:flex;align-items:center;gap:4px;min-height:44px;border:0;background:var(--tint);border-radius:12px;padding:0 12px;font-size:13.5px;font-weight:800;text-decoration:none;color:var(--ink)}
.d .seg{display:flex;background:var(--tint);border-radius:14px;padding:4px;margin:14px 16px 0}
.d .seg button{flex:1;border:0;background:none;min-height:40px;font-size:14px;font-weight:800;color:var(--mid);border-radius:11px}
.d .seg button.on{background:var(--paper);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.d .fam{padding:20px 16px 0}.d .fam h2{font-size:15px;font-weight:800;margin:0 0 10px;letter-spacing:-.01em}
.d .tiles{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.d .tile{border:0;background:var(--tint);border-radius:18px;padding:10px 12px;text-align:left;display:flex;align-items:center;gap:10px;min-height:60px;font-size:15px;font-weight:800;letter-spacing:-.02em}
.d .tile .ico{width:38px;height:38px;border-radius:12px;background:var(--paper);display:flex;align-items:center;justify-content:center;flex:0 0 auto}
.d .brands{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:14px 16px 0}
.d .bcard{border:0;background:var(--tint);border-radius:18px;min-height:56px;padding:10px 14px;text-align:left;display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:16px;font-weight:800;letter-spacing:-.02em}
.d .bcard.liked{background:var(--red-soft);color:var(--red-ink)}
.d .more{border:1px dashed #C9C9C3;background:none;border-radius:16px;min-height:48px;font-size:14px;font-weight:800;color:var(--mid);width:100%}
.d .pagehead{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;padding:4px 16px 16px}
.d .pill{flex:0 0 auto;display:flex;align-items:center;gap:6px;border:0;background:var(--ink);color:#fff;border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:800}
.d .pill.on{background:var(--red-soft);color:var(--red-ink)}
.d .login{margin:16px 16px 0;background:var(--tint);border-radius:22px;padding:20px}
.d .login h3{font-size:19px;font-weight:800;letter-spacing:-.03em;margin:0}
.d .login p{color:var(--mid);margin:8px 0 0;font-size:14px}
.d .cta{display:block;width:100%;margin-top:16px;border:0;background:var(--ink);color:#fff;border-radius:16px;min-height:50px;font-size:15px;font-weight:800}
.d .cta:disabled{opacity:.5}
.d .ghost{border:0;background:none;color:var(--mid);font-size:14px;font-weight:800;min-height:44px;padding:0 16px;margin-top:12px;display:block}
.d .chips{display:flex;gap:8px;overflow-x:auto;padding:0 16px 2px;scrollbar-width:none}
.d .chips button{flex:0 0 auto;border:0;background:var(--red-soft);color:var(--red-ink);border-radius:999px;min-height:44px;padding:0 16px;font-size:14px;font-weight:800}
.d .sheet-wrap{position:fixed;inset:0;background:rgba(16,17,18,.4);display:flex;align-items:flex-end;justify-content:center;z-index:10}
.d .sheet{width:100%;max-width:480px;background:var(--paper);border-radius:26px 26px 0 0;padding:24px 20px 32px}
.d .sheet h2{font-size:22px;font-weight:800;letter-spacing:-.03em;margin:8px 0 0;line-height:1.15}
.d .sheet p.hint{color:var(--mid);font-size:14px;margin:8px 0 0}
.d .sheet input{width:100%;margin-top:16px;border:1px solid #CFCFCA;border-radius:14px;padding:14px;font-size:16px;color:var(--ink);outline:0}
.d .sheet input:focus{border-color:var(--ink)}
.d .toast{position:fixed;bottom:100px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 18px;border-radius:999px;font-size:14px;font-weight:700;z-index:9;white-space:nowrap}
nav.d-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:480px;display:grid;grid-template-columns:repeat(3,1fr);gap:6px;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid var(--line);z-index:5;padding:6px 10px calc(10px + env(safe-area-inset-bottom))}
.d-nav button{position:relative;border:0;background:none;min-height:54px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;font-size:12px;font-weight:800;color:var(--soft);border-radius:16px}
.d-nav button.on{color:var(--ink);background:var(--tint)}
.d-nav .badge{position:absolute;top:5px;left:calc(50% + 6px);min-width:18px;height:18px;border-radius:9px;background:var(--good);color:#fff;font-size:11px;line-height:18px;padding:0 5px}
@media (hover:hover){.d .prow:hover{background:#FAFAF8}.d .tile:hover,.d .bcard:hover{background:var(--tint2)}}
@media (min-width:1000px){
  .d .app{max-width:1180px;padding:0 32px 48px}
  .d .top{height:72px;padding:0;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);z-index:6}
  .d .tabs{display:flex;gap:4px}
  .d .tabs button{border:0;background:none;min-height:44px;padding:0 16px;border-radius:12px;font-size:14px;font-weight:800;color:var(--soft);display:flex;align-items:center;gap:7px}
  .d .tabs button.on{background:var(--tint);color:var(--ink)}
  nav.d-nav{display:none}
  .d .toast{bottom:32px}
  .d .home{display:grid;grid-template-columns:320px minmax(0,1fr);gap:40px;align-items:start;padding-top:28px}
  .d .side{position:sticky;top:100px}
  .d .side .intro,.d .side .sbar,.d .side .cats{margin-left:0;margin-right:0;padding-left:0;padding-right:0}
  .d .side .cats{flex-wrap:wrap;overflow:visible}
  .d h1{font-size:34px}
  .d .main .hero{margin:0;width:100%;padding:26px 28px 28px}
  .d .main .hero .brand{font-size:28px}.d .main .hero .price{font-size:32px}.d .main .hero .pct{font-size:64px}
  .d .main .sechead{padding-left:0;padding-right:0}
  .d .list{display:grid;grid-template-columns:1fr 1fr;column-gap:28px}
  .d .list .prow{padding-left:4px}
  .d .list .prow:last-child{border-bottom:0}
  .d .item{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:40px;align-items:start;padding-top:12px}
  .d .item .pcard{margin-left:0;margin-right:0}
  .d .item .offers,.d .item .sechead,.d .item .desc{padding-left:0;padding-right:0}
  .d .item .sechead:first-child{padding-top:0}
  .d .item .prow{padding-left:4px}
  .d .narrow{max-width:760px;margin:0 auto;padding-top:20px}
  .d .tiles{grid-template-columns:repeat(4,1fr)}.d .brands{grid-template-columns:repeat(4,1fr)}
  .d .sheet-wrap{align-items:center}.d .sheet{border-radius:26px}
}
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

export default function App() {
  const [tab, setTab] = useState("today");
  const [view, setView] = useState(null);          // null | { kind: "item", id } | { kind: "brand", name } | { kind: "cat", key, label }
  const [cat, setCat] = useState("");              // catégorie choisie sur l'accueil ; "" = tout
  const [mode, setMode] = useState("cat");         // Explorer : cat | brand
  const [q, setQ] = useState("");
  const [today, setToday] = useState(null);
  const [list, setList] = useState(null);          // liste d'une catégorie d'Explorer, ou résultats de recherche d'Explorer
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [moreBrands, setMoreBrands] = useState(false);
  const [item, setItem] = useState(null);
  const [brandPage, setBrandPage] = useState(null);
  const [session, setSession] = useState({ checked: false, email: null });
  const [saved, setSaved] = useState(new Set());
  const [followed, setFollowed] = useState(new Set());
  const [savedList, setSavedList] = useState(null);
  const [version, setVersion] = useState(0);       // incrémenté quand le classement doit être relu (ex. marque suivie)
  const [login, setLogin] = useState(null);
  const [toast, setToast] = useState(null);
  const [error, setError] = useState(null);

  const flash = t => { setToast(t); setTimeout(() => setToast(null), 2200); };
  const askLogin = message => setLogin({ message });

  const refreshSession = () => api("auth/me")
    .then(d => setSession({ checked: true, email: d.email }))
    .catch(() => setSession({ checked: true, email: null }));

  useEffect(() => {
    refreshSession();
    const url = new URL(window.location.href);
    if (url.searchParams.get("auth") === "expired") {
      flash("Ce lien a expiré. Demandez-en un nouveau.");
      url.searchParams.delete("auth");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
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
  }, [version]);

  useEffect(() => {
    if (view || tab !== "today") return;
    const t = setTimeout(() => {
      const params = new URLSearchParams();                   // une recherche porte sur tout le catalogue, remises d'abord
      if (q.trim()) params.set("q", q.trim()); else if (cat) params.set("category", cat);
      api(`${q.trim() ? "search" : "today"}?${params}`).then(d => { setToday(d); setError(null); })
        .catch(() => setError("Impossible de charger les produits."));
    }, q ? 200 : 0);
    return () => clearTimeout(t);
  }, [tab, cat, q, view, version]);

  useEffect(() => {
    if (view || tab !== "explore" || !q.trim()) return;
    const t = setTimeout(() => api(`search?q=${encodeURIComponent(q.trim())}`).then(setList).catch(() => {}), 200);
    return () => clearTimeout(t);
  }, [tab, q, view]);

  useEffect(() => {
    if (!view) return;
    if (view.kind === "item") api(`item/${view.id}`).then(setItem).catch(() => setError("Produit introuvable."));
    if (view.kind === "brand") api(`brand/${encodeURIComponent(view.name)}`).then(setBrandPage).catch(() => setError("Marque introuvable."));
    if (view.kind === "cat") api(`today?category=${encodeURIComponent(view.key)}`).then(setList).catch(() => setError("Catégorie introuvable."));
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

  const toggleFollow = async (brand) => {
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

  const goTab = t => { setView(null); setItem(null); setBrandPage(null); setList(null); setTab(t); setQ(""); };
  // chaque vue garde celle d'où l'on vient : « Retour » y ramène (fiche → groupe → accueil). via : d'où vient la fiche
  // (mesure des clics sortants).
  const open = (id, via) => { setItem(null); setView(v => ({ kind: "item", id, via, from: v })); };
  const openGroup = g => setView(v => ({ kind: "group", brand: g.brand, category: g.category, label: g.kind, items: g.items, from: v }));
  const goBack = () => { setItem(null); setBrandPage(null); setList(null); setView(view?.from || null); };
  const dropOf = p => p.saved_price ? Math.round(p.saved_price - p.price) : 0;
  const drops = (savedList || []).filter(p => dropOf(p) >= 1).length;

  const note = p => p.saving >= 1 ? `${eur(p.saving)} de moins` : dropOf(p) >= 1 ? `Baisse de ${eur(dropOf(p))}` : null;
  const said = p => `${p.brand}, ${p.name || p.title}, ${p.pct > 0 ? `moins ${p.pct} %, ` : ""}${eur(p.price)}`;   // lecteur d'écran : le titre complet
  // Une ligne = pictogramme, marque, catégorie, remise, prix. Les caractéristiques n'apparaissent que pour départager
  // deux produits de même marque et même catégorie : sous la marque (mode « detail »), ou seules dans la liste d'un
  // groupe, dont l'en-tête dit déjà la marque et la catégorie (mode « group »).
  const telling = p => p.specs.slice(0, 2).join(" · ") || p.name || p.kind;
  const rowOf = (p, via, mode) => <div key={p.id} className="prow" role="button" tabIndex={0} aria-label={said(p)}
    onClick={() => open(p.id, via)} onKeyDown={e => { if (e.key === "Enter") open(p.id, via); }}>
    <span className="pic"><CatIcon cat={p.category} size={24} /></span>
    {mode === "group" ? <span className="txt"><span className="brand">{telling(p)}</span></span> : <span className="txt">
      <span className="brand">{p.brand}{isFollowed(p.brand) ? <span className="tagl">suivie</span> : ""}</span>
      {note(p) ? <span className="drop">{note(p)}</span> : <span className="kind">{mode === "detail" ? telling(p) : p.kind}</span>}
    </span>}
    <span className="p">{p.pct > 0 ? <><b className="off">−{p.pct} %</b><span className="at">{eur(p.price)}</span></>
      : <b className="now">{eur(p.price)}</b>}</span>
    <button className={`rfav ${isSaved(p.id) ? "on" : ""}`} aria-pressed={isSaved(p.id)}
      aria-label={isSaved(p.id) ? "Retirer des favoris" : "Ajouter aux favoris"} onClick={e => toggleSave(p.id, e)}>
      <Mark on={isSaved(p.id)} size={21} /></button></div>;
  const keyOf = p => `${p.brand}\u0001${p.category}`;
  const rows = (list, via) => {                                    // produits : départagés s'ils se ressemblent
    const n = {}; list.forEach(p => { n[keyOf(p)] = (n[keyOf(p)] || 0) + 1; });
    return list.map(p => rowOf(p, via, n[keyOf(p)] > 1 ? "detail" : null));
  };
  // Remises : une ligne par marque × catégorie (« Nordvik · Lit ») ; plusieurs produits → la ligne ouvre leur liste.
  const groups = list => {
    const out = [], at = new Map();
    for (const p of list) {
      if (!at.has(keyOf(p))) { at.set(keyOf(p), out.length); out.push({ key: keyOf(p), brand: p.brand, category: p.category, kind: p.kind, items: [] }); }
      out[at.get(keyOf(p))].items.push(p);
    }
    return out;
  };
  const bestPct = g => Math.max(...g.items.map(p => p.pct));
  const upTo = g => new Set(g.items.map(p => p.pct)).size > 1;
  const minPrice = g => Math.min(...g.items.map(p => p.price));
  const groupLabel = g => `${g.kind} · ${g.items.length} remises`;
  const groupRow = g => g.items.length === 1 ? rowOf(g.items[0], null, null) :
    <div key={g.key} className="prow" role="button" tabIndex={0} onClick={() => openGroup(g)}
      onKeyDown={e => { if (e.key === "Enter") openGroup(g); }}
      aria-label={`${g.brand}, ${groupLabel(g)}, ${upTo(g) ? "jusqu'à " : ""}moins ${bestPct(g)} %, dès ${eur(minPrice(g))}`}>
      <span className="pic"><CatIcon cat={g.category} size={24} /></span>
      <span className="txt"><span className="brand">{g.brand}{isFollowed(g.brand) ? <span className="tagl">suivie</span> : ""}</span>
        <span className="kind">{groupLabel(g)}</span></span>
      <span className="p"><b className="off">{upTo(g) && <small>jusqu'à</small>}−{bestPct(g)} %</b><span className="at">dès {eur(minPrice(g))}</span></span>
      <span className="into" aria-hidden="true"><Icon d={UI.next} size={20} sw={2.2} /></span></div>;
  const grouped = list => groups(list).map(groupRow);

  const searchBar = <label className="sbar"><Icon d={UI.search} size={19} />
    <input value={q} onChange={e => setQ(e.target.value)} placeholder="Rechercher un produit ou une marque" aria-label="Rechercher" enterKeyHint="search" />
    {q && <button className="sx" aria-label="Effacer" onClick={() => setQ("")}><Icon d={UI.x} size={18} /></button>}</label>;

  const back = (label, onClick) => <button className="back" onClick={onClick}><Icon d={UI.back} size={18} sw={2.2} />{label}</button>;
  const tabsList = [["today", "Aujourd'hui", UI.today], ["explore", "Explorer", UI.compass], ["saved", "Favoris", UI.mark]];
  const plural = (n, w) => `${n} ${w}${n > 1 ? "s" : ""}`;

  let body;
  if (view?.kind === "item" && item) {
    const best = item.offers.find(o => o.best);
    const when = timing(item);
    const source = view.via || "item";
    body = <>
      {back("Retour", goBack)}
      <div className="item">
        <div className="pcard">
          <div className="phead">
            <span className="pic"><CatIcon cat={item.category} size={28} /></span>
            <div className="who"><h1 className="brand">{item.brand}</h1><div className="kind">{item.kind}</div></div>
            <button className={`fav ${isSaved(item.id) ? "on" : ""}`} onClick={() => toggleSave(item.id)} aria-pressed={isSaved(item.id)}
              aria-label={isSaved(item.id) ? "Retirer des favoris" : "Ajouter aux favoris"}><Mark on={isSaved(item.id)} size={22} /></button>
          </div>
          <div className="deal">{item.pct > 0 ? <div className="pct">−{item.pct} %</div> : <div />}
            <div className="price">{eur(item.price)}{item.pct > 0 && item.was && <s>{eur(item.was)}</s>}</div></div>
          {when && <div className="when">{when}</div>}
          {best && <a className="buy" href={`/api/r/out/${best.offer_id}?from=${source}`} target="_blank" rel="noopener">
            Voir l'offre chez {best.merchant}<Icon d={UI.ext} size={18} sw={2.2} /></a>}
        </div>
        <div>
          <div className="sechead"><h2>Description</h2></div>
          <div className="desc"><p>{item.name || item.title}</p>
            {item.specs.length > 0 && <ul className="specs">{item.specs.map(x => <li key={x}>{x}</li>)}</ul>}</div>
          {item.alternatives.length > 0 && <>
            <div className="sechead"><h2>Moins cher, comparable</h2></div>
            <div>{rows(item.alternatives, "alternative")}</div>
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
            <div>{rows(item.similar, "similar")}</div>
          </>}
        </div>
      </div>
    </>;
  } else if (view?.kind === "brand" && brandPage) {
    const on = isFollowed(brandPage.brand);
    body = <div className="narrow">
      {back("Retour", goBack)}
      <div className="pagehead">
        <div><div className="eyebrow">Marque</div><h1>{brandPage.brand}</h1></div>
        <button className={`pill ${on ? "on" : ""}`} onClick={() => toggleFollow(brandPage.brand)} aria-pressed={on}>
          <Icon d={on ? UI.check : UI.plus} size={17} sw={2.4} />{on ? "Suivie" : "Suivre"}</button>
      </div>
      <div>{grouped(brandPage.products)}</div>
    </div>;
  } else if (view?.kind === "group") {
    body = <div className="narrow">
      {back("Retour", goBack)}
      <div className="ghead"><span className="pic"><CatIcon cat={view.category} size={26} /></span>
        <div><h1>{view.brand}</h1><div className="kind">{view.label} · {view.items.length} remises</div></div></div>
      <div>{view.items.map(p => rowOf(p, null, "group"))}</div>
    </div>;
  } else if (view?.kind === "cat") {
    body = <div className="narrow">
      {back("Retour", goBack)}
      <div className="pagehead"><h1>{view.label}</h1></div>
      <div>{grouped(list?.products || [])}</div>
      {list && list.total === 0 && <div className="empty">Aucune remise dans cette catégorie aujourd'hui.</div>}
    </div>;
  } else if (tab === "today") {
    const items = today?.products || [];
    const gs = q ? [] : groups(items);
    const hero = gs[0];
    body = <div className="home">
      <div className="side">
        <div className="intro">{q ? <h1>{today ? plural(today.total, "résultat") : "…"}</h1>
          : <h1><em>{today ? today.total : "…"}</em> remise{today && today.total > 1 ? "s" : ""} aujourd'hui</h1>}</div>
        {searchBar}
        {!q && categories.length > 1 && <div className="cats" role="group" aria-label="Catégories">
          <button className={!cat ? "on" : ""} aria-pressed={!cat} onClick={() => setCat("")}>Tout</button>
          {categories.map(x => <button key={x.key} className={cat === x.key ? "on" : ""} aria-pressed={cat === x.key}
            onClick={() => setCat(k => k === x.key ? "" : x.key)}>{x.label}</button>)}
        </div>}
      </div>
      <div className="main">
        {hero && (one => <button className="hero" onClick={() => one ? open(one.id) : openGroup(hero)}
          aria-label={one ? said(one) : `${hero.brand}, ${groupLabel(hero)}`}>
          <span className="ht"><span className="pic"><CatIcon cat={hero.category} size={30} /></span>
            <span><span className="brand">{hero.brand}</span><span className="kind">{one ? hero.kind : groupLabel(hero)}</span></span></span>
          <span className="row"><span className="pct">{upTo(hero) && <small>jusqu'à</small>}−{bestPct(hero)} %</span>
            <span className="price">{one ? eur(one.price) : `dès ${eur(minPrice(hero))}`}</span></span>
        </button>)(hero.items.length === 1 ? hero.items[0] : null)}
        <div style={{ height: 14 }} />
        {today && items.length === 0 && <div className="empty">{q ? "Aucun produit ne correspond." : "Aucune remise dans cette catégorie aujourd'hui."}</div>}
        <div className="list">{q ? rows(items) : gs.slice(1).map(groupRow)}</div>
      </div>
    </div>;
  } else if (tab === "explore") {
    const byFam = {};
    categories.forEach(x => { (byFam[x.family || "autres"] = byFam[x.family || "autres"] || []).push(x); });
    body = <div className="narrow">
      <div className="intro"><h1>Explorer</h1></div>
      {searchBar}
      {q.trim() ? <>
        <div style={{ height: 14 }} />
        <div>{rows(list?.products || [])}</div>
        {list && list.total === 0 && <div className="empty">Aucun produit ne correspond.</div>}
      </> : <>
        <div className="seg"><button className={mode === "cat" ? "on" : ""} onClick={() => setMode("cat")}>Catégories</button>
          <button className={mode === "brand" ? "on" : ""} onClick={() => setMode("brand")}>Marques</button></div>
        {mode === "cat" && Object.keys(FAMILY).concat(["autres"]).filter(f => byFam[f]).map(f => <div key={f} className="fam">
          <h2>{FAMILY[f] || "Autres"}</h2>
          <div className="tiles">{byFam[f].map(x => <button key={x.key} className="tile" onClick={() => setView({ kind: "cat", key: x.key, label: x.label })}>
            <span className="ico"><CatIcon cat={x.key} size={21} /></span>{x.label}</button>)}</div>
        </div>)}
        {mode === "cat" && categories.length === 0 && <div className="empty">Aucune remise aujourd'hui.</div>}
        {mode === "brand" && <>
          <div className="brands">{(moreBrands ? brands : brands.slice(0, 8)).map(b =>
            <button key={b.name} className={`bcard ${b.followed ? "liked" : ""}`} onClick={() => setView({ kind: "brand", name: b.name })}>
              {b.name}{b.followed && <Icon d={UI.check} size={17} sw={2.4} />}</button>)}</div>
          {brands.length > 8 && <div className="pad" style={{ marginTop: 12 }}>
            <button className="more" onClick={() => setMoreBrands(!moreBrands)}>{moreBrands ? "Voir moins" : "Voir plus"}</button></div>}
        </>}
      </>}
    </div>;
  } else {
    body = <div className="narrow">
      <div className="intro"><h1>Favoris</h1></div>
      {!session.checked && <div className="empty">Chargement…</div>}
      {session.checked && !session.email && <div className="login">
        <h3>Gardez vos favoris et vos marques.</h3>
        <p>Votre e-mail suffit, sans mot de passe.</p>
        <button className="cta" onClick={() => askLogin("Connectez-vous pour retrouver vos favoris")}>Me connecter</button>
      </div>}
      {session.email && <>
        <div className="sechead"><h2>Produits</h2></div>
        {savedList && savedList.length === 0 && <div className="empty" style={{ paddingTop: 0 }}>Touchez le signet d'un produit pour le garder ici.</div>}
        <div>{rows(savedList || [])}</div>
        <div className="sechead"><h2>Marques suivies</h2></div>
        {followed.size === 0 && <div className="empty" style={{ paddingTop: 0 }}>Suivez une marque depuis Explorer.</div>}
        {followed.size > 0 && <div className="chips">{[...followed].map(b =>
          <button key={b} onClick={() => { setTab("explore"); setMode("brand"); setView({ kind: "brand", name: b }); }}>{b}</button>)}</div>}
        <button className="ghost" onClick={logout}>Se déconnecter</button>
      </>}
    </div>;
  }

  return <div className="d"><style>{CSS}</style><div className="app">
    <header className="top">
      <button className="logo" onClick={() => goTab("today")} aria-label="Deals, accueil">Deal<b>s</b></button>
      <div className="tabs">{tabsList.map(([k, l, d]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => goTab(k)}><Icon d={d} size={18} />{l}</button>)}</div>
    </header>
    {error && <div className="empty">{error}</div>}
    {body}
    <nav className="d-nav" aria-label="Navigation">{tabsList.map(([k, l, d]) =>
      <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} onClick={() => goTab(k)}>
        <Icon d={d} size={22} />{l}{k === "saved" && drops > 0 && <span className="badge" aria-label={`${drops} en baisse`}>{drops}</span>}</button>)}</nav>
    {login && <LoginSheet message={login.message} onClose={() => setLogin(null)}
      onDone={() => { setLogin(null); refreshSession(); setVersion(v => v + 1); }} />}
    <Toast text={toast} />
  </div></div>;
}
