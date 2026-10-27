"""Ontologie : ce que l'app sait d'un domaine de produits, en DONNÉES versionnées (un fichier JSON par domaine,
`aspirateurs.json`), séparées du code qui s'en sert. Quatre niveaux, comme dans la note de vision :

  taxonomie            le chemin du domaine (Maison › Entretien › Aspirateurs), ses catégories, ses sous-familles (robot,
                       laveur, à main, balai, traîneau) et la règle qui range un produit dans l'une d'elles — dans l'ordre :
                       la première qui convient (un « balai laveur » est un laveur)
  ontologie du domaine les caractéristiques (poids, autonomie, filtre HEPA…) : type, unité, comment les lire sur la fiche
                       de l'enseigne (noms déclarés, formats variés) ou dans le titre (le nom du modèle, « Animal », est un
                       indice plus faible), ce qu'un type entraîne (un robot est sans fil) et ce qui se déduit (une
                       autonomie : sur batterie) — une déduction est dite comme telle, jamais rangée comme un fait
  modèle de décision   les critères (maniabilité, couverture, poils…) calculés à partir des caractéristiques, par
                       sous-famille : 1 (oui), 0,5 (en partie), 0 (non) ou inconnu ; les besoins (« un chat », « des
                       allergies ») qui demandent des critères — fort, faiblement, ou sans exception (éliminatoire) ; les
                       questions à poser quand le besoin est vague
  offres et décision   ailleurs : le moteur de parcours (journey.py) applique ces règles aux produits publiés et à leurs
                       prix.

Un fait inconnu reste inconnu (ni oui ni non) ; chaque fait garde sa source (fiche, titre, nom du modèle) et la version
de l'ontologie qui l'a lu. Une ontologie est relue au chargement (`check`) : une référence fausse, une expression
illisible ou un mot réclamé deux fois l'empêchent de servir (tests/test_ontology.py).
"""
import json
import re
from pathlib import Path

from ..extract.categories import plain

HERE = Path(__file__).resolve().parent
SCHEMA = 1
WEIGHTS = {"fort": 1.0, "faible": 0.35, "eliminatoire": 1.0}
SOURCES = ("fiche", "titre", "nom", "deduit", "type")      # du plus sûr au moins sûr
SCORES = (0, 0.5, 1)
UNKNOWN_SCORE = 0.25                                       # un critère inconnu : mieux qu'un non, moins qu'un « en partie »
YES = {"oui", "yes", "true", "1", "avec", "inclus", "incluse", "present", "presente", "x"}
NO = {"non", "no", "false", "0", "sans", "absent", "absente", "aucun", "aucune"}
NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


class OntologyError(ValueError):
    pass


def text(s):
    """Le texte comparé : sans accents, minuscules, tirets lus comme des espaces (« 2-en-1 » = « 2 en 1 »)."""
    return " ".join(plain(s).replace("-", " ").replace("²", "2").split())


def name_key(s):
    """Un nom de caractéristique déclaré : « Poids (kg) » → « poids », « Brosse anti-enchevêtrement » → « brosse anti
    enchevetrement »."""
    s = re.sub(r"\([^)]*\)", " ", plain(s))
    return " ".join(re.sub(r"[^a-z0-9']+", " ", s).split())


