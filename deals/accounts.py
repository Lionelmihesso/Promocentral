"""Connexion par lien magique : ni mot de passe, ni formulaire d'inscription.

- La personne saisit son e-mail ; un lien à usage unique, valable 15 minutes, part par e-mail ; le compte naît au
  premier lien ouvert. Réponse identique qu'un compte existe ou non (pas d'énumération des adresses).
- Le lien pose un cookie de session HttpOnly, SameSite=Lax, valable 90 jours (Secure en https).
- Seuls les hachages SHA-256 des jetons sont stockés.
- Limites d'envoi : 5 liens par adresse et par heure, 20 par adresse IP et par heure, et un plafond quotidien global
  (DEALS_MAILS_PER_DAY) pour qu'un envoi en masse ne puisse pas épuiser le quota du fournisseur et bloquer tout le monde.
- Envoi : SMTP si DEALS_SMTP_HOST est défini, sinon en mémoire (et dans le fichier DEALS_OUTBOX) pour le développement.
- Une mission lancée avant la connexion attend avec le lien, sur le serveur : elle est lancée quand le lien est ouvert,
  sur n'importe quel appareil, et l'e-mail la nomme (« Confirmez votre mission : … »).
- Sans e-mail (v56) : le premier geste qui garde quelque chose (favori, marque, rayon, recherche sauvegardée) crée un
  compte invité et son cookie, sans rien demander ; au plus GUESTS_PER_IP_HOUR par adresse IP et par heure. L'adresse
  s'ajoute ensuite, si la personne le veut : le lien ouvert la rattache au compte invité (ou, si un compte existe déjà
  pour cette adresse, y verse tout ce que l'invité avait gardé). « Effacer mes données » supprime le compte et tout ce
  qu'il gardait ; les fiches vues et les clics restent dans les mesures, sans lien avec personne.
"""
import hashlib
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage

from .errors import BadRequest, TooMany, Unauthorized, Unavailable

LINK_TTL = 15 * 60
SESSION_TTL = 90 * 24 * 3600
GUEST_TTL = 365 * 24 * 3600                                # le cookie est la seule clé d'un compte invité
GUESTS_PER_IP_HOUR = 100                                  # comptes invités par adresse IP et par heure (une box, un opérateur mobile : beaucoup de monde)
PERSONAL = ("follows", "saves", "missions", "interests")   # ce qu'un invité verse au compte (ses réglages restent les siens)
PER_EMAIL_HOUR = 5
PER_IP_HOUR = 20
COOKIE = "deals_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


def login_message(to, link, sender, about=None):
    """Le lien de connexion ; about : la mission qui attend ce lien (« Aspirateur balai · 300 € max »)."""
    m = EmailMessage()
    m["Subject"] = f"Confirmez votre mission : {about}" if about else "Votre lien de connexion Promo Central"
    m["From"] = sender
    m["To"] = to
    why = (f"Pour lancer votre mission « {about} », ouvrez ce lien : on guette chaque nuit et on vous prévient dès qu'un "
           "produit est à votre prix." if about else "Pour vous connecter à Promo Central, ouvrez ce lien sur l'appareil où vous utilisez l'app :")
    m.set_content(f"Bonjour,\n\n{why}\n{link}\n\n"
                  "Il est valable 15 minutes et ne sert qu'une fois. Si vous n'avez rien demandé, ignorez ce message.\n")
    m.add_alternative(f"""<p>Bonjour,</p><p>{why}</p>
<p><a href="{link}" style="display:inline-block;background:#101112;color:#fff;padding:12px 18px;border-radius:12px;text-decoration:none;font-weight:700">{"Lancer ma mission" if about else "Me connecter"}</a></p>
<p style="color:#5E6166">Valable 15 minutes, à usage unique. Si vous n'avez rien demandé, ignorez ce message.</p>""", subtype="html")
    return m


class Outbox:
    """Développement et tests : les liens restent en mémoire (et dans un fichier si demandé)."""

    def __init__(self, path=""):
        self.sent, self.mails, self.path = [], [], path

    def send(self, to, link, about=None):
        self.sent.append((to, link))
        self.mails.append((to, login_message(to, link, "deals@localhost", about)))
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"{to}\t{link}\n")

    def send_mail(self, to, message):
        """Autres e-mails (missions) : gardés en mémoire ; une ligne « adresse, MAIL, objet » dans le fichier."""
        self.mails.append((to, message))
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"{to}\tMAIL\t{message['Subject']}\n")


