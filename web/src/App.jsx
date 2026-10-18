/* DEALS — application grand public (même design que la maquette v41), branchée sur /api/r/.
   Lecture ouverte : aujourd'hui, catégories, marques, fiches. Favoris et marques suivies : connexion par e-mail (lien magique),
   demandée au moment de l'action, jamais avant. Aucune donnée en dur : tout vient de l'API. */
import { useState, useEffect } from "react";

const Mark = ({ on, size = 22 }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" style={{ display: "block" }}>
  <path d="M6 3h12v18l-6-4-6 4z" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>;

const eur = n => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n) + " €";

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
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap');
.d{--ink:#101112;--paper:#FFFFFF;--tint:#F3F3F1;--mid:#5E6166;--low:#9A9DA2;--line:#E7E7E4;--red:#FF4D1A;--red-soft:#FFEAE2;--good:#1F7A52;
  font-family:Manrope,-apple-system,"Segoe UI",system-ui,sans-serif;color:var(--ink);background:#DADAD6;min-height:100vh;font-size:15px;line-height:1.4;-webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1}
.d *{box-sizing:border-box}.d button{font:inherit;color:inherit;cursor:pointer}.d input{font:inherit}
.d :focus-visible{outline:2px solid var(--red);outline-offset:3px;border-radius:8px}
.d .app{max-width:480px;margin:0 auto;min-height:100vh;background:var(--paper);position:relative;padding-bottom:96px}
.d .bar{display:flex;justify-content:space-between;align-items:center;height:62px;padding:0 20px}
.d .logo{font-weight:800;font-size:19px;letter-spacing:-.04em}.d .logo b{color:var(--red)}
.d .clock{font-size:12px;font-weight:600;color:var(--mid);background:var(--tint);border-radius:999px;padding:6px 11px}
.d .eyebrow{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mid)}
.d h1{font-size:40px;font-weight:800;letter-spacing:-.045em;line-height:1;margin:8px 0 0}
.d h1 em{font-style:normal;color:var(--red)}
.d .pad{padding:0 20px}
.d .sechead{display:flex;justify-content:space-between;align-items:center;padding:28px 20px 10px}
.d .sechead h2{font-size:21px;font-weight:800;letter-spacing:-.03em;margin:0}
.d .hero{margin:20px 20px 0;background:var(--ink);color:#fff;border-radius:26px;padding:22px;cursor:pointer;display:block;width:calc(100% - 40px);border:0;text-align:left}
.d .hero .t{font-size:24px;font-weight:800;letter-spacing:-.03em;line-height:1.1;margin-top:10px}
.d .hero .row{display:flex;justify-content:space-between;align-items:flex-end;margin-top:18px}
.d .hero .price{font-size:44px;font-weight:800;letter-spacing:-.05em;line-height:.9}
.d .hero .pct{font-size:30px;font-weight:800;letter-spacing:-.04em;color:var(--red);line-height:.9;text-align:right}
.d .prow{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;width:100%;border:0;background:none;border-top:1px solid var(--line);padding:16px 20px;text-align:left;cursor:pointer}
.d .prow .brand{font-size:12px;font-weight:700;color:var(--mid);text-transform:uppercase;letter-spacing:.06em}
.d .prow .t{font-size:17px;font-weight:700;letter-spacing:-.02em;margin-top:3px;line-height:1.2}
.d .prow .p{text-align:right}
.d .prow .p b{display:block;font-size:20px;font-weight:800;letter-spacing:-.03em}
.d .prow .p i{display:inline-block;font-style:normal;font-size:12px;font-weight:800;color:#fff;background:var(--red);border-radius:6px;padding:3px 7px;margin-top:5px}
.d .rfav{flex:0 0 auto;align-self:center;border:0;background:none;padding:6px 0 6px 12px;color:var(--low);display:flex}
.d .rfav.on{color:var(--red)}
.d .tagl{display:inline-block;font-size:11px;font-weight:800;color:var(--red);text-transform:uppercase;letter-spacing:.06em;margin-left:6px}
.d .cats{display:flex;gap:8px;overflow-x:auto;padding:0 20px 4px;margin-top:16px;scrollbar-width:none}
.d .cats::-webkit-scrollbar{display:none}
.d .cats button{flex:0 0 auto;border:0;background:var(--tint);border-radius:999px;padding:10px 16px;font-size:14px;font-weight:700;white-space:nowrap}
.d .cats button.on{background:var(--ink);color:#fff}
.d .cats button small{font-size:12px;opacity:.6;margin-left:4px}
.d .seg{display:flex;background:var(--tint);border-radius:14px;padding:4px;margin:18px 20px 0}
.d .seg button{flex:1;border:0;background:none;padding:10px 0;font-size:14px;font-weight:800;color:var(--mid);border-radius:11px}
.d .seg button.on{background:var(--paper);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.d .brands{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:14px 20px 0}
.d .bcard{border:0;background:var(--tint);border-radius:18px;padding:16px;text-align:left;display:flex;justify-content:space-between;align-items:center}
.d .bcard b{font-size:16px;font-weight:800;letter-spacing:-.02em}
.d .bcard span{font-size:12px;color:var(--mid);font-weight:700}
.d .bcard.liked{background:var(--red-soft)}
.d .more{border:1px dashed #CFCFCA;background:none;border-radius:16px;padding:14px;font-size:14px;font-weight:800;color:var(--mid);width:100%}
.d .sbar{display:flex;align-items:center;gap:10px;background:var(--tint);border-radius:16px;padding:0 16px;height:52px}
.d .sbar input{flex:1;border:0;outline:0;background:transparent;font-size:16px;color:var(--ink)}
.d .sbar input::placeholder{color:var(--low)}
.d .sicon{font-size:18px;color:var(--mid)}
.d .sx{border:0;background:none;font-size:20px;color:var(--low);padding:0 2px}
.d .back{border:0;background:none;padding:10px 20px 0;font-size:14px;font-weight:700;color:var(--mid);display:block}
.d .pcard{margin:14px 20px 0;background:var(--ink);color:#fff;border-radius:30px;padding:26px 24px 24px}
.d .pcard .brand{font-size:13px;font-weight:700;color:#9EA1A6;text-transform:uppercase;letter-spacing:.08em}
.d .pcard .t{font-size:32px;font-weight:800;letter-spacing:-.04em;line-height:1.05;margin-top:10px}
.d .pcard .pct{font-size:96px;font-weight:800;letter-spacing:-.07em;line-height:.85;color:var(--red);margin-top:28px}
.d .pcard .price{font-size:26px;font-weight:800;letter-spacing:-.03em;margin-top:14px}
.d .pcard .price s{font-size:15px;font-weight:600;color:#7D8086;margin-left:10px;letter-spacing:0}
.d .phead{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
.d .fav{flex:0 0 auto;border:0;background:rgba(255,255,255,.12);color:#fff;width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.d .fav.on{background:var(--red)}
.d .offers{padding:0 20px}
.d .offer{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:16px 0;border-bottom:1px solid var(--line)}
.d .offer:first-child{border-top:1px solid var(--line)}
.d .offer .m{font-size:16px;font-weight:800;letter-spacing:-.02em}
.d .offer .e{font-size:12px;color:var(--mid);margin-top:2px;font-weight:600}
.d .offer .r{display:flex;align-items:center;gap:12px}
.d .offer .r b{font-size:20px;font-weight:800;letter-spacing:-.03em}
.d .offer .go{border:0;background:var(--tint);border-radius:12px;padding:10px 12px;font-size:13px;font-weight:800;text-decoration:none;color:var(--ink)}
.d .offer.best .go{background:var(--red);color:#fff}
.d .offer .tag{font-size:11px;font-weight:800;color:var(--good);text-transform:uppercase;letter-spacing:.06em}
.d .follow{display:flex;justify-content:space-between;align-items:center;width:calc(100% - 40px);margin:16px 20px 0;background:var(--ink);color:#fff;border:0;border-radius:18px;padding:16px 20px;font-size:15px;font-weight:700}
.d .follow.on{background:var(--red-soft);color:var(--red)}
.d .brandhead{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin-top:10px}
.d .pill{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:4px;border:0;background:var(--tint);border-radius:20px;padding:12px 16px;min-width:76px}
.d .pill .hi{font-size:22px;line-height:1;color:var(--mid)}
.d .pill .hl{font-size:12px;font-weight:800;color:var(--mid)}
.d .pill.on{background:var(--red-soft)}
.d .pill.on .hi,.d .pill.on .hl{color:var(--red)}
.d .login{margin:20px 20px 0;background:var(--tint);border-radius:22px;padding:20px}
.d .login h3{font-size:19px;font-weight:800;letter-spacing:-.03em;margin:8px 0 0}
.d .login p{color:var(--mid);margin:8px 0 0;font-size:14px}
.d .cta{display:block;width:100%;margin-top:16px;border:0;background:var(--ink);color:#fff;border-radius:16px;padding:15px;font-size:15px;font-weight:800}
.d .cta:disabled{opacity:.5}
.d .ghost{border:0;background:none;color:var(--mid);font-size:14px;font-weight:700;padding:14px 20px;display:block}
.d .chips{display:flex;gap:8px;overflow-x:auto;padding:0 20px 2px;margin-top:14px;scrollbar-width:none}
.d .chips button{flex:0 0 auto;border:0;background:var(--red-soft);color:var(--red);border-radius:999px;padding:9px 14px;font-size:14px;font-weight:800}
.d .empty{padding:36px 20px;color:var(--mid)}
.d .err{color:var(--red);font-size:14px;font-weight:700;margin-top:10px}
.d .sheet-wrap{position:fixed;inset:0;background:rgba(16,17,18,.35);display:flex;align-items:flex-end;justify-content:center;z-index:10}
.d .sheet{width:100%;max-width:480px;background:var(--paper);border-radius:26px 26px 0 0;padding:24px 20px 32px}
.d .sheet h2{font-size:22px;font-weight:800;letter-spacing:-.03em;margin:8px 0 0;line-height:1.15}
.d .sheet p.hint{color:var(--mid);font-size:14px;margin:8px 0 0}
.d .sheet input{width:100%;margin-top:16px;border:1px solid var(--line);border-radius:14px;padding:14px;font-size:16px;color:var(--ink);outline:0}
.d .sheet input:focus{border-color:var(--ink)}
nav.d-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:480px;display:grid;grid-template-columns:repeat(3,1fr);background:var(--paper);border-top:1px solid var(--line);z-index:5;padding:8px 10px 18px}
.d-nav button{border:0;background:none;padding:10px 0;font-size:13px;font-weight:700;color:var(--low);border-radius:14px}
.d-nav button.on{color:var(--ink);background:var(--tint)}
.d .toast{position:fixed;bottom:104px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 18px;border-radius:999px;font-size:14px;font-weight:700;z-index:9;white-space:nowrap}
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
  const [view, setView] = useState(null);          // null | { kind: "item", id } | { kind: "brand", name }
  const [need, setNeed] = useState("");            // catégorie (clé API) ; "" = tout
  const [mode, setMode] = useState("cat");         // Explorer : cat | brand
  const [q, setQ] = useState("");
  const [products, setProducts] = useState(null);  // liste courante (classée par l'API)
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [moreBrands, setMoreBrands] = useState(false);
  const [item, setItem] = useState(null);          // fiche produit
  const [brandPage, setBrandPage] = useState(null);
  const [session, setSession] = useState({ checked: false, email: null });
  const [saved, setSaved] = useState(new Set());
  const [followed, setFollowed] = useState(new Set());
  const [savedList, setSavedList] = useState(null);
  const [version, setVersion] = useState(0);       // incrémenté quand le classement doit être relu (ex. marque suivie)
  const [login, setLogin] = useState(null);        // null | { message }
  const [toast, setToast] = useState(null);
  const [error, setError] = useState(null);

  const flash = t => { setToast(t); setTimeout(() => setToast(null), 2200); };
  const askLogin = message => setLogin({ message });

  // session : lue au chargement, puis relue quand l'utilisateur revient d'un lien magique ouvert dans le même navigateur
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

  // marques suivies et favoris : uniquement quand l'utilisateur est connecté
  useEffect(() => {
    if (!session.checked) return;
    if (!session.email) { setSaved(new Set()); setFollowed(new Set()); setSavedList(null); return; }
    api("follows").then(d => setFollowed(new Set(d.brands))).catch(() => {});
    api("saves").then(d => { setSavedList(d.products); setSaved(new Set(d.products.map(p => p.id))); }).catch(() => {});
  }, [session.checked, session.email, version]);

  // la liste Favoris est relue à chaque ouverture de l'onglet (un favori ajouté ailleurs doit y figurer)
  useEffect(() => {
    if (tab !== "saved" || !session.email) return;
    api("saves").then(d => setSavedList(d.products)).catch(() => {});
  }, [tab, session.email]);

  // catégories et marques : une fois
  useEffect(() => {
    api("categories").then(setCategories).catch(() => setError("Impossible de charger les catégories."));
    api("brands").then(setBrands).catch(() => {});
  }, [version]);

  // liste : aujourd'hui, ou explorer par catégorie / recherche (debounce léger sur la saisie)
  useEffect(() => {
    if (view || (tab === "explore" && mode === "brand")) return;
    const t = setTimeout(() => {
      const params = new URLSearchParams();
      if (need && tab === "explore") params.set("category", need);
      if (q.trim()) params.set("q", q.trim());
      api(`today?${params}`).then(d => { setProducts(d.products); setError(null); })
        .catch(() => setError("Impossible de charger les produits."));
    }, q ? 200 : 0);
    return () => clearTimeout(t);
  }, [tab, need, q, view, version]);

  useEffect(() => {
    if (!view) return;
    if (view.kind === "item") api(`item/${view.id}`).then(setItem).catch(() => setError("Produit introuvable."));
    if (view.kind === "brand") api(`brand/${encodeURIComponent(view.name)}`).then(setBrandPage).catch(() => setError("Marque introuvable."));
  }, [view, version]);

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

  const goTab = t => { setView(null); setItem(null); setBrandPage(null); setTab(t); if (t !== "explore") setQ(""); };

  const fav = p => <button className={`rfav ${isSaved(p.id) ? "on" : ""}`} aria-pressed={isSaved(p.id)}
    aria-label={isSaved(p.id) ? "Retirer des favoris" : "Ajouter aux favoris"} onClick={e => toggleSave(p.id, e)}>
    <Mark on={isSaved(p.id)} size={20} /></button>;

  const row = p => <div key={p.id} className="prow" role="button" tabIndex={0} onClick={() => setView({ kind: "item", id: p.id })}>
    <span><span className="brand">{p.brand}{isFollowed(p.brand) ? <span className="tagl">suivie</span> : ""}</span><div className="t">{p.title}</div></span>
    <span className="p"><b>{eur(p.price)}</b>{p.pct > 0 && <i>−{p.pct}%</i>}</span>{fav(p)}</div>;

  const searchBar = placeholder => <div className="pad" style={{ marginTop: 16 }}>
    <label className="sbar"><span className="sicon">⌕</span>
      <input value={q} onChange={e => setQ(e.target.value)} placeholder={placeholder} aria-label="Rechercher" />
      {q && <button className="sx" aria-label="Effacer" onClick={() => setQ("")}>×</button>}</label></div>;

  let body;
  if (view?.kind === "item" && item) {
    body = <>
      <button className="back" onClick={() => { setView(null); setItem(null); }}>← Retour</button>
      <div className="pcard">
        <div className="phead">
          <div><div className="brand">{item.brand} · {item.category_label}</div><div className="t">{item.title}</div></div>
          <button className={`fav ${isSaved(item.id) ? "on" : ""}`} onClick={() => toggleSave(item.id)} aria-pressed={isSaved(item.id)}
            aria-label={isSaved(item.id) ? "Retirer des favoris" : "Ajouter aux favoris"}><Mark on={isSaved(item.id)} size={22} /></button>
        </div>
        {item.pct > 0 && <div className="pct">−{item.pct}%</div>}
        <div className="price">{eur(item.price)}{item.was && <s>{eur(item.was)}</s>}</div>
      </div>
      <div className="sechead" style={{ paddingTop: 22 }}><h2>{item.offers.length > 1 ? `${item.offers.length} enseignes` : "1 enseigne"}</h2><span className="eyebrow">meilleure en premier</span></div>
      <div className="offers">
        {item.offers.map(o => <div key={o.merchant} className={`offer ${o.best ? "best" : ""}`}>
          <div><div className="m">{o.merchant}</div>{o.best && <div className="tag">Meilleure offre</div>}{o.availability !== "in_stock" && o.availability !== "unknown" && <div className="e">Indisponible</div>}</div>
          <div className="r"><b>{eur(o.price)}</b>
            <a className="go" href={o.url} target="_blank" rel="noopener noreferrer">Voir ↗</a></div></div>)}
      </div>
      {item.similar.length > 0 && <>
        <div className="sechead"><h2>Produits similaires</h2></div>
        {item.similar.map(row)}
      </>}
    </>;
  } else if (view?.kind === "brand" && brandPage) {
    const on = isFollowed(brandPage.brand);
    body = <>
      <button className="back" onClick={() => { setView(null); setBrandPage(null); }}>← Explorer</button>
      <div className="pad brandhead">
        <div><div className="eyebrow">Marque</div><h1>{brandPage.brand}</h1></div>
        <button className={`pill ${on ? "on" : ""}`} onClick={() => toggleFollow(brandPage.brand)} aria-pressed={on}>
          <span className="hi">{on ? "✓" : "+"}</span><span className="hl">{on ? "Suivie" : "Suivre"}</span></button>
      </div>
      <div className="sechead"><h2>{brandPage.products.length} produit{brandPage.products.length > 1 ? "s" : ""}</h2><span className="eyebrow">par remise</span></div>
      {brandPage.products.map(row)}
    </>;
  } else if (tab === "today") {
    const hero = !q && products && products.length ? products[0] : null;
    const rest = hero ? products.slice(1) : products || [];
    body = <>
      <div className="bar"><span className="logo">Deal<b>s</b></span><span className="clock">Aujourd'hui</span></div>
      <div className="pad" style={{ marginTop: 12 }}>
        <div className="eyebrow">Aujourd'hui</div>
        <h1>{products ? products.length : "…"} produit{products && products.length > 1 ? "s" : ""}<br />en <em>remise</em></h1>
      </div>
      {searchBar("Rechercher un produit ou une marque")}
      {hero && <button className="hero" onClick={() => setView({ kind: "item", id: hero.id })}>
        <div className="eyebrow" style={{ color: "#9EA1A6" }}>Le plus intéressant</div>
        <div className="t">{hero.brand} {hero.title}</div>
        <div className="row"><div className="price">{eur(hero.price)}</div>{hero.pct > 0 && <div className="pct">−{hero.pct}%</div>}</div>
      </button>}
      <div className="sechead"><h2>{q ? "Résultats" : "Les autres"}</h2></div>
      {products && products.length === 0 && <div className="empty">Aucun produit ne correspond.</div>}
      {rest.map(row)}
    </>;
  } else if (tab === "explore") {
    body = <>
      <div className="bar"><span className="logo">Deal<b>s</b></span><span className="clock">Explorer</span></div>
      {mode === "cat" && searchBar("Rechercher")}
      <div className="pad" style={{ marginTop: 12 }}><div className="eyebrow">Explorer</div><h1>Par <em>{mode === "cat" ? "catégorie" : "marque"}</em></h1></div>
      <div className="seg"><button className={mode === "cat" ? "on" : ""} onClick={() => setMode("cat")}>Catégorie</button>
        <button className={mode === "brand" ? "on" : ""} onClick={() => setMode("brand")}>Marque</button></div>
      {mode === "cat" && <>
        <div className="cats">
          <button className={!need ? "on" : ""} onClick={() => setNeed("")}>Tout</button>
          {categories.map(c => <button key={c.key} className={need === c.key ? "on" : ""} onClick={() => setNeed(c.key)}>{c.label}<small>{c.count}</small></button>)}
        </div>
        {(products || []).map(row)}
        {products && products.length === 0 && <div className="empty">Aucun produit dans cette sélection.</div>}
      </>}
      {mode === "brand" && <>
        <div className="brands">{(moreBrands ? brands : brands.slice(0, 6)).map(b =>
          <button key={b.name} className={`bcard ${b.followed ? "liked" : ""}`} onClick={() => setView({ kind: "brand", name: b.name })}>
            <b>{b.name}</b><span>{b.followed ? "✓" : b.count}</span></button>)}</div>
        {brands.length > 6 && <div className="pad" style={{ marginTop: 14 }}>
          <button className="more" onClick={() => setMoreBrands(!moreBrands)}>{moreBrands ? "Voir moins" : `Voir plus · ${brands.length - 6}`}</button></div>}
      </>}
    </>;
  } else {
    body = <>
      <div className="bar"><span className="logo">Deal<b>s</b></span><span className="clock">Favoris</span></div>
      <div className="pad" style={{ marginTop: 12 }}><div className="eyebrow">Favoris</div><h1>Vos <em>favoris</em></h1></div>
      {!session.checked && <div className="empty">Chargement…</div>}
      {session.checked && !session.email && <div className="login">
        <div className="eyebrow">Compte</div>
        <h3>Gardez vos favoris et vos marques.</h3>
        <p>Votre e-mail suffit. Vos choix vous suivent d'un appareil à l'autre.</p>
        <button className="cta" onClick={() => askLogin("Connectez-vous pour retrouver vos favoris")}>Me connecter</button>
      </div>}
      {session.email && <>
        <div className="sechead"><h2>Marques suivies</h2><span className="eyebrow">{followed.size}</span></div>
        {followed.size === 0 && <div className="empty" style={{ paddingTop: 0 }}>Aucune marque suivie. Ouvrez une marque depuis Explorer.</div>}
        {followed.size > 0 && <div className="chips">{[...followed].map(b =>
          <button key={b} onClick={() => { setTab("explore"); setMode("brand"); setView({ kind: "brand", name: b }); }}>{b}</button>)}</div>}
        <div className="sechead"><h2>Produits</h2><span className="eyebrow">{savedList ? savedList.length : 0}</span></div>
        {savedList && savedList.length === 0 && <div className="empty" style={{ paddingTop: 0 }}>Rien pour l'instant. Touchez le signet sur un produit.</div>}
        {(savedList || []).map(row)}
        <button className="ghost" onClick={logout}>Se déconnecter</button>
      </>}
    </>;
  }

  return <div className="d"><style>{CSS}</style><div className="app">
    {error && <div className="empty">{error}</div>}
    {body}
    <nav className="d-nav" aria-label="Navigation">{[["today", "Aujourd'hui"], ["explore", "Explorer"], ["saved", "Favoris"]].map(([k, l]) =>
      <button key={k} className={tab === k ? "on" : ""} aria-current={tab === k ? "page" : undefined} onClick={() => goTab(k)}>{l}</button>)}</nav>
    {login && <LoginSheet message={login.message} onClose={() => setLogin(null)}
      onDone={() => { setLogin(null); refreshSession(); setVersion(v => v + 1); }} />}
    <Toast text={toast} />
  </div></div>;
}
