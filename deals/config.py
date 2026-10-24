"""Réglages de DEALS, en un seul endroit.

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
    user_agent: str = "DealsBot/0.1 (+https://deals.example/robot ; contact : robot@deals.example)"
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


TRUE, FALSE = ("1", "true", "yes", "oui", "on"), ("0", "false", "no", "non", "off")
SMTP_TLS = ("starttls", "ssl", "none")


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
    if not s.public_url.startswith(("http://", "https://")):
        raise ValueError(f"DEALS_PUBLIC_URL : {s.public_url!r} doit commencer par https://")
    return s
