"""Lecture des données d'une page produit, en un seul passage, bibliothèque standard uniquement.

- JSON-LD : chaîne de réparation reprise d'extruct (Zyte, licence BSD-3, extruct/jsonld.py, révision d24f541 du
  2026-10-15 ; voir THIRD_PARTY_NOTICES.md) : habillages CDATA / commentaires, échappements JavaScript, guillemets non
  échappés, déchets en fin de script, valeurs concaténées, entités HTML (seulement après un échec). jstyleson est
  remplacé par `_dispose` (commentaires et virgules traînantes hors des chaînes).
- Microdonnées : arbre itemscope / itemprop (spécification WHATWG), converti en dictionnaires de forme JSON-LD, pour que
  les mêmes règles Produit / Offre s'appliquent aux deux formats.
- Balises meta (OpenGraph produit), lien canonique, titre, premier h1.
- États applicatifs embarqués : <script type="application/json"> (dont __NEXT_DATA__) et window.__…STATE__ = {…}.
- Nœuds de texte visibles avec leur contexte (classes, id, élément barré) : sert à retrouver un prix barré autour du
  prix affiché, jamais à deviner le prix lui-même.
"""
import functools
import html as _html
import json
import re
from html.parser import HTMLParser

# ====================================================================== JSON-LD (portage d'extruct, BSD-3)
HTML_OR_JS_COMMENTLINE = re.compile(r"^\s*(//.*|<!--.*-->)")
_ESCAPE_SEQUENCE = re.compile(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", re.S)
_VALID_ESCAPE_CHARS = set('"\\/bfnrt')
_FRAMING_TOKENS = re.compile(r"//|/\*|\*/|<!--|--!?>|<!\[CDATA\[|\]\]>|\s+")
JSON_SPACE = " \t\r\n"
_STRUCTURAL_CHARS = set(",}]:")


def _repair_escape(match):
    escape = match.group(1)
    if len(escape) == 5 and escape[0] == "u":
        return match.group(0)
    if len(escape) == 3 and escape[0] == "x":
        return "\\u00" + escape[1:]
    if escape in _VALID_ESCAPE_CHARS:
        return match.group(0)
    if escape == "'":
        return escape
    return "\\\\" + escape


def _repair_escapes(script):
    """\\' → ' ; \\x27 → \\u0027 ; toute autre barre oblique inverse invalide est doublée (jamais perdue)."""
    return _ESCAPE_SEQUENCE.sub(_repair_escape, script)


def _is_framing_line(line):
    return not _FRAMING_TOKENS.sub("", line)


def _strip_framing(script):
    """Retire les lignes d'habillage (commentaires HTML/JS, CDATA) aux deux bouts, lignes entières seulement."""
    lines = script.split("\n")
    start, end = 0, len(lines)
    while start < end and _is_framing_line(lines[start]):
        start += 1
    while end > start and _is_framing_line(lines[end - 1]):
        end -= 1
    return "\n".join(lines[start:end])


def _skip_space(script, index):
    while index < len(script) and script[index] in JSON_SPACE:
        index += 1
    return index


def _repair_quotes(script):
    """Échappe les guillemets à l'intérieur d'une chaîne : un guillemet ne ferme la chaîne que s'il est suivi d'un
    caractère structurel. Ne modifie jamais un JSON valide."""
    out, index, length, in_string = [], 0, len(script), False
    while index < length:
        char = script[index]
        if not in_string:
            out.append(char)
            in_string = char == '"'
            index += 1
        elif char == "\\" and index + 1 < length:
            out.append(script[index:index + 2])
            index += 2
        elif char == '"':
            lookahead = _skip_space(script, index + 1)
            if lookahead >= length or script[lookahead] in _STRUCTURAL_CHARS:
                out.append(char)
                in_string = False
            else:
                out.append('\\"')
            index += 1
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _decode_leading_values(script):
    """Toutes les valeurs JSON complètes en tête du script ; le reste (accolade en trop, point-virgule…) est ignoré."""
    decoder = json.JSONDecoder(strict=False)
    values, index = [], _skip_space(script, 0)
    while index < len(script):
        try:
            value, index = decoder.raw_decode(script, index)
        except ValueError:
            break
        values.append(value)
        index = _skip_space(script, index)
    return values


def _dispose(text):
    """Rôle de jstyleson : retire les commentaires // et /* */ puis les virgules traînantes, hors des chaînes."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            in_str = c != '"'
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    s, res, in_str, i = "".join(out), [], False, 0
    while i < len(s):
        c = s[i]
        if in_str:
            res.append(c)
            if c == "\\" and i + 1 < len(s):
                res.append(s[i + 1])
                i += 2
                continue
            in_str = c != '"'
        elif c == '"':
            in_str = True
            res.append(c)
        elif c == ",":
            j = _skip_space(s, i + 1)
            if j >= len(s) or s[j] not in "}]":
                res.append(c)
        else:
            res.append(c)
        i += 1
    return "".join(res)


def _loads_js(text):
    return json.loads(_dispose(text), strict=False)


def _iter_items(data):
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict):
        yield data


def _iter_jsonld(script):
    try:
        data = json.loads(script, strict=False)
    except ValueError:
        unwrapped = HTML_OR_JS_COMMENTLINE.sub("", _strip_framing(script)) + "\n"
        try:
            data = _loads_js(unwrapped)
        except ValueError:
            repaired = _repair_escapes(unwrapped)
            try:
                data = _loads_js(repaired)
            except ValueError:
                requoted = _repair_quotes(repaired)
                try:
                    data = _loads_js(requoted)
                except ValueError:
                    values = _decode_leading_values(requoted)
                    if not values:
                        raise
                    for value in values:
                        yield from _iter_items(value)
                    return
    yield from _iter_items(data)


def parse_jsonld(script):
    """Texte d'un <script type="application/ld+json"> → liste d'objets ([] si illisible)."""
    script = (script or "").strip()
    if not script:
        return []
    try:
        return [i for i in _iter_jsonld(script) if i]
    except ValueError:
        unescaped = _html.unescape(script)        # certains sites encodent le JSON en entités HTML
        if unescaped == script:
            return []
        try:
            return [i for i in _iter_jsonld(unescaped) if i]
        except ValueError:
            return []


_LD_RE = re.compile(r"<script\b[^>]*\btype\s*=\s*[\"']?application/ld\+json[\"']?[^>]*>(.*?)</script\s*>", re.S | re.I)


def jsonld_items(html):
    """Tous les objets JSON-LD de la page (lecture tolérante)."""
    out = []
    for block in _LD_RE.findall(html or ""):
        out += parse_jsonld(block)
    return out


# ====================================================================== passage unique sur la page
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr", "keygen"}
SRC_TAGS = {"audio", "embed", "iframe", "img", "source", "track", "video"}
HREF_TAGS = {"a", "area", "link"}
STATE_JS = re.compile(r"(?:window\.)?(__[A-Z_]*(?:STATE|DATA)__|__NUXT__)\s*=\s*", re.I)
MAX_NODES = 40000


@functools.lru_cache(maxsize=4096)
def tokens(value):
    """Classes / id d'un contexte → jetons (« price--old » → {price, old} ; « oldPrice » → {old, price})."""
    return frozenset(_tokens(value))


def _tokens(*values):
    out = set()
    for v in values:
        if v:
            v = re.sub(r"([a-z])([A-Z])", r"\1 \2", v)
            out.update(t for t in re.split(r"[^a-z0-9àâäéèêëïîôöùûüç]+", v.lower()) if t)
    return out


class Page(HTMLParser):
    """Un passage : meta, canonique, titre, h1, scripts JSON-LD / JSON, microdonnées, nœuds de texte en contexte."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.canonical, self.title, self.h1 = {}, None, None, None
        self.ld_scripts, self.json_scripts = [], []
        self.items = []
        self.nodes = []                 # [texte, contexte (classes, id), barré, chemin des éléments ouverts]
        self._stack = []
        self._serial = 0
        self._script = None
        self._style = False
        self._skip = 0
        self._title_buf = self._h1_buf = None

    # ------------------------------------------------------------ microdonnées
    def _parent_item(self):
        for e in reversed(self._stack):
            if e["item"] is not None:
                return e["item"]
        return None

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if tag == "script":
            t = a.get("type", "").lower().strip()
            kind = "ld" if "ld+json" in t else "json" if (t == "application/json" or a.get("id") == "__NEXT_DATA__") else \
                "js" if t in ("", "text/javascript", "application/javascript", "module") else None
            self._script = [kind, a.get("id"), []]
            return
        if tag == "style":
            self._style = True
            return
        if tag == "meta":
            k = a.get("property") or a.get("name")
            if k and "content" in a:
                self.meta.setdefault(k.strip().lower(), a["content"])
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split() and a.get("href"):
            self.canonical = self.canonical or a["href"]
        elif tag == "title" and self.title is None:
            self._title_buf = []
        elif tag == "h1" and self.h1 is None and self._h1_buf is None:
            self._h1_buf = []
        if tag in ("noscript", "template"):
            self._skip += 1
        parent = self._parent_item()
        props = a.get("itemprop", "").split()
        created, pending = None, None
        if "itemscope" in a:
            created = {"@type": [t.rstrip("/").rsplit("/", 1)[-1] for t in a.get("itemtype", "").split()]}
            if props and parent is not None:
                for p in props:
                    parent.setdefault(p, []).append(created)
            else:
                self.items.append(created)
        elif props and parent is not None:
            if "content" in a:
                value = a["content"]
            elif tag in SRC_TAGS:
                value = a.get("src")
            elif tag in HREF_TAGS:
                value = a.get("href")
            elif tag == "object":
                value = a.get("data")
            elif tag in ("data", "meter"):
                value = a.get("value")
            elif tag == "time" and a.get("datetime"):
                value = a["datetime"]
            else:
                value = None
                pending = (parent, props)
            if pending is None:
                for p in props:
                    parent.setdefault(p, []).append(value)
        if tag in VOID:
            return
        struck = tag in ("del", "s", "strike") or "line-through" in a.get("style", "").replace(" ", "")
        self._serial += 1
        attr = " ".join(v for v in (a.get("class"), a.get("id"), a.get("itemprop"), a.get("data-testid")) if v)
        self._stack.append({"tag": tag, "sid": self._serial, "item": created, "pending": pending, "buf": [] if pending else None,
                            "attr": attr, "struck": struck})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self._stack and self._stack[-1]["tag"] == tag:
            self._close(len(self._stack) - 1)

    def handle_data(self, data):
        if self._script is not None:
            self._script[2].append(data)
            return
        if self._style:
            return
        for e in self._stack:
            if e["buf"] is not None:
                e["buf"].append(data)
        if self._title_buf is not None:
            self._title_buf.append(data)
        if self._h1_buf is not None:
            self._h1_buf.append(data)
        text = " ".join(data.split())
        if text and not self._skip and len(self.nodes) < MAX_NODES:
            ctx = " ".join(e["attr"] for e in self._stack[-5:] if e["attr"])      # découpé en jetons seulement si besoin
            struck = any(e["struck"] for e in self._stack)
            self.nodes.append([text[:300], ctx, struck, tuple(e["sid"] for e in self._stack)])

    def _close(self, i):
        while len(self._stack) > i:
            e = self._stack.pop()
            if e["pending"]:
                parent, props = e["pending"]
                text = " ".join("".join(e["buf"]).split())
                for p in props:
                    parent.setdefault(p, []).append(text)
            if e["tag"] in ("noscript", "template"):
                self._skip = max(0, self._skip - 1)

    def handle_endtag(self, tag):
        if tag == "script":
            if self._script is not None:
                kind, sid, buf = self._script
                text = "".join(buf)
                if kind == "ld":
                    self.ld_scripts.append(text)
                elif kind == "json" and len(text) < 5_000_000:
                    self.json_scripts.append((sid, text))
                elif kind == "js" and len(text) < 5_000_000 and STATE_JS.search(text):
                    self.json_scripts.append((sid or "js", text))
            self._script = None
            return
        if tag == "style":
            self._style = False
            return
        if tag == "title" and self._title_buf is not None:
            self.title = " ".join("".join(self._title_buf).split()) or None
            self._title_buf = None
        if tag == "h1" and self._h1_buf is not None:
            self.h1 = " ".join("".join(self._h1_buf).split()) or None
            self._h1_buf = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                self._close(i)
                break

    def finish(self):
        self.close()
        self._close(0)
        return self


def _simplify(item):
    """Item de microdonnées → dictionnaire de forme JSON-LD (valeurs uniques déballées)."""
    out = {}
    for k, vs in item.items():
        if k == "@type":
            out[k] = vs if len(vs) != 1 else vs[0]
            continue
        vals = [_simplify(v) if isinstance(v, dict) else v for v in vs]
        out[k] = vals[0] if len(vals) == 1 else vals
    return out


def scan(html):
    """→ Page analysée : .ld (objets JSON-LD), .micro (microdonnées en forme JSON-LD), .states (objets JSON embarqués)."""
    p = Page()
    try:
        p.feed(html or "")
    except Exception:                       # HTML pathologique : on garde ce qui a été lu
        pass
    p.finish()
    p.ld = [i for s in p.ld_scripts for i in parse_jsonld(s)]
    p.micro = [_simplify(i) for i in p.items]
    p.states = []
    for sid, text in p.json_scripts:
        m = STATE_JS.search(text) if sid == "js" or not text.lstrip().startswith(("{", "[")) else None
        start = m.end() if m else 0
        try:
            value, _ = json.JSONDecoder(strict=False).raw_decode(text.strip() if not m else text, start if m else 0)
            p.states.append(value)
        except ValueError:
            continue
    return p
