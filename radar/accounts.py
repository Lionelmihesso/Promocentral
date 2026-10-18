"""Comptes : connexion par lien magique (e-mail), sans mot de passe ni formulaire.

- L'utilisateur saisit son e-mail ; un lien à usage unique, valable 15 minutes, part par e-mail.
- Le compte est créé au premier lien cliqué (aucune étape d'inscription).
- Le lien pose un cookie de session HttpOnly valable 90 jours : on ne se reconnecte qu'exceptionnellement.
- Seuls les hachages SHA-256 des jetons sont stockés en base.
- Envoi : `Outbox` garde les liens en mémoire (tests) et, si DEALS_OUTBOX est défini, les écrit dans ce fichier.
  En production, remplacer `Outbox.send` par un envoi SMTP ou un fournisseur d'e-mail.
"""
import hashlib
import os
import re
import secrets
import time

LINK_TTL = 15 * 60
SESSION_TTL = 90 * 24 * 3600
MAX_LINKS_PER_HOUR = 5
COOKIE = "deals_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS login_links (token_hash TEXT PRIMARY KEY, email TEXT NOT NULL,
  created_at REAL NOT NULL, expires_at REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS login_links_email ON login_links(email, created_at);
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
  created_at REAL NOT NULL, expires_at REAL NOT NULL);
"""


def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


class RateLimited(ValueError):
    status = 429


class Outbox:
    def __init__(self):
        self.sent = []  # (destinataire, lien)

    def send(self, to, link):
        self.sent.append((to, link))
        path = os.environ.get("DEALS_OUTBOX")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{to}\t{link}\n")


class Accounts:
    def __init__(self, radar):
        self.R, self.L = radar, radar.L
        self.outbox = Outbox()
        self.base = os.environ.get("DEALS_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
        with self.L.lock:
            self.L.db.executescript(SCHEMA)
            self.L.db.commit()

    def q(self, sql, args=(), one=False):
        return self.L.q(sql, args, one=one)

    # ------------------------------------------------------------ lien magique
    @staticmethod
    def normalize(email):
        e = (email or "").strip().lower()
        if len(e) > 254 or not EMAIL_RE.match(e):
            raise ValueError("Adresse e-mail invalide")
        return e

    def request_link(self, email):
        """Réponse identique qu'un compte existe ou non : pas d'énumération des adresses."""
        e = self.normalize(email)
        now = time.time()
        n = self.q("SELECT COUNT(*) AS n FROM login_links WHERE email=? AND created_at>?", (e, now - 3600), one=True)["n"]
        if n >= MAX_LINKS_PER_HOUR:
            raise RateLimited("Trop de demandes, réessayez dans une heure")
        token = secrets.token_urlsafe(32)
        self.q("INSERT INTO login_links(token_hash, email, created_at, expires_at) VALUES (?,?,?,?)",
               (_h(token), e, now, now + LINK_TTL))
        self.outbox.send(e, f"{self.base}/api/r/auth/verify?token={token}")
        return {"ok": True, "message": "Lien envoyé. Ouvrez-le depuis votre boîte mail."}

    def consume(self, token):
        """Valide le lien (une seule fois), crée le compte si besoin, retourne un jeton de session."""
        now = time.time()
        h = _h(token or "")
        with self.L.lock:
            row = self.L.db.execute("SELECT email FROM login_links WHERE token_hash=?", (h,)).fetchone()
            cur = self.L.db.execute("UPDATE login_links SET used=1 WHERE token_hash=? AND used=0 AND expires_at>?", (h, now))
            self.L.db.commit()
        if not row or cur.rowcount != 1:
            raise ValueError("Lien expiré ou déjà utilisé : demandez-en un nouveau")
        uid = self.R.user(row["email"])  # même table users que le reste du moteur ; le nom est l'e-mail
        session = secrets.token_urlsafe(32)
        self.q("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
               (_h(session), uid, now, now + SESSION_TTL))
        return session

    def verify(self, q):
        try:
            session = self.consume(q.get("token", ""))
        except ValueError:                       # lien expiré ou déjà utilisé : retour à l'app, qui le signale
            return {"__redirect__": "/?auth=expired"}
        secure = "; Secure" if self.base.startswith("https") else ""
        return {"__redirect__": "/", "__set_cookie__": f"{COOKIE}={session}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}{secure}"}

    # ------------------------------------------------------------ session
    def user_for(self, session):
        """Identifiant utilisateur de la session courante ; lève PermissionError (→ 401) sinon."""
        if not session:
            raise PermissionError("Connexion requise")
        row = self.q("SELECT user_id, expires_at FROM sessions WHERE token_hash=?", (_h(session),), one=True)
        if not row or row["expires_at"] < time.time():
            raise PermissionError("Connexion requise")
        return row["user_id"]

    def me(self, session):
        uid = self.user_for(session)
        return {"email": self.q("SELECT name FROM users WHERE id=?", (uid,), one=True)["name"]}

    def logout(self, session):
        if session:
            self.q("DELETE FROM sessions WHERE token_hash=?", (_h(session),))
        return {"ok": True, "__set_cookie__": f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"}


def of(radar):
    """Une seule instance de comptes par moteur (partage de la boîte d'envoi)."""
    a = getattr(radar, "_accounts", None)
    if a is None:
        a = radar._accounts = Accounts(radar)
    return a
