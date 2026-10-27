"""Ontologie : ce qu'est un produit d'un domaine, en DONNÉES versionnées (un fichier JSON par domaine, `aspirateurs.json`),
séparées du code qui s'en sert. Trois niveaux, pas plus :

  catégorie          le domaine et ses rayons (Aspirateurs : aspirateur, robot aspirateur)
  sous-catégorie     les types (robot, laveur, à main, balai, traîneau) et la règle qui range un produit dans l'un d'eux —
                     dans l'ordre : le premier qui convient (un « balai laveur » est un laveur) ; ce qu'un type est par
                     définition (un robot est sans fil et sans sac)
  attributs          deux, pas plus : sans fil, sans sac

Tout se lit dans ce que donnent les flux affiliés et les API des enseignes : le titre de l'offre et sa catégorie déclarée
(« Électroménager > Aspirateur > Aspirateur balai »). Rien n'est rédigé ni deviné : un attribut que l'offre ne dit pas
reste inconnu. Une ontologie est relue au chargement (`check`) : une référence fausse, une expression illisible ou un mot
réclamé deux fois l'empêchent de servir (tests/test_ontology.py).
"""
import json
import re
from pathlib import Path

from ..extract.categories import plain

HERE = Path(__file__).resolve().parent
SCHEMA = 2


class OntologyError(ValueError):
    pass


def text(s):
    """Le texte comparé : sans accents, minuscules, tirets lus comme des espaces (« sans-fil » = « sans fil »)."""
    return " ".join(plain(s).replace("-", " ").split())


def parts(title, declared=None):
    """Ce qu'on lit d'une offre : son titre, puis chaque niveau de sa catégorie déclarée (« Aspirateur > Aspirateur
    balai » : « aspirateur », « aspirateur balai »)."""
    return [text(title)] + [text(x) for x in re.split(r"[>/|»›]", declared or "") if x.strip()]


class Domain:
    def __init__(self, data, source="?"):
        check(data, source)
        self.data, self.source = data, source
        self.key, self.version, self.label, self.one = data["domain"], data["version"], data["label"], data["one"]
        self.categories = tuple(data["categories"])
        self.subs = data["subcategories"]
        self.sub = {s["key"]: s for s in self.subs}
        self.attrs = {a["key"]: a for a in data["attributes"]}
        self.drops = set(data.get("drops", ()))
        self._text = [(a["key"], re.compile(r["re"]), r["value"]) for a in data["attributes"] for r in a.get("text", ())]
        self._subre = [[re.compile(x["text"]) for x in s["match"].get("any", ())] for s in self.subs]
        # La langue du domaine : (expression, nature, ce qu'elle dit), les plus longues d'abord
        lex = [(w, "domain", None) for w in data.get("words", ())]
        lex += [(w, "sub", s["key"]) for s in self.subs for w in s.get("words", ())]
        lex += [(w, "attr", (a["key"], v)) for a in data["attributes"] for w, v in (a.get("words") or {}).items()]
        self._lex = [(re.compile(rf"(?<!\w){re.escape(w)}(?!\w)"), w, kind, what) for w, kind, what in sorted(lex, key=lambda e: -len(e[0]))]

    def category_of(self, sub):
        """Le rayon d'une sous-catégorie (robot → robot_aspirateur)."""
        return self.sub[sub]["match"]["category"][0]

    def owns(self, key):
        """Une clé que l'ontologie lit elle-même (ses attributs, la sous-catégorie)."""
        return key in self.attrs or key == "sub"

    def sub_of(self, category, title, declared=None):
        """La sous-catégorie d'une offre : la première dont la règle convient (sa catégorie, puis un mot de son titre ou
        d'un niveau de sa catégorie déclarée) ; None si rien ne la dit (le produit reste dans le domaine, sans type)."""
        texts = parts(title, declared)
        for s, res in zip(self.subs, self._subre):
            if category not in s["match"]["category"]:
                continue
            if not res or any(rx.search(t) for rx in res for t in texts):
                return s["key"]
        return None

    def read(self, title, declared=None):
        """Les attributs que l'offre dit (son titre, puis sa catégorie déclarée) → {attribut: True | False}."""
        vals = {}
        for t in parts(title, declared):
            for key, rx, value in self._text:
                if key not in vals and rx.search(t):
                    vals[key] = value
        return vals

    def facts(self, attrs):
        """{attribut: valeur} d'un produit : ce que son offre dit, puis ce que son type est par définition (un robot est
        sans fil) — jamais à la place de ce que l'offre dit."""
        attrs = attrs or {}
        out = {k: attrs[k] for k in self.attrs if attrs.get(k) is not None}
        for k, v in (self.sub.get(attrs.get("sub")) or {}).get("implies", {}).items():
            out.setdefault(k, v)
        return out

    def understand(self, t):
        """Une phrase (texte simple, `text`) → {sub, props: {attribut: valeur}, said: mots expliqués, domain: le domaine
        est-il nommé}. Les expressions les plus longues d'abord ; un mot pris n'est plus repris ; deux types nommés : le
        plus précis (l'ordre des sous-catégories) ; un attribut dit deux fois : le premier dit, comme dans une offre."""
        out = {"sub": None, "props": {}, "said": set(), "domain": False}
        subs, props = [], []
        for rx, w, kind, what in self._lex:
            m = rx.search(t)
            if not m:
                continue
            t = rx.sub(lambda x: " " * len(x.group(0)), t)       # même longueur : les positions restent justes
            out["said"] |= set(re.split(r"[\s']+", w))
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