class SmtpOutbox:
    """Production : n'importe quel fournisseur SMTP (starttls sur 587, ssl sur 465)."""

    def __init__(self, settings):
        self.cfg = settings
        self.sender = settings.mail_from or settings.smtp_user or "deals@localhost"

    def send(self, to, link, about=None):
        self.send_mail(to, login_message(to, link, self.sender, about))

    def send_mail(self, to, message):
        c = self.cfg
        try:
            if c.smtp_tls == "ssl":
                conn = smtplib.SMTP_SSL(c.smtp_host, c.smtp_port, timeout=10, context=ssl.create_default_context())
            else:
                conn = smtplib.SMTP(c.smtp_host, c.smtp_port, timeout=10)
            with conn:
                if c.smtp_tls not in ("ssl", "none"):        # chiffré par défaut ; en clair seulement si « none » est écrit
                    conn.starttls(context=ssl.create_default_context())
                if c.smtp_user:
                    conn.login(c.smtp_user, c.smtp_password)
                conn.send_message(message)
        except (OSError, smtplib.SMTPException) as e:
            raise Unavailable("Envoi impossible pour le moment, réessayez dans un instant") from e


def outbox_for(settings):
    return SmtpOutbox(settings) if settings.smtp_host else Outbox(settings.outbox)


def expire_guests(store, now):
    """La nuit : les comptes invités dont la clé (le cookie, un an sans geste qui garde) a expiré ne peuvent plus être
    ouverts par personne ; ils sont effacés comme « Effacer mes données » (fiches vues et clics restent dans les mesures,
    sans lien avec personne). → combien."""
    with store.tx() as c:
        gone = [(r[0],) for r in c.execute("SELECT id FROM users WHERE email IS NULL AND id NOT IN "
                                           "(SELECT user_id FROM sessions WHERE expires_at>?)", (now,))]
        for table in ("views", "clicks"):
            c.executemany(f"UPDATE {table} SET user_id=NULL WHERE user_id=?", gone)
        c.executemany("DELETE FROM users WHERE id=?", gone)
    return len(gone)


