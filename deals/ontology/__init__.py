"""Ontologie : ce qu'est un produit, rayon par rayon, en DONNÉES versionnées — un fichier JSON par famille
(electromenager.json, electronique.json, ameublement.json, literie.json), séparé du code qui s'en sert. Trois niveaux,
pas plus :

  catégorie          le rayon (lave-linge, téléviseurs…) ; un domaine en réunit parfois plusieurs (les aspirateurs :
                     aspirateur et robot aspirateur)
  sous-catégorie     les types (hublot, top ; OLED, QLED…) et la règle qui range une offre dans l'un d'eux — dans l'ordre :
                     le premier qui convient (un « balai laveur » est un laveur) ; ce qu'un type est par définition (un
                     robot est sans fil et sans sac)
  attributs          un ou deux par rayon : oui ou non (sans fil, No Frost : des expressions écrites ici), ou une mesure
                     (capacité, taille d'écran : lue par l'extracteur, extract.categories, comparée selon sa règle, query)

Tout se lit dans ce que donnent les flux affiliés et les API des enseignes : le titre de l'offre et sa catégorie déclarée
(« Électroménager > Lave-linge > Lave-linge hublot »). Rien n'est rédigé ni deviné : un attribut que l'offre ne dit pas
reste inconnu. Une ontologie est relue au chargement (`check`) : une référence fausse, une expression illisible, un mot
réclamé deux fois dans un rayon ou un rayon décrit deux fois l'empêchent de servir (tests/test_ontology.py).
"""
import json
import re
from pathlib import Path

from ..extract.categories import FAMILY_OF, MEASURES, plain

HERE = Path(__file__).resolve().parent
SCHEMA = 3
KINDS = ("bool", "measure")
COMPARE = ("more", "same", "less")      # une alternative : oui est un plus (par défaut), une forme, oui est un moins


class OntologyError(ValueError):
    pass


def text(s):
    """Le texte comparé : sans accents, minuscules, tirets lus comme des espaces (« sans-fil » = « sans fil »)."""
    return " ".join(plain(s).replace("-", " ").split())


LISTING = re.compile(r"\s(?:et|ou)\s|[,&+]")


def parts(title, declared=None):
    """Ce qu'on lit d'une offre : son titre, puis chaque niveau de sa catégorie déclarée (« Aspirateur > Aspirateur
    balai » : « aspirateur », « aspirateur balai ») — sauf un niveau qui en nomme plusieurs (« Commodes et chiffonniers »,
    « Casques et écouteurs », « Aspirateurs avec ou sans sac ») : il ne dit pas lequel est l'offre."""
    levels = [text(x) for x in re.split(r"[>/|»›]", declared or "") if x.strip()]
    return [text(title)] + [x for x in levels if not LISTING.search(x)]


