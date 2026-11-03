"""Réglages de Promo Central (nom de code : deals), en un seul endroit.

Valeurs par défaut pour le développement ; en production, les variables d'environnement DEALS_<NOM> (fichier
/etc/deals/deals.env) les remplacent : DEALS_DB, DEALS_PUBLIC_URL, DEALS_SMTP_HOST… Les règles du produit (seuils,
familles, coefficients) restent dans le module qui les applique, pas ici.

Une valeur invalide arrête le démarrage avec le nom de la variable fautive, plutôt qu'un service qui tourne mal
(exemple réel : systemd ne retire pas un commentaire placé en fin de ligne, « starttls  # … » n'est pas « starttls »).
"""
import os
from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class Settings:
    db: str = "deals.sqlite"
    public_url: str = "http://127.0.0.1:8000"     # sert aux liens de connexion ; en https, le cookie est marqué Secure
    port: int = 8000
    trust_proxy: bool = True                        # X-Forwarded-For pris en compte seulement s'il vient de 127.0.0.1 (Caddy)
    user_agent: str = "PromoCentralBot/0.1 (+https://promocentral.example/robot ; contact : robot@promocentral.example)"
    min_interval_s: float = 5.0                     # au moins 5 s entre deux requêtes vers un même site
    night_budget_s: float = 4 * 3600.0              # durée maximale de la passe de nuit
    reports_dir: str = "reports"
    smtp_host: str = ""                             # vide : les liens restent en mémoire (et dans DEALS_OUTBOX) — développement
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: str = "starttls"                      # starttls | ssl | none
    mail_from: str = ""
    outbox: str = ""                                # développement : fichier où écrire les liens de connexion
    mails_per_day: int = 250                        # plafond global d'e-mails de connexion (offre gratuite courante : 300/jour)
    mission_mails: int = 50                         # plafond d'e-mails de missions par nuit ; le reste part la nuit suivante
    affiliate: str = ""                             # fichier JSON des enseignes partenaires (affiliate.py) ; vide : développement
    sources: str = ""                               # fichier JSON des sources (ingest/registry.py : flux des enseignes) ; vide : le code
    raw_dir: str = "raw"                            # fichiers bruts des flux, gardés raw_keep_days jours (ingest/batches.py)
    raw_keep_days: int = 14
    feed_max_mb: int = 500                          # taille maximale d'un flux téléchargé
    legal_editor: str = ""                          # mentions légales (page de l'app) : éditeur (raison sociale, forme, capital)
    legal_registration: str = ""                    # immatriculation (RCS, SIREN), TVA intracommunautaire
    legal_address: str = ""                         # adresse du siège
    legal_director: str = ""                        # directeur de la publication
    legal_contact: str = ""                         # contact (et exercice des droits sur les données personnelles)
    legal_host: str = ""                            # hébergeur : nom, adresse, téléphone
    operator_email: str = ""                        # responsable d'exploitation : l'agent lui écrit si c'est utile (agent.py)
    photos: bool = False                            # v67 : montrer la photo du produit donnée par le flux (chargée depuis le
                                                    # serveur de l'enseigne) ; non : nos illustrations. À décider (droits, tiers)
    env: str = "dev"                                # dev | demo | prod : noté dans chaque ligne du journal
    log_json: bool = False                          # journal opérationnel aussi en JSON sur la sortie d'erreur (journald)


TRUE, FALSE = ("1", "true", "yes", "oui", "on"), ("0", "false", "no", "non", "off")
SMTP_TLS = ("starttls", "ssl", "none")
ENVS = ("dev", "demo", "prod")
# Mode démo (DEALS_ENV=demo) : données simulées, fictives, affichées comme telles ; aucune mention légale, aucun SMTP,
# aucun flux ni partenaire réel. Ce mode ne relâche aucun contrôle de la production : il est exclusif de prod.
DEMO_REFUSED = ("nightly", "missions", "discover", "diagnose", "sample", "build", "ingest", "replay", "publish")


LEGAL = ("legal_editor", "legal_registration", "legal_address", "legal_director", "legal_contact", "legal_host")


def legal_missing(s):
    """Les mentions légales qui manquent (DEALS_LEGAL_…) : en production, l'app ne démarre pas sans elles."""
    return ["DEALS_" + k.upper() for k in LEGAL if not getattr(s, k).strip()]


def is_demo(s):
    return s.env == "demo"


def problems(s):
    """Ce qui empêche de démarrer dans ce mode, en clair (deals.py check). Liste vide : prêt."""
    out = []
    if s.env == "prod":
        if missing := legal_missing(s):
            out.append("mentions légales incomplètes (" + ", ".join(missing) + ") : la production ne démarre pas sans elles")
        if not s.public_url.startswith("https://"):
            out.append("DEALS_PUBLIC_URL doit être en https:// en production")
        if s.user_agent == Settings.user_agent:
            out.append("DEALS_USER_AGENT : le nom du robot, sa page et un contact sont à régler")
        if not s.operator_email:
            out.append("DEALS_OPERATOR_EMAIL : le responsable d'exploitation est à renseigner")
        exemples = [k for k in ("public_url", "mail_from", "operator_email", "user_agent", "smtp_host")
                    if ".example" in getattr(s, k)]
        if exemples:
            out.append("valeurs d'exemple encore présentes (" + ", ".join(exemples) + ") : à remplacer par les vraies")
    return out


def load(env=None, **overrides):
    """Réglages depuis l'environnement (DEALS_<NOM>), puis surcharges explicites. ValueError si une valeur est invalide."""
    env = os.environ if env is None else env
    values = {}
    for f in fields(Settings):
        name = "DEALS_" + f.name.upper()
        raw = (env.get(name) or "").strip()
        if not raw:
            continue
        try:
            if f.type is bool:
                if raw.lower() not in TRUE + FALSE:
                    raise ValueError
                values[f.name] = raw.lower() in TRUE
            else:
                values[f.name] = f.type(raw)
        except ValueError:
            raise ValueError(f"{name} : valeur invalide {raw!r}") from None
    s = replace(Settings(**values), **overrides)
    if s.smtp_tls not in SMTP_TLS:
        raise ValueError(f"DEALS_SMTP_TLS : {s.smtp_tls!r} au lieu de {' | '.join(SMTP_TLS)} (commentaire en fin de ligne ?)")
    if s.env not in ENVS:
        raise ValueError(f"DEALS_ENV : {s.env!r} au lieu de {' | '.join(ENVS)}")
    if not s.public_url.startswith(("http://", "https://")):
        raise ValueError(f"DEALS_PUBLIC_URL : {s.public_url!r} doit commencer par https://")
    return s