def check(d, source="?"):
    """Relit une ontologie avant de s'en servir : schéma, version, références (sous-catégories, attributs), expressions
    lisibles, mots réclamés une seule fois. → OntologyError à la première faute, avec où elle est."""
    def fail(msg):
        raise OntologyError(f"{source} : {msg}")
    for k in ("schema", "domain", "version", "label", "one", "categories", "subcategories", "attributes"):
        if k not in d:
            fail(f"« {k} » manque")
    if d["schema"] != SCHEMA:
        fail(f"schéma {d['schema']} inconnu (attendu : {SCHEMA})")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(d["version"])):
        fail("version : trois nombres (2.0.0)")
    attrs = set()
    for a in d["attributes"]:
        k = a.get("key")
        if not k or k in attrs:
            fail(f"attribut sans clé ou en double : {k}")
        if not a.get("yes") or not a.get("no") or not a.get("text"):
            fail(f"{k} : « yes », « no » et « text » sont requis")
        for r in a["text"]:
            _compile(r.get("re", ""), fail, k)
            if not isinstance(r.get("value"), bool):
                fail(f"{k} : une expression dit oui (true) ou non (false)")
        attrs.add(k)
    subs = set()
    for s in d["subcategories"]:
        k = s.get("key")
        if not k or k in subs:
            fail(f"sous-catégorie sans clé ou en double : {k}")
        if not s["match"].get("category") or not set(s["match"]["category"]) <= set(d["categories"]):
            fail(f"{k} : catégorie hors du domaine")
        for x in s["match"].get("any", ()):
            if not x.get("text"):
                fail(f"{k} : une règle « any » dit un texte")
            _compile(x["text"], fail, k)
        for y in list(s.get("implies") or {}) + list(s.get("attributes") or ()):
            if y not in attrs:
                fail(f"{k} : attribut inconnu « {y} »")
        subs.add(k)
    words = {}
    for who, ws in [("le domaine", d.get("words", ()))] + [(s["key"], s.get("words", ())) for s in d["subcategories"]] + \
            [(a["key"], a.get("words") or {}) for a in d["attributes"]]:
        for w in ws:
            if w in words:
                fail(f"« {w} » est déjà pris par {words[w]}")
            words[w] = who
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
    """Le domaine d'une catégorie (« robot_aspirateur » → aspirateurs), ou None : la catégorie n'a pas d'ontologie."""
    return BY_CATEGORY.get(category)


def detect(t):
    """Le domaine qu'une phrase nomme sans nommer de catégorie (« balai sans fil », « robot »)."""
    for d in DOMAINS.values():
        u = d.understand(t)
        if u["domain"] or u["sub"]:
            return d
    return None