def number(s):
    m = NUM.search(s or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return int(v) if v.is_integer() else v


def show(v, prop=None):
    """Une valeur dite : 2.3 → « 2,3 », « laser » → « laser » (le libellé de l'énumération)."""
    if prop is not None and prop.get("type") == "enum":
        return prop["values"].get(v, v)
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return str(v)


class Domain:
    def __init__(self, data, source="?"):
        check(data, source)
        self.data, self.source = data, source
        self.key, self.version, self.label, self.one = data["domain"], data["version"], data["label"], data["one"]
        self.path, self.categories = list(data["path"]), tuple(data["categories"])
        self.subs = data["subfamilies"]
        self.sub = {s["key"]: s for s in self.subs}
        self.props = {p["key"]: p for p in data["properties"]}
        self.criteria = {c["key"]: c for c in data["criteria"]}
        self.needs = {n["key"]: n for n in data["needs"]}
        self.questions = data["questions"]
        self.infer = data.get("infer", [])
        self.drops = set(data.get("drops", ()))
        self._fiche = {}                                   # nom déclaré → [(caractéristique, règle)]
        for p in data["properties"]:
            for rule in p.get("fiche", ()):
                for n in rule["names"]:
                    self._fiche.setdefault(name_key(n), []).append((p["key"], rule))
        self._titre = [(p["key"], re.compile(r["re"]), r) for p in data["properties"] for r in p.get("titre", ())]
        self._subre = [[re.compile(a["title"]) if "title" in a else None for a in s["match"].get("any", ())] for s in self.subs]
        # La langue du domaine : (expression, nature, ce qu'elle dit), les plus longues d'abord
        lex = [(w, "domain", None) for w in data.get("words", ())]
        lex += [(w, "sub", s["key"]) for s in self.subs for w in s.get("words", ())]
        lex += [(w, "need", n["key"]) for n in data["needs"] for w in n["words"]]
        lex += [(w, "prop", (p["key"], v)) for p in data["properties"] for w, v in (p.get("words") or {}).items()]
        lex += [(w, "filler", None) for w in data.get("fillers", ())]
        self._lex = [(re.compile(rf"(?<!\w){re.escape(w)}(?!\w)"), w, kind, what) for w, kind, what in sorted(lex, key=lambda e: -len(e[0]))]
        self._surface = re.compile(r"(?<!\d)(\d{2,4})\s*(?:m2|m\s2|metres? carres?)(?!\w)")

    # ------------------------------------------------------------------ taxonomie
    def sub_of(self, category, title, attrs):
        """La sous-famille d'un produit : la première dont la règle convient (catégorie, puis un mot du titre, une
        fonction, ou un fait lu) ; None si aucune (le produit reste dans le domaine, sans type)."""
        t = text(title)
        for s, res in zip(self.subs, self._subre):
            m = s["match"]
            if category not in m["category"]:
                continue
            anys = m.get("any")
            if not anys:
                return s["key"]
            for a, rx in zip(anys, res):
                if rx is not None and rx.search(t) or "feature" in a and a["feature"] in (attrs.get("features") or ()) \
                        or "fact" in a and all(attrs.get(k) == v for k, v in a["fact"].items()):
                    return s["key"]
        return None

    def category_of(self, sub):
        return self.sub[sub]["match"]["category"][0]

    def owns(self, key):
        """Une clé que l'ontologie lit elle-même (ses caractéristiques, la sous-famille, la provenance)."""
        return key in self.props or key in ("sub", "_src", "_v")

    # ------------------------------------------------------------------ lire une page
    def read(self, title, props=None):
        """La fiche (déclarée par l'enseigne, prioritaire) puis le titre → ({caractéristique: valeur}, {caractéristique:
        source}). Une valeur hors de sa plage, ou sans l'unité exigée, n'est pas lue."""
        vals, src = {}, {}
        for name, value in (props or {}).items():
            for key, rule in self._fiche.get(name_key(name), ()):
                if key in vals:
                    continue
                v = self._parse(self.props[key], rule, value)
                if v is not None:
                    vals[key], src[key] = v, "fiche"
        t = text(title)
        for key, rx, rule in self._titre:
            if key in vals:
                continue
            m = rx.search(t)
            if not m:
                continue
            v = rule["value"] if "value" in rule else self._ranged(self.props[key], number(m.group(1)))
            if v is not None:
                vals[key], src[key] = v, rule.get("src", "titre")
        return vals, src

    def _parse(self, prop, rule, value):
        raw = plain(str(value)).strip()
        how = rule["value"]
        if how == "yesno":
            word = re.sub(r"[^a-z0-9]+", " ", raw).strip()
            return True if word in YES else False if word in NO else None
        if how == "number":
            units = rule.get("units")
            if units:
                unit = next((u for u in sorted(units, key=len, reverse=True) if re.search(rf"\d\s*{re.escape(u)}\b", raw)), None)
                if unit is None and rule.get("unit_required"):
                    return None
                factor = units.get(unit, 1) if unit else 1
            else:
                factor = 1
            v = number(raw)
            return self._ranged(prop, None if v is None else round(v * factor, 3))
        for out, rx in how.items():                        # une table : « true », « false », ou les valeurs d'une énumération
            if re.search(rx, raw):
                return True if out == "true" else False if out == "false" else out
        return None

    @staticmethod
    def _ranged(prop, v):
        if v is None:
            return None
        lo, hi = prop.get("range", (None, None))
        if lo is not None and not lo <= v <= hi:
            return None
        return int(v) if isinstance(v, float) and v.is_integer() else v

    # ------------------------------------------------------------------ faits et déductions
    def facts(self, attrs):
        """{caractéristique: (valeur, source)} d'un produit : ses faits (attrs et leur provenance, _src), puis ce que son
        type entraîne (source « type »), puis les déductions (source « deduit ») — jamais à la place d'un fait."""
        attrs = attrs or {}
        src = attrs.get("_src") or {}
        out = {k: (attrs[k], src.get(k, "titre")) for k in self.props if attrs.get(k) is not None}
        sub = attrs.get("sub")
        for k, v in (self.sub[sub].get("implies") or {}).items() if sub in self.sub else ():
            out.setdefault(k, (v, "type"))
        for rule in self.infer:
            if self.holds(rule["if"], sub, out) is True:
                for k, v in rule["then"].items():
                    out.setdefault(k, (v, "deduit"))
        return out

    def holds(self, cond, sub, facts):
        """Une condition de règle : True, False, ou None (indéterminée : une caractéristique inconnue, un type inconnu).
        Valeurs : true/false ou une valeur (égale), une liste (l'une d'elles), {min, max}, null (inconnue), « known »."""
        state = True
        for k, want in cond.items():
            if k == "sub":
                r = None if sub is None else sub in want
            else:
                have = facts.get(k)
                v = have[0] if have else None
                if want is None:
                    r = v is None
                elif want == "known":
                    r = v is not None
                elif v is None:
                    r = None
                elif isinstance(want, dict):
                    r = (want.get("min") is None or v >= want["min"]) and (want.get("max") is None or v <= want["max"])
                elif isinstance(want, list):
                    r = v in want
                else:
                    r = v == want
            if r is False:
                return False
            if r is None:
                state = None
        return state

    def judge(self, key, sub, facts):
        """Un critère pour un produit (sa sous-famille, ses faits) → (score 1 | 0,5 | 0 | None, ce qui le dit, source,
        impossible, au mieux). La première règle vraie décide ; aucune vraie mais une indéterminée : inconnu (ni oui ni
        non), et « au mieux » dit le score que les règles indéterminées permettent encore (un produit dont la fiche dit
        « pas de brosse pour les poils » ne peut plus valoir qu'« en partie » : il passe après celui dont on ne sait rien)."""
        c = self.criteria[key]
        open_, top_lost = [], False
        for rule in c["rules"]:
            h = self.holds(rule["if"], sub, facts)
            if h is True:
                return rule["score"], self._say(rule["say"], facts), self._source(rule["if"], facts), bool(rule.get("impossible")), rule["score"]
            if h is None:
                open_.append(rule)
            elif rule["score"] == 1 and not open_ and ("sub" not in rule["if"] or sub in rule["if"]["sub"]):
                top_lost = True                            # la meilleure règle, pour ce type, est exclue par un fait connu
        if open_:
            best = max(r["score"] for r in open_)
            said = next((r["unknown"] for r in open_ if r.get("unknown")), None) if top_lost else None
            return None, said or c["unknown"], None, False, best
        used = {k for r in c["rules"] for k in r["if"] if k != "sub"}
        return 0, self._say(c["no"], facts), self._source({k: 1 for k in used if k in facts}, facts), False, 0

    def _say(self, template, facts):
        return re.sub(r"\{(\w+)\}", lambda m: show(facts[m.group(1)][0], self.props.get(m.group(1))) if m.group(1) in facts else "?", template)

    @staticmethod
    def _source(cond, facts):
        """La source d'un verdict : la moins sûre des caractéristiques qu'il lit ; « type » s'il ne lit que la sous-famille."""
        srcs = [facts[k][1] for k in cond if k != "sub" and k in facts]
        return max(srcs, key=SOURCES.index) if srcs else "type"

    # ------------------------------------------------------------------ comprendre une phrase
    def understand(self, t):
        """Une phrase (texte simple, `text`) → {sub, needs: [(besoin, mots)], props: {caractéristique: valeur}, said: mots
        expliqués, domain: le domaine est-il nommé}. Les expressions les plus longues d'abord ; un mot pris n'est plus
        repris (« auto-vidage » n'est pas la voiture)."""
        out = {"sub": None, "needs": [], "props": {}, "said": set(), "domain": False}
        found, subs, said_subs = {}, [], {}
        m = self._surface.search(t)
        if m:
            area = int(m.group(1))
            key = next((n["key"] for n in self.needs.values() if area >= n.get("surface_min", 10 ** 9) or area <= n.get("surface_max", -1)), None)
            if key:
                found.setdefault(key, [m.start()]).append(m.group(0))
            out["said"] |= set(m.group(0).split())
            t = t[:m.start()] + " " * len(m.group(0)) + t[m.end():]
        for rx, w, kind, what in self._lex:
            hit = rx.search(t)
            if not hit:
                continue
            t = rx.sub(lambda x: " " * len(x.group(0)), t)
            out["said"] |= set(re.split(r"[\s']+", w))
            if kind == "domain":
                out["domain"] = True
            elif kind == "sub":
                subs.append(what)
                said_subs.setdefault(what, (w, hit.start()))
            elif kind == "need":
                found.setdefault(what, [hit.start()]).append(w)
                found[what][0] = min(found[what][0], hit.start())
            elif kind == "prop":
                out["props"].setdefault(what[0], what[1])
        if subs:                                           # deux types nommés : le plus spécifique (l'ordre des sous-familles) ;
            order = [s["key"] for s in self.subs]          # l'autre dit ce qu'il demande (« robot laveur » : un robot qui lave)
            subs.sort(key=order.index)
            out["sub"] = subs[0]
            for other in subs[1:]:
                for k in (self.sub[other].get("with") or {}).get("needs", ()):
                    w, at = said_subs[other]
                    found.setdefault(k, [at]).append(w)
        out["needs"] = [(k, v[1:]) for k, v in sorted(found.items(), key=lambda kv: kv[1][0])]   # dans l'ordre de la phrase
        return out


def check(d, source="?"):
    """Relit une ontologie avant de s'en servir : schéma, références (sous-familles, caractéristiques, critères), règles
    lisibles, scores permis, mots réclamés une seule fois. → OntologyError à la première faute, avec où elle est."""
    def fail(msg):
        raise OntologyError(f"{source} : {msg}")
    for k in ("schema", "domain", "version", "label", "one", "path", "categories", "subfamilies", "properties", "criteria", "needs", "questions"):
        if k not in d:
            fail(f"« {k} » manque")
    if d["schema"] != SCHEMA:
        fail(f"schéma {d['schema']} inconnu (attendu : {SCHEMA})")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(d["version"])):
        fail("version : trois nombres (1.0.0)")
    props = {}
    for p in d["properties"]:
        k = p.get("key")
        if not k or k in props:
            fail(f"caractéristique sans clé ou en double : {k}")
        if p.get("type") not in ("bool", "number", "enum"):
            fail(f"{k} : type inconnu")
        if p["type"] == "number" and not (isinstance(p.get("range"), list) and len(p["range"]) == 2):
            fail(f"{k} : une plage [min, max] est requise")
        if p["type"] == "enum" and not p.get("values"):
            fail(f"{k} : les valeurs de l'énumération manquent")
        for r in p.get("fiche", ()):
            if not r.get("names") or "value" not in r:
                fail(f"{k} : règle de fiche sans noms ou sans valeur")
            if isinstance(r["value"], dict):
                for out, rx in r["value"].items():
                    if p["type"] == "enum" and out not in p["values"] or p["type"] == "bool" and out not in ("true", "false"):
                        fail(f"{k} : valeur « {out} » inconnue")
                    _compile(rx, fail, k)
            elif r["value"] not in ("yesno", "number"):
                fail(f"{k} : lecture « {r['value']} » inconnue")
        for r in p.get("titre", ()):
            rx = _compile(r.get("re", ""), fail, k)
            if "value" not in r and rx.groups < 1:
                fail(f"{k} : une expression de titre sans valeur doit capturer un nombre")
            if r.get("src", "titre") not in SOURCES:
                fail(f"{k} : source inconnue")
        props[k] = p
    subs = {}
    for s in d["subfamilies"]:
        k = s.get("key")
        if not k or k in subs:
            fail(f"sous-famille sans clé ou en double : {k}")
        if not set(s["match"].get("category", ())) <= set(d["categories"]) or not s["match"].get("category"):
            fail(f"{k} : catégorie hors du domaine")
        for a in s["match"].get("any", ()):
            if "title" in a:
                _compile(a["title"], fail, k)
            for x in (a.get("fact") or {}):
                if x not in props:
                    fail(f"{k} : caractéristique inconnue « {x} »")
        for x in list(s.get("implies") or {}) + list(s.get("decision") or ()):
            if x not in props:
                fail(f"{k} : caractéristique inconnue « {x} »")
        if set(s.get("with") or {}) - {"needs"} or not set((s.get("with") or {}).get("needs", ())) <= {n.get("key") for n in d["needs"]}:
            fail(f"{k} : « with » ne dit que des besoins connus")
        subs[k] = s
    for r in d.get("infer", ()):
        for x in list(r["if"]) + list(r["then"]):
            if x not in props:
                fail(f"déduction : caractéristique inconnue « {x} »")
    crits = {}
    for c in d["criteria"]:
        k = c.get("key")
        if not k or k in crits:
            fail(f"critère sans clé ou en double : {k}")
        for x in ("label", "rules", "no", "unknown"):
            if x not in c:
                fail(f"{k} : « {x} » manque")
        for r in c["rules"]:
            if r.get("score") not in SCORES:
                fail(f"{k} : score {r.get('score')} interdit (0, 0,5 ou 1)")
            for x, want in r["if"].items():
                if x == "sub":
                    if not set(want) <= set(subs):
                        fail(f"{k} : sous-famille inconnue dans {want}")
                elif x not in props:
                    fail(f"{k} : caractéristique inconnue « {x} »")
            for x in re.findall(r"\{(\w+)\}", r["say"]):
                if x not in r["if"]:
                    fail(f"{k} : « {{{x}}} » dit une valeur que la règle ne lit pas")
        for x in re.findall(r"\{(\w+)\}", c["no"]):
            if x not in props:
                fail(f"{k} : « {{{x}}} » inconnu")
        crits[k] = c
    words, needs = {}, set()
    claim = lambda w, who: fail(f"« {w} » est déjà pris par {words[w]}") if w in words else words.__setitem__(w, who)
    for w in d.get("words", ()):
        claim(w, "le domaine")
    for s in d["subfamilies"]:
        for w in s.get("words", ()):
            claim(w, s["key"])
    for n in d["needs"]:
        k = n.get("key")
        if not k or k in needs:
            fail(f"besoin sans clé ou en double : {k}")
        if not n.get("words") or not n.get("criteria") and not n.get("context"):
            fail(f"{k} : des mots et des critères sont requis (ou « context » : un besoin dit, sans critère)")
        for c, w in n["criteria"].items():
            if c not in crits or w not in WEIGHTS:
                fail(f"{k} : critère « {c} » ou poids « {w} » inconnu")
        if not set(n.get("hint", ())) <= set(subs):
            fail(f"{k} : sous-famille suggérée inconnue")
        for w in n["words"]:
            claim(w, k)
        needs.add(k)
    for p in d["properties"]:
        for w in (p.get("words") or {}):
            claim(w, p["key"])
    for w in d.get("fillers", ()):
        claim(w, "les mots sans critère")
    for q in d["questions"]:
        if q.get("when") not in ("sub", "need"):
            fail(f"question {q.get('key')} : « when » vaut sub ou need")
        for o in q["options"]:
            a = o.get("apply") or {}
            if set(a) - {"sub", "need"} or a.get("sub", next(iter(subs))) not in subs or a.get("need", next(iter(needs))) not in needs:
                fail(f"question {q.get('key')} : réponse « {o.get('label')} » inconnue")
    return True


def _compile(rx, fail, where):
    try:
        return re.compile(rx)
    except re.error as e:
        fail(f"{where} : expression illisible « {rx} » ({e})")


def load(folder=HERE):
    """Les domaines d'un dossier (un fichier JSON chacun) : {clé: Domain}."""
    out = {}
    for f in sorted(Path(folder).glob("*.json")):
        d = Domain(json.loads(f.read_text(encoding="utf-8")), f.name)
        out[d.key] = d
    return out


DOMAINS = load()
BY_CATEGORY = {c: d for d in DOMAINS.values() for c in d.categories}


def domain_of(category):
    """Le domaine d'une catégorie (« robot_aspirateur » → aspirateurs), ou None : la catégorie n'a pas encore d'ontologie."""
    return BY_CATEGORY.get(category)


def detect(t):
    """Le domaine qu'une phrase nomme sans nommer de catégorie (« balai pour chat », « robot qui se vide tout seul »)."""
    for d in DOMAINS.values():
        u = d.understand(t)
        if u["domain"] or u["sub"]:
            return d
    return None