class Domain:
    """Un rayon (ou quelques rayons) et ce qu'en dit l'ontologie : ses types, ses attributs, sa langue."""

    def __init__(self, data, family="?", version="0.0.0", source="?"):
        check_domain(data, lambda msg: _raise(f"{source} : {data.get('domain', '?')} : {msg}"))
        self.data, self.source, self.family, self.version = data, source, family, version
        self.key, self.label, self.one = data["domain"], data["label"], data["one"]
        self.categories = tuple(data["categories"])
        self.subs = data.get("subcategories", [])
        self.sub = {s["key"]: s for s in self.subs}
        self.attrs = {a["key"]: a for a in data["attributes"]}
        self.bools = [k for k, a in self.attrs.items() if a["kind"] == "bool"]
        self.measures = [k for k, a in self.attrs.items() if a["kind"] == "measure"]
        self.drops = set(data.get("drops", ()))
        self._text = [(a["key"], re.compile(r["re"]), r["value"]) for a in data["attributes"] if a["kind"] == "bool" for r in a["text"]]
        self._subre = [[re.compile(x["text"]) for x in s["match"].get("any", ())] for s in self.subs]
        # La langue du rayon : (expression, nature, ce qu'elle dit), les plus longues d'abord
        lex = [(w, "domain", None) for w in data.get("words", ())]
        lex += [(w, "sub", s["key"]) for s in self.subs for w in s.get("words", ())]
        lex += [(w, "attr", (a["key"], v)) for a in data["attributes"] if a["kind"] == "bool" for w, v in (a.get("words") or {}).items()]
        self._lex = [(re.compile(rf"(?<!\w){re.escape(w)}(?!\w)"), w, kind, what) for w, kind, what in sorted(lex, key=lambda e: -len(e[0]))]

    def category_of(self, sub):
        """Le rayon d'une sous-catégorie (robot → robot_aspirateur)."""
        return self.sub[sub]["match"]["category"][0]

    def owns(self, key):
        """Une clé que l'ontologie lit elle-même dans l'offre (le type, les attributs oui/non) : jamais gardée d'avant."""
        return key == "sub" or key in self.bools

    def attributes_of(self, sub=None):
        """Les attributs à proposer (Affiner) : ceux du type choisi (tous, s'il n'en dit pas) ; sans type, ceux de deux types
        au moins (tous, si le rayon a moins de deux types)."""
        every = list(self.attrs)
        if sub in self.sub:
            return list(self.sub[sub].get("attributes", every))
        if len(self.subs) < 2:
            return every
        n = {k: sum(k in s.get("attributes", every) for s in self.subs) for k in every}
        return [k for k in every if n[k] >= 2]

    def sub_of(self, category, title, declared=None):
        """La sous-catégorie d'une offre : la première dont la règle convient (sa catégorie, puis un mot de son titre ou
        d'un niveau de sa catégorie déclarée) ; None si rien ne la dit (le produit reste dans le rayon, sans type)."""
        texts = parts(title, declared)
        for s, res in zip(self.subs, self._subre):
            if category not in s["match"]["category"]:
                continue
            if not res or any(rx.search(t) for rx in res for t in texts):
                return s["key"]
        return None

    def read(self, title, declared=None):
        """Les attributs oui/non que l'offre dit (son titre, puis sa catégorie déclarée) → {attribut: True | False}."""
        vals = {}
        for t in parts(title, declared):
            for key, rx, value in self._text:
                if key not in vals and rx.search(t):
                    vals[key] = value
        return vals

    def facts(self, attrs):
        """{attribut oui/non: valeur} d'un produit : ce que son offre dit, puis ce que son type est par définition (un robot
        est sans fil) — jamais à la place de ce que l'offre dit."""
        attrs = attrs or {}
        out = {k: attrs[k] for k in self.bools if attrs.get(k) is not None}
        for k, v in (self.sub.get(attrs.get("sub")) or {}).get("implies", {}).items():
            out.setdefault(k, v)
        return out

    def understand(self, t):
        """Une phrase (texte simple, `text`) → {sub, props: {attribut: valeur}, said: mots expliqués, domain: le rayon est-il
        nommé, named: la plus longue expression du rayon ou d'un type reconnue}. Les expressions les plus longues d'abord ;
        un mot pris n'est plus repris ; deux types nommés : le plus précis (l'ordre des sous-catégories) ; un attribut dit
        deux fois : le premier dit, comme dans une offre."""
        out = {"sub": None, "props": {}, "said": set(), "domain": False, "named": ""}
        subs, props = [], []
        for rx, w, kind, what in self._lex:
            m = rx.search(t)
            if not m:
                continue
            t = rx.sub(lambda x: " " * len(x.group(0)), t)       # même longueur : les positions restent justes
            out["said"] |= set(re.split(r"[\s']+", w))
            if kind in ("domain", "sub") and len(w) > len(out["named"]):
                out["named"] = w
            if kind == "domain":
                out["domain"] = True
            elif kind == "sub":
                subs.append(what)
            else:
                props.append((m.start(), what))
        for _, (k, v) in sorted(props):
            out["props"].setdefault(k, v)
        if subs:
            out["sub"] = min(subs, key=[s["key"] for s in self.subs].index)
        return out


def _raise(msg):
    raise OntologyError(msg)


def check(f, source="?"):
    """Relit le fichier d'une famille avant de s'en servir : schéma, famille suivie, version, et chacun de ses rayons
    (check_domain). → OntologyError à la première faute, avec où elle est."""
    def fail(msg):
        raise OntologyError(f"{source} : {msg}")
    for k in ("schema", "family", "label", "version", "domains"):
        if k not in f:
            fail(f"« {k} » manque")
    if f["schema"] != SCHEMA:
        fail(f"schéma {f['schema']} inconnu (attendu : {SCHEMA})")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(f["version"])):
        fail("version : trois nombres (3.0.0)")
    for d in f["domains"]:
        check_domain(d, lambda msg, d=d: fail(f"{d.get('domain', '?')} : {msg}"))
        for c in d["categories"]:
            if FAMILY_OF.get(c) != f["family"]:
                fail(f"{d['domain']} : le rayon « {c} » n'est pas un rayon suivi de la famille {f['family']}")
    return True