class Accounts:
    def __init__(self, store, settings, outbox=None, clock=time.time):
        self.s, self.cfg, self.clock = store, settings, clock
        self.outbox = outbox or outbox_for(settings)
        self.base = settings.public_url.rstrip("/")
        self._guests = {}                                  # adresse IP → créations de comptes invités dans l'heure

    @staticmethod
    def normalize(email):
        e = (email or "").strip().lower()
        if len(e) > 254 or not EMAIL_RE.match(e):
            raise BadRequest("Adresse e-mail invalide")
        return e

    def request_link(self, email, ip=None, mission=None, about=None, guest=None):
        """Envoie un lien de connexion ; mission (JSON vérifié par missions.py) attend avec lui, about la nomme ; guest : le
        compte invité qui le demande, auquel l'adresse sera rattachée."""
        e = self.normalize(email)
        now = self.clock()
        count = lambda where, args: self.s.q(f"SELECT COUNT(*) n FROM login_links WHERE {where}", args, one=True)["n"]
        if count("email=? AND created_at>?", (e, now - 3600)) >= PER_EMAIL_HOUR:
            raise TooMany("Trop de demandes pour cette adresse, réessayez dans une heure")
        if ip and count("ip=? AND created_at>?", (ip, now - 3600)) >= PER_IP_HOUR:
            raise TooMany("Trop de demandes, réessayez dans une heure")
        if count("created_at>?", (now - 86400,)) >= self.cfg.mails_per_day:
            raise TooMany("Connexion momentanément indisponible, réessayez demain")
        token = secrets.token_urlsafe(32)
        with self.s.tx():
            self.s.x("DELETE FROM login_links WHERE created_at<?", (now - 2 * 86400,))
            self.s.x("DELETE FROM sessions WHERE expires_at<?", (now,))
            self.s.x("INSERT INTO login_links(token_hash, email, ip, created_at, expires_at, mission, guest_id) VALUES (?,?,?,?,?,?,?)",
                     (_h(token), e, ip, now, now + LINK_TTL, mission, guest))
        self.outbox.send(e, f"{self.base}/api/r/auth/verify?token={token}", about)
        return {"ok": True, "message": "Lien envoyé. Ouvrez-le depuis votre boîte mail."}

    def verify(self, token):
        """Lien ouvert → (adresse de retour, cookie de session | None, (compte, mission en JSON | None, adresse rattachée)
        | None). Un lien expiré ou déjà utilisé renvoie à l'app. Demandé depuis un compte invité : l'adresse lui est
        rattachée, ou, si un compte existe déjà pour elle, tout ce que l'invité gardait y est versé."""
        now = self.clock()
        h = _h(token or "")
        with self.s.tx() as c:
            row = c.execute("SELECT email, mission, guest_id FROM login_links WHERE token_hash=?", (h,)).fetchone()
            used = c.execute("UPDATE login_links SET used=1 WHERE token_hash=? AND used=0 AND expires_at>?", (h, now)).rowcount
            if not row or used != 1:
                return "/?auth=expired", None, None
            found = c.execute("SELECT id FROM users WHERE email=?", (row["email"],)).fetchone()
            guest = row["guest_id"] if row["guest_id"] and c.execute("SELECT 1 FROM users WHERE id=? AND email IS NULL",
                                                                      (row["guest_id"],)).fetchone() else None
            if guest and not found:
                c.execute("UPDATE users SET email=? WHERE id=?", (row["email"], guest))
                uid = guest
            else:
                c.execute("INSERT OR IGNORE INTO users(email, created_at) VALUES (?,?)", (row["email"], now))
                uid = c.execute("SELECT id FROM users WHERE email=?", (row["email"],)).fetchone()["id"]
                if guest:
                    self._merge(c, guest, uid)
            session = secrets.token_urlsafe(32)
            c.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                      (_h(session), uid, now, now + SESSION_TTL))
        return "/", self.cookie(session), (uid, row["mission"], bool(guest))

    @staticmethod
    def _merge(c, guest, uid):
        """Tout ce que le compte invité gardait passe au compte (sans doublon : ce que le compte avait déjà l'emporte) ; ses
        sessions aussi, pour que l'appareil de l'invité reste connecté ; puis l'invité disparaît."""
        for table in PERSONAL:
            c.execute(f"UPDATE OR IGNORE {table} SET user_id=? WHERE user_id=?", (uid, guest))
        c.execute("UPDATE sessions SET user_id=? WHERE user_id=?", (uid, guest))
        for table in ("views", "clicks"):
            c.execute(f"UPDATE {table} SET user_id=? WHERE user_id=?", (uid, guest))
        c.execute("DELETE FROM missions WHERE user_id=? AND id NOT IN (SELECT MIN(id) FROM missions WHERE user_id=? "
                  "GROUP BY product_id, category, brand, want)", (uid, uid))      # la même recherche gardée des deux côtés
        c.execute("DELETE FROM users WHERE id=?", (guest,))                       # ce qui restait (doublons) part avec lui

    def guest(self, ip=None):
        """Un compte invité, au premier geste qui garde quelque chose : (compte, cookie). Il n'apprend pas des fiches
        ouvertes tant que la personne ne l'a pas demandé (Profil)."""
        now = self.clock()
        if ip:
            if len(self._guests) > 10_000:                  # la mémoire des créations ne garde que l'heure passée
                self._guests = {k: v for k, v in self._guests.items() if v and v[-1] > now - 3600}
            recent = [t for t in self._guests.get(ip, []) if t > now - 3600]
            if len(recent) >= GUESTS_PER_IP_HOUR:
                raise TooMany("Trop de demandes, réessayez dans une heure")
            self._guests[ip] = recent + [now]
        session = secrets.token_urlsafe(32)
        with self.s.tx() as c:
            uid = c.execute("INSERT INTO users(email, created_at) VALUES (NULL, ?)", (now,)).lastrowid
            c.execute("INSERT INTO prefs(user_id, learn) VALUES (?, 0)", (uid,))
            c.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                      (_h(session), uid, now, now + GUEST_TTL))
        return uid, self.cookie(session, GUEST_TTL)

    def renew(self, session):
        """Un compte invité qui garde encore quelque chose : sa clé (le cookie) repart pour un an. → le cookie à reposer, ou
        None (pas un invité)."""
        now = self.clock()
        with self.s.tx() as c:
            n = c.execute("UPDATE sessions SET expires_at=? WHERE token_hash=? AND expires_at>? AND user_id IN "
                          "(SELECT id FROM users WHERE email IS NULL)", (now + GUEST_TTL, _h(session or ""), now)).rowcount
        return self.cookie(session, GUEST_TTL) if n else None

    def forget(self, uid):
        """« Effacer mes données » : le compte et tout ce qu'il gardait ; fiches vues et clics restent dans les mesures,
        sans lien avec personne."""
        with self.s.tx() as c:
            for table in ("views", "clicks"):
                c.execute(f"UPDATE {table} SET user_id=NULL WHERE user_id=?", (uid,))
            c.execute("DELETE FROM users WHERE id=?", (uid,))
        return {"ok": True}

    def cookie(self, session=None, ttl=SESSION_TTL):
        secure = "; Secure" if self.base.startswith("https") else ""
        if session is None:
            return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"
        return f"{COOKIE}={session}; Path=/; HttpOnly; SameSite=Lax; Max-Age={ttl}{secure}"

    def user(self, session):
        """Compte de la session, ou None."""
        if not session:
            return None
        row = self.s.q("SELECT user_id FROM sessions WHERE token_hash=? AND expires_at>?", (_h(session), self.clock()), one=True)
        return row["user_id"] if row else None

    def require(self, session):
        uid = self.user(session)
        if uid is None:
            raise Unauthorized("Connexion requise")
        return uid

    def me(self, session):
        email = self.s.q("SELECT email FROM users WHERE id=?", (self.require(session),), one=True)["email"]
        return {"email": email, "guest": email is None}

    def logout(self, session):
        if session:
            self.s.x("DELETE FROM sessions WHERE token_hash=?", (_h(session),))
        return self.cookie(None)
