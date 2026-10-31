"""Client HTTP poli pour l'écoute du marché.

- s'identifie clairement : User-Agent obligatoire, avec contact (DEALS_USER_AGENT) ;
- robots.txt lu selon la RFC 9309 par Protego (Scrapy, BSD-3, embarqué dans deals/vendor) : jokers * et $, règle la
  plus longue, groupes d'agents ; Crawl-delay et Request-rate respectés. La bibliothèque standard de Python 3.11/3.12
  ne respecte que 37 des 66 cas de la spécification (mesuré) : son comportement dépendrait de la version installée.
  Cache 24 h (1 h après une erreur) ; robots.txt absent (4xx) → tout est permis ; injoignable (5xx, réseau) → on s'abstient ;
- espace les requêtes par hôte (5 s par défaut, davantage si le site le demande) ;
- requêtes conditionnelles (ETag / Last-Modified → 304 = inchangé) ;
- encodage : BOM, en-tête HTTP, <meta charset>, sinon UTF-8 puis Windows-1252 (règle WHATWG : latin-1 = windows-1252) ;
- taille plafonnée (15 Mo, décompression comprise) ;
- blocage reconnu par signature : DataDome, Cloudflare, Akamai, Imperva, PerimeterX, Kasada, Queue-it, captcha générique.
Classement : ok | not_modified | blocked | rate_limited | gone | disallowed | error.
Aucun contournement de protection anti-robot : un site qui bloque est signalé, pas forcé.
"""
import re
import threading
import time
import urllib.error
import urllib.request
import zlib
from urllib.parse import urlsplit

from ...vendor.protego import Protego

MAX_BYTES = 15_000_000
MAX_CRAWL_DELAY = 300.0
ROBOTS_TTL, ROBOTS_RETRY = 24 * 3600, 3600
# Signatures FORTES : présentes seulement sur une page de défi ou de refus.
CHALLENGE = [
    ("datadome", re.compile(r"captcha-delivery\.com", re.I)),
    ("cloudflare", re.compile(r"<title>\s*(?:just a moment|attention required|un instant)|cf_chl_opt|cf-browser-verification", re.I)),
    ("akamai", re.compile(r"errors\.edgesuite\.net|access denied.{0,400}reference\s*(?:&#32;)?#\s*\d+\.[0-9a-f]+", re.I | re.S)),
    ("imperva", re.compile(r"_Incapsula_Resource|Incapsula incident ID", re.I)),
    ("perimeterx", re.compile(r"px-captcha|captcha\.px-cdn\.net", re.I)),
    ("captcha", re.compile(r"are you a robot|[êe]tes[- ]vous un robot|vous [êe]tes un robot|verify you are human|"
                           r"v[ée]rifi(?:er|ez) que vous [êe]tes (?:un )?humain", re.I)),
]
# Signatures FAIBLES : le site est protégé (script présent sur toutes ses pages), simple information.
PROTECTION = [
    ("datadome", re.compile(r"js\.datadome\.co|datadome", re.I)),
    ("cloudflare", re.compile(r"/cdn-cgi/challenge-platform/", re.I)),
    ("perimeterx", re.compile(r"_pxAppId|perimeterx", re.I)),
    ("kasada", re.compile(r"KPSDK", re.I)),
    ("queue-it", re.compile(r"queue-it\.net", re.I)),
]
PRODUCT_SIGNALS = re.compile(r"application/ld\+json|itemprop\s*=\s*[\"']?(?:price|offers)|product:price:amount|og:price:amount", re.I)
LATIN1 = {"iso-8859-1", "iso8859-1", "latin1", "latin-1", "l1", "us-ascii", "ascii"}


def classify(code, headers, html):
    """→ (statut forcé | None, protection repérée | None). Une page produit lisible n'est jamais déclarée bloquée,
    même si le site est protégé (le nom de la protection est alors une simple information)."""
    h = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    if h.get("cf-mitigated", "").lower() == "challenge":
        return "blocked", "cloudflare"
    body = (html or "")[:200_000]
    challenge = next((name for name, rx in CHALLENGE if rx.search(body)), None)
    vendor = challenge or next((name for name, rx in PROTECTION if rx.search(body)), None)
    if vendor is None and ("x-datadome" in h or "x-datadome-cid" in h or "datadome=" in h.get("set-cookie", "").lower()):
        vendor = "datadome"
    if vendor is None and any(k.startswith("x-kpsdk") for k in h):
        vendor = "kasada"
    if code in (401, 403):
        return "blocked", vendor
    if code == 429:
        return "rate_limited", vendor
    if challenge and (code >= 400 or not PRODUCT_SIGNALS.search(html or "")):
        return "blocked", vendor
    return None, vendor


def decode(raw, ctype=None):
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", "replace")
    m = re.search(r"charset=[\"']?([\w-]+)", ctype or "", re.I) or re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4096], re.I)
    cs = m.group(1) if m else None
    cs = (cs.decode("ascii", "ignore") if isinstance(cs, bytes) else cs or "").lower() or None
    if cs in LATIN1:
        cs = "cp1252"
    if cs:
        try:
            return raw.decode(cs, "replace")
        except LookupError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _decompress(raw, enc):
    enc = (enc or "").lower().strip()
    if enc in ("gzip", "x-gzip") or raw[:2] == b"\x1f\x8b":
        return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, MAX_BYTES)
    if enc == "deflate":
        try:
            return zlib.decompressobj().decompress(raw, MAX_BYTES)
        except zlib.error:
            return zlib.decompressobj(-zlib.MAX_WBITS).decompress(raw, MAX_BYTES)
    if enc not in ("", "identity"):
        raise ValueError(f"encodage {enc} non géré")
    return raw


