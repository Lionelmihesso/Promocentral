"""Client HTTP poli pour l'écoute du marché.

- s'identifie clairement (User-Agent configurable avec contact)
- respecte robots.txt (mis en cache 6 h par hôte)
- espace les requêtes par hôte (politesse, défaut 5 s)
- requêtes conditionnelles (ETag / Last-Modified → 304 = inchangé)
- classe chaque résultat : ok | not_modified | blocked | rate_limited | gone | disallowed | error
Aucun contournement de protection anti-robot : un site qui bloque est signalé, pas forcé.
"""
import gzip
import re
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
import zlib
from urllib.parse import urlsplit

DEFAULT_UA = "MarketListener/0.1 (+mailto:contact@example.com)"
BLOCK_MARKERS = re.compile(r"captcha|datadome|cf-chl|challenge-platform|access denied|are you a robot|px-captcha", re.I)


class Fetcher:
    def __init__(self, user_agent=DEFAULT_UA, min_interval=5.0, timeout=20.0, respect_robots=True):
        self.ua = user_agent
        self.min_interval = min_interval
        self.timeout = timeout
        self.respect_robots = respect_robots
        self._robots = {}      # host -> (parser|None, fetched_at, allow_all)
        self._last = {}        # host -> last request time
        self._host_locks = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------------- politesse
    def _host(self, url):
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def _host_lock(self, host):
        with self._lock:
            return self._host_locks.setdefault(host, threading.Lock())

    def _wait_turn(self, host):
        while True:
            with self._lock:
                wait = self._last.get(host, 0) + self.min_interval - time.monotonic()
                if wait <= 0:
                    self._last[host] = time.monotonic()
                    return
            time.sleep(min(wait, 1.0))

    def allowed(self, url):
        if not self.respect_robots:
            return True
        host = self._host(url)
        entry = self._robots.get(host)
        if not entry or time.time() - entry[1] > 6 * 3600:
            rp = urllib.robotparser.RobotFileParser()
            allow_all = False
            try:
                req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": self.ua})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as e:
                allow_all = 400 <= e.code < 500  # pas de robots.txt → tout est permis
                if not allow_all:
                    rp = None                    # erreur serveur → prudence : on s'abstient
            except Exception:
                rp = None
            entry = (rp, time.time(), allow_all)
            self._robots[host] = entry
        rp, _, allow_all = entry
        if allow_all:
            return True
        return rp is not None and rp.can_fetch(self.ua, url)

    # -------------------------------------------------------------- requête
    def get(self, url, etag=None, last_modified=None):
        """→ dict(status, code, html, etag, last_modified, elapsed_ms, retry_after, final_url)"""
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
                    raw = r.read()
                    enc = r.headers.get("Content-Encoding", "")
                    if enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        raw = zlib.decompress(raw)
                    html = raw.decode(_charset(r.headers.get("Content-Type"), raw), "replace")
                    res = {"status": "ok", "code": r.status, "html": html, "etag": r.headers.get("ETag"),
                           "last_modified": r.headers.get("Last-Modified"), "final_url": r.geturl()}
                    if BLOCK_MARKERS.search(html[:5000]) and "application/ld+json" not in html:
                        res["status"] = "blocked"
            except urllib.error.HTTPError as e:
                body = e.read()[:5000].decode("utf-8", "replace") if e.fp else ""
                if e.code == 304:
                    res = {"status": "not_modified", "code": 304}
                elif e.code == 429:
                    res = {"status": "rate_limited", "code": 429, "retry_after": _retry_after(e.headers)}
                elif e.code in (404, 410):
                    res = {"status": "gone", "code": e.code}
                elif e.code in (401, 403) or BLOCK_MARKERS.search(body):
                    res = {"status": "blocked", "code": e.code}
                else:
                    res = {"status": "error", "code": e.code}
            except Exception as e:  # timeout, DNS, TLS…
                res = {"status": "error", "code": None, "error": type(e).__name__}
            res["elapsed_ms"] = round((time.monotonic() - t0) * 1000)
            return res


def _charset(ctype, raw):
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I) or re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:3000], re.I)
    cs = m.group(1) if m else "utf-8"
    return cs.decode() if isinstance(cs, bytes) else cs


def _retry_after(headers):
    try:
        return int(headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None
