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
PER_EMAIL_HOUR = 5
PER_IP_HOUR = 20
COOKIE = "deals_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


def login_message(to, link, sender, about=None):
    """Le lien de connexion ; about : la mission qui attend ce lien (« Aspirateur balai · 300 € max »)."""
    m = EmailMessage()
    m["Subject"] = f"Confirmez votre mission : {about}" if about else "Votre lien de connexion Deals"
    m["From"] = sender
    m["To"] = to
    why = (f"Pour lancer votre mission « {about} », ouvrez ce lien : on guette chaque nuit et on vous prévient dès qu'un "
           "produit est à votre prix." if about else "Pour vous connecter à Deals, ouvrez ce lien sur l'appareil où vous utilisez l'app :")
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


class Accounts:
    def __init__(self, store, settings, outbox=None, clock=time.time):
        self.s, self.cfg, self.clock = store, settings, clock
        self.outbox = outbox or outbox_for(settings)
        self.base = settings.public_url.rstrip("/")

    @staticmethod
    def normalize(email):
        e = (email or "").strip().lower()
        if len(e) > 254 or not EMAIL_RE.match(e):
            raise BadRequest("Adresse e-mail invalide")
        return e

    def request_link(self, email, ip=None, mission=None, about=None):
        """Envoie un lien de connexion ; mission (JSON vérifié par missions.py) attend avec lui, about la nomme."""
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
            self.s.x("INSERT INTO login_links(token_hash, email, ip, created_at, expires_at, mission) VALUES (?,?,?,?,?,?)",
                     (_h(token), e, ip, now, now + LINK_TTL, mission))
        self.outbox.send(e, f"{self.base}/api/r/auth/verify?token={token}", about)
        return {"ok": True, "message": "Lien envoyé. Ouvrez-le depuis votre boîte mail."}

    def verify(self, token):
        """Lien ouvert → (adresse de retour, cookie de session | None, (compte, mission en JSON) | None : la mission qui
        attendait ce lien). Un lien expiré ou déjà utilisé renvoie à l'app."""
        now = self.clock()
        h = _h(token or "")
        with self.s.tx() as c:
            row = c.execute("SELECT email, mission FROM login_links WHERE token_hash=?", (h,)).fetchone()
            used = c.execute("UPDATE login_links SET used=1 WHERE token_hash=? AND used=0 AND expires_at>?", (h, now)).rowcount
            if not row or used != 1:
                return "/?auth=expired", None, None
            c.execute("INSERT OR IGNORE INTO users(email, created_at) VALUES (?,?)", (row["email"], now))
            uid = c.execute("SELECT id FROM users WHERE email=?", (row["email"],)).fetchone()["id"]
            session = secrets.token_urlsafe(32)
            c.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                      (_h(session), uid, now, now + SESSION_TTL))
        return "/", self.cookie(session), ((uid, row["mission"]) if row["mission"] else None)

    def cookie(self, session=None):
        secure = "; Secure" if self.base.startswith("https") else ""
        if session is None:
            return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"
        return f"{COOKIE}={session}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}{secure}"

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
        return {"email": self.s.q("SELECT email FROM users WHERE id=?", (self.require(session),), one=True)["email"]}

    def logout(self, session):
        if session:
            self.s.x("DELETE FROM sessions WHERE token_hash=?", (_h(session),))
        return self.cookie(None)