def check_domain(d, fail):
    """Un rayon : ses champs, ses attributs (oui/non : expressions lisibles qui disent oui ou non ; mesure : une mesure que
    l'extracteur sait lire), ses types (rayon du domaine, expressions lisibles, ce qu'ils sont par définition et les
    attributs qu'ils proposent : des attributs du rayon), des mots réclamés une seule fois."""
    for k in ("domain", "label", "one", "categories", "attributes"):
        if k not in d:
            fail(f"« {k} » manque")
    if not d["categories"]:
        fail("aucun rayon")
    attrs = {}
    for a in d["attributes"]:
        k = a.get("key")
        if not k or k in attrs:
            fail(f"attribut sans clé ou en double : {k}")
        if a.get("kind") not in KINDS:
            fail(f"{k} : « kind » vaut bool ou measure")
        if not a.get("label"):
            fail(f"{k} : « label » manque")
        if a["kind"] == "measure" and k not in MEASURES:
            fail(f"{k} : une mesure que l'extracteur ne sait pas lire")
        if a["kind"] == "bool":
            if not a.get("yes") or not a.get("no") or not a.get("text"):
                fail(f"{k} : « yes », « no » et « text » sont requis")
            for r in a["text"]:
                _compile(r.get("re", ""), fail, k)
                if not isinstance(r.get("value"), bool):
                    fail(f"{k} : une expression dit oui (true) ou non (false)")
            for w, v in (a.get("words") or {}).items():
                if not isinstance(v, bool):
                    fail(f"{k} : le mot « {w} » dit oui (true) ou non (false)")
            if a.get("compare", "more") not in COMPARE:
                fail(f"{k} : « compare » vaut more, same ou less")
        attrs[k] = a["kind"]
    subs = set()
    for s in d.get("subcategories", ()):
        k = s.get("key")
        if not k or k in subs:
            fail(f"sous-catégorie sans clé ou en double : {k}")
        for f in ("label", "plural", "one"):
            if not s.get(f):
                fail(f"{k} : « {f} » manque")
        if not s.get("match", {}).get("category") or not set(s["match"]["category"]) <= set(d["categories"]):
            fail(f"{k} : catégorie hors du domaine")
        for x in s["match"].get("any", ()):
            if not x.get("text"):
                fail(f"{k} : une règle « any » dit un texte")
            _compile(x["text"], fail, k)
        for y, v in (s.get("implies") or {}).items():
            if attrs.get(y) != "bool" or not isinstance(v, bool):
                fail(f"{k} : attribut inconnu « {y} »" if y not in attrs else f"{k} : « {y} » est entraîné par oui ou non")
        for y in s.get("attributes", ()):
            if y not in attrs:
                fail(f"{k} : attribut inconnu « {y} »")
        subs.add(k)
    words = {}
    for who, ws in [("le domaine", d.get("words", ()))] + [(s["key"], s.get("words", ())) for s in d.get("subcategories", ())] + \
            [(a["key"], a.get("words") or {}) for a in d["attributes"]]:
        for w in ws:
            if w in words:
                fail(f"« {w} » est déjà pris par {words[w]}")
            words[w] = who


def _compile(rx, fail, where):
    try:
        return re.compile(rx)
    except re.error as e:
        fail(f"{where} : expression illisible « {rx} » ({e})")


def load(folder=HERE):
    """Les familles d'un dossier (un fichier JSON chacune) → ({clé de domaine: Domain}, {famille: (libellé, version)}).
    Un rayon décrit deux fois, ou un domaine en double : OntologyError."""
    domains, families, seen = {}, {}, {}
    for path in sorted(Path(folder).glob("*.json")):
        f = json.loads(path.read_text(encoding="utf-8"))
        check(f, path.name)
        families[f["family"]] = (f["label"], f["version"])
        for data in f["domains"]:
            d = Domain(data, f["family"], f["version"], path.name)
            if d.key in domains:
                raise OntologyError(f"{path.name} : le domaine « {d.key} » est déjà décrit")
            for c in d.categories:
                if c in seen:
                    raise OntologyError(f"{path.name} : le rayon « {c} » est déjà décrit par {seen[c]}")
                seen[c] = d.key
            domains[d.key] = d
    return domains, families


DOMAINS, FAMILIES = load()
BY_CATEGORY = {c: d for d in DOMAINS.values() for c in d.categories}


def domain_of(category):
    """Le domaine d'une catégorie (« robot_aspirateur » → aspirateurs), ou None : la catégorie n'a pas d'ontologie."""
    return BY_CATEGORY.get(category)


def detect(t):
    """Le domaine qu'une phrase nomme sans nommer de rayon (« balai sans fil », « hublot 9 kg ») : celui qui en reconnaît
    l'expression la plus longue (« plaques mixtes » : une plaque, pas une cuisinière) ; à égalité (« encastrable » : un four
    ou un lave-vaisselle) ou aucun : None."""
    found = sorted(((len(u["named"]), d) for d in DOMAINS.values() for u in [d.understand(t)] if u["domain"] or u["sub"]),
                   key=lambda x: -x[0])
    return found[0][1] if found and (len(found) == 1 or found[0][0] > found[1][0]) else None