class Fetcher:
    def __init__(self, user_agent, min_interval=5.0, timeout=20.0, respect_robots=True):
        self.ua = user_agent
        self.min_interval = min_interval
        self.timeout = timeout
        self.respect_robots = respect_robots
        self._robots = {}      # hôte -> (Protego | None, état ok|absent|unreachable, lu à)
        self._last = {}        # hôte -> dernière requête
        self._host_locks = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------------- politesse
    def _host(self, url):
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def _host_lock(self, host):
        with self._lock:
            return self._host_locks.setdefault(host, threading.Lock())

    def robots(self, host):
        entry = self._robots.get(host)
        if entry and time.time() - entry[2] < (ROBOTS_TTL if entry[1] != "unreachable" else ROBOTS_RETRY):
            return entry
        try:
            req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = _decompress(r.read(600_000), r.headers.get("Content-Encoding"))
            entry = (Protego.parse(raw[:512_000].decode("utf-8", "replace")), "ok", time.time())
        except urllib.error.HTTPError as e:
            e.close()
            entry = (None, "absent" if 400 <= e.code < 500 and e.code != 429 else "unreachable", time.time())
        except Exception:
            entry = (None, "unreachable", time.time())
        self._robots[host] = entry
        return entry

    def allowed(self, url):
        if not self.respect_robots:
            return True
        rp, state, _ = self.robots(self._host(url))
        if state == "absent":
            return True
        return state == "ok" and rp.can_fetch(url, self.ua)

    def delay_for(self, host):
        """Intervalle entre deux requêtes vers un hôte : le nôtre, ou celui demandé par le site (Crawl-delay, Request-rate)."""
        d = self.min_interval
        rp = (self._robots.get(host) or (None,))[0]
        if rp is not None:
            cd, rr = rp.crawl_delay(self.ua), rp.request_rate(self.ua)
            if cd:
                d = max(d, min(float(cd), MAX_CRAWL_DELAY))
            if rr and rr.requests:
                d = max(d, min(rr.seconds / rr.requests, MAX_CRAWL_DELAY))
        return d

    def _wait_turn(self, host):
        interval = self.delay_for(host)
        while True:
            with self._lock:
                wait = self._last.get(host, 0) + interval - time.monotonic()
                if wait <= 0:
                    self._last[host] = time.monotonic()
                    return
            time.sleep(min(wait, 1.0))

    # -------------------------------------------------------------- requêtes
    def get_bytes(self, url):
        """Fichier brut (plan de site, compressé ou non), mêmes règles de politesse que les pages ; None si refusé."""
        if not self.allowed(url):
            return None
        host = self._host(url)
        with self._host_lock(host):
            self._wait_turn(host)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": self.ua}), timeout=self.timeout) as r:
                    raw, enc = r.read(MAX_BYTES), r.headers.get("Content-Encoding")
            except Exception:
                return None
        try:
            return _decompress(raw, enc)
        except (zlib.error, ValueError):
            return None

    def get(self, url, etag=None, last_modified=None):
        """→ dict(status, code, html, etag, last_modified, elapsed_ms, retry_after, final_url, protection)"""
        if not self.allowed(url):
            return {"status": "disallowed", "code": None}
        host = self._host(url)
        headers = {"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml",
                   "Accept-Language": "fr-FR,fr;q=0.9", "Accept-Encoding": "gzip, deflate"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        with self._host_lock(host):
            self._wait_turn(host)
            t0 = time.monotonic()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=self.timeout) as r:
                    raw = _decompress(r.read(MAX_BYTES), r.headers.get("Content-Encoding"))
                    html = decode(raw, r.headers.get("Content-Type"))
                    forced, vendor = classify(r.status, r.headers, html)
                    res = {"status": forced or "ok", "code": r.status, "html": html, "etag": r.headers.get("ETag"),
                           "last_modified": r.headers.get("Last-Modified"), "final_url": r.geturl(), "protection": vendor}
            except urllib.error.HTTPError as e:
                with e:
                    body = decode(_decompress(e.read(200_000), e.headers.get("Content-Encoding")), e.headers.get("Content-Type")) if e.fp else ""
                forced, vendor = classify(e.code, e.headers, body)
                if e.code == 304:
                    res = {"status": "not_modified", "code": 304}
                elif e.code == 429:
                    res = {"status": "rate_limited", "code": 429, "retry_after": _retry_after(e.headers)}
                elif e.code in (404, 410):
                    res = {"status": "gone", "code": e.code}
                elif forced == "blocked":
                    res = {"status": "blocked", "code": e.code}
                else:
                    res = {"status": "error", "code": e.code, "retry_after": _retry_after(e.headers)}
                res["protection"] = vendor
            except Exception as e:  # délai, DNS, TLS, encodage…
                res = {"status": "error", "code": None, "error": type(e).__name__}
            res["elapsed_ms"] = round((time.monotonic() - t0) * 1000)
            return res


def _retry_after(headers):
    try:
        return int(headers.get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None
