"""Base SQLite : un fichier, le schéma ici et nulle part ailleurs (source unique du modèle de données), une version.

Concurrence par construction : mode WAL (une lecture ne bloque jamais), une connexion par fil, des transactions
courtes — une par page relue, une par action d'une personne, une pour publier le catalogue. Le serveur web et la passe
de nuit partagent le fichier sans verrou applicatif.

  store = Store("deals.sqlite")
  store.q(sql, args, one=False) → lignes (dict)       store.x(sql, args) → id inséré       store.many(sql, lignes)
  with store.tx(): …                                  écritures groupées, tout ou rien

Schéma = SCHEMA (version 1) puis les MIGRATIONS dans l'ordre. Une base neuve suit exactement le même chemin qu'une base
existante : chaque migration est donc exécutée par chaque test. Création et migrations se font dans une seule
transaction (deux processus qui démarrent ensemble : un seul migre, l'autre attend puis trouve la base à jour).
"""
import sqlite3
import threading
from contextlib import contextmanager

SCHEMA_VERSION = 14
SCHEMA = """
-- marché : écrit par market.py (collecte de nuit)
CREATE TABLE products (
  id INTEGER PRIMARY KEY, gtin TEXT UNIQUE, brand TEXT, mpn TEXT, title TEXT NOT NULL, norm_title TEXT, category TEXT,
  attributes TEXT NOT NULL DEFAULT '{}', image TEXT, needs_review INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
CREATE TABLE offers (
  id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, host TEXT NOT NULL, retailer TEXT NOT NULL, merchant TEXT NOT NULL,
  product_id INTEGER REFERENCES products(id), category_hint TEXT,
  status TEXT NOT NULL DEFAULT 'new',          -- new | active | gone | blocked | disallowed | out_of_scope
  note TEXT, protection TEXT, etag TEXT, last_modified TEXT, pending_price REAL, fails INTEGER NOT NULL DEFAULT 0,
  checked_at REAL, created_at REAL NOT NULL);
CREATE INDEX offers_product ON offers(product_id);
CREATE INDEX offers_retailer ON offers(retailer, status);
CREATE TABLE prices (                           -- une ligne par changement ; sinon last_seen avance
  id INTEGER PRIMARY KEY, offer_id INTEGER NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  first_seen REAL NOT NULL, last_seen REAL NOT NULL, price REAL NOT NULL, was REAL, availability TEXT NOT NULL,
  seller TEXT, valid_until TEXT, lowest_30d REAL, source TEXT, was_source TEXT);
CREATE INDEX prices_offer ON prices(offer_id, first_seen);
CREATE INDEX prices_seen ON prices(last_seen);
CREATE TABLE site_rules (host TEXT PRIMARY KEY, rules TEXT NOT NULL);
CREATE TABLE runs (id INTEGER PRIMARY KEY, day TEXT NOT NULL, started REAL NOT NULL, ended REAL, stats TEXT);

-- catalogue publié : écrit par publish.py en une transaction, lu par l'app
CREATE TABLE catalog (
  product_id INTEGER PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL, brand TEXT, category TEXT, price REAL NOT NULL,
  was REAL, pct INTEGER NOT NULL DEFAULT 0, merchant TEXT, offer_id INTEGER, verified INTEGER NOT NULL DEFAULT 0,
  search TEXT NOT NULL, published_on TEXT NOT NULL);
CREATE INDEX catalog_deals ON catalog(pct, category);
CREATE INDEX catalog_brand ON catalog(brand);
CREATE TABLE catalog_offers (
  product_id INTEGER NOT NULL, offer_id INTEGER NOT NULL, merchant TEXT, price REAL NOT NULL, was REAL,
  pct INTEGER NOT NULL DEFAULT 0, availability TEXT NOT NULL, rank INTEGER NOT NULL, PRIMARY KEY (product_id, offer_id));
CREATE TABLE similar (product_id INTEGER NOT NULL, other_id INTEGER NOT NULL, rank INTEGER NOT NULL, PRIMARY KEY (product_id, other_id));

-- personnes : écrit par accounts.py et activity.py
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, created_at REAL NOT NULL);
CREATE TABLE login_links (
  token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, ip TEXT, created_at REAL NOT NULL, expires_at REAL NOT NULL,
  used INTEGER NOT NULL DEFAULT 0);
CREATE INDEX login_links_email ON login_links(email, created_at);
CREATE INDEX login_links_time ON login_links(created_at);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at REAL NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE follows (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, brand TEXT NOT NULL, created_at REAL NOT NULL,
  PRIMARY KEY (user_id, brand));
CREATE TABLE saves (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, product_id INTEGER NOT NULL, created_at REAL NOT NULL,
  PRIMARY KEY (user_id, product_id));
CREATE TABLE clicks (
  id INTEGER PRIMARY KEY, at REAL NOT NULL, day TEXT NOT NULL, user_id INTEGER, product_id INTEGER NOT NULL,
  offer_id INTEGER NOT NULL, merchant TEXT, source TEXT);
CREATE INDEX clicks_day ON clicks(day);
"""
MIGRATIONS = {
    2: [  # fiche : depuis quand la remise court, jusqu'à quand ; favoris : prix au moment du choix (pour montrer une baisse)
        "ALTER TABLE catalog ADD COLUMN since TEXT",
        "ALTER TABLE catalog ADD COLUMN ends TEXT",
        "ALTER TABLE saves ADD COLUMN price REAL",
    ],
    3: [  # fiche : alternatives comparables moins chères (alternatives.py), écrites avec le catalogue
        "CREATE TABLE alternatives (product_id INTEGER NOT NULL, other_id INTEGER NOT NULL, rank INTEGER NOT NULL, "
        "PRIMARY KEY (product_id, other_id))",
    ],
    4: [  # fiche : description (caractéristiques lues), calculée avec le catalogue ; les listes n'en montrent rien
        "ALTER TABLE catalog ADD COLUMN specs TEXT",
    ],
    5: [  # fiche : courbe du prix sur 90 jours ; accueil : heure de la dernière publication
        "ALTER TABLE catalog ADD COLUMN history TEXT",
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)",
    ],
    6: [  # missions : « je veux un aspirateur balai sous 300 €, préviens-moi » (écrit par missions.py)
        "ALTER TABLE catalog ADD COLUMN attrs TEXT",
        "CREATE TABLE missions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
        "product_id INTEGER, category TEXT, brand TEXT, want TEXT NOT NULL DEFAULT '{}', max_price REAL NOT NULL, "
        "label TEXT NOT NULL, created_at REAL NOT NULL, notified TEXT NOT NULL DEFAULT '{}')",
        "CREATE INDEX missions_user ON missions(user_id)",
    ],
    7: [  # la fiche ne montre plus de description (elle est chez l'enseigne) : plus calculée ni stockée
        "ALTER TABLE catalog DROP COLUMN specs",
    ],
    8: [  # affiliation : un clic sait s'il part chez un partenaire et de quelle mission il vient ; les fiches vues donnent le
          # taux de clic ; une mission lancée avant la connexion attend avec son lien, sur le serveur
        "ALTER TABLE clicks ADD COLUMN partner INTEGER",
        "ALTER TABLE clicks ADD COLUMN mission_id INTEGER",
        "CREATE TABLE views (id INTEGER PRIMARY KEY, at REAL NOT NULL, day TEXT NOT NULL, user_id INTEGER, "
        "product_id INTEGER NOT NULL, source TEXT, mission_id INTEGER)",
        "CREATE INDEX views_day ON views(day)",
        "ALTER TABLE login_links ADD COLUMN mission TEXT",
    ],
    9: [  # top deals et filtre « prix bas » : le verdict de prix de chaque produit, calculé à la publication (catalog.position)
        "ALTER TABLE catalog ADD COLUMN level TEXT",
        "ALTER TABLE catalog ADD COLUMN span INTEGER",
        "ALTER TABLE catalog ADD COLUMN usual REAL",
    ],
    10: [  # autonomie : registre des sources et leur état, journal opérationnel, incidents, actions auditées, quarantaine
        "CREATE TABLE sources (key TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'site', name TEXT NOT NULL, "
        "partner INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active', failures INTEGER NOT NULL DEFAULT 0, "
        "last_success REAL, last_run REAL, reason TEXT, updated_at REAL)",
        "CREATE TABLE events (id INTEGER PRIMARY KEY, at REAL NOT NULL, severity TEXT NOT NULL, component TEXT NOT NULL, "
        "kind TEXT NOT NULL, entity TEXT, cid TEXT, payload TEXT)",
        "CREATE INDEX events_cid ON events(cid)",
        "CREATE INDEX events_at ON events(at)",
        "CREATE TABLE incidents (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, entity TEXT NOT NULL DEFAULT '', severity TEXT NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'open', opened_at REAL NOT NULL, last_seen REAL NOT NULL, resolved_at REAL, "
        "nights INTEGER NOT NULL DEFAULT 1, evidence TEXT, runbook TEXT, cid TEXT, escalated INTEGER NOT NULL DEFAULT 0)",
        "CREATE INDEX incidents_open ON incidents(status, kind, entity)",
        "CREATE TABLE actions (id INTEGER PRIMARY KEY, at REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, entity TEXT, "
        "incident_id INTEGER, policy TEXT NOT NULL, status TEXT NOT NULL, justification TEXT NOT NULL, inputs TEXT, "
        "preconditions TEXT, expected_effect TEXT, idempotency_key TEXT NOT NULL UNIQUE, result TEXT, verification TEXT, "
        "rollback_plan TEXT, decided_by TEXT, decided_at REAL, cid TEXT, notified INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE quarantine (offer_id INTEGER PRIMARY KEY, since REAL NOT NULL, price REAL NOT NULL, usual REAL NOT NULL, "
        "rule TEXT NOT NULL, confirmed INTEGER NOT NULL DEFAULT 0, checked_day TEXT, status TEXT NOT NULL DEFAULT 'held', "
        "released_at REAL, reason TEXT, price_id INTEGER)",
        "ALTER TABLE prices ADD COLUMN rejected INTEGER NOT NULL DEFAULT 0",   # erreur de prix écartée : hors courbes et verdicts
        "ALTER TABLE runs ADD COLUMN cid TEXT",
        "ALTER TABLE runs ADD COLUMN status TEXT",
    ],
    11: [  # profil de goûts (profile.py) : rayons choisis, réglages ; témoins sans personnalisation dans les mesures
        "CREATE TABLE interests (user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, category TEXT NOT NULL, "
        "created_at REAL NOT NULL, PRIMARY KEY (user_id, category))",
        "CREATE TABLE prefs (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, learn INTEGER NOT NULL DEFAULT 1, "
        "reset_at REAL)",
        "ALTER TABLE views ADD COLUMN variant TEXT",
        "ALTER TABLE clicks ADD COLUMN variant TEXT",
    ],
    12: [  # comptes sans e-mail (invités : favoris, marques, missions sans connexion ; l'adresse s'ajoute ensuite) ; missions =
           # recherches sauvegardées : prix facultatif, alerte par e-mail réglable, nouveautés depuis le dernier regard.
           # SQLite ne retire pas un NOT NULL : les deux tables sont recopiées (clés étrangères suspendues, store.Store)
        "CREATE TABLE users_v12 (id INTEGER PRIMARY KEY, email TEXT UNIQUE, created_at REAL NOT NULL)",
        "INSERT INTO users_v12(id, email, created_at) SELECT id, email, created_at FROM users",
        "DROP TABLE users",
        "ALTER TABLE users_v12 RENAME TO users",
        "CREATE TABLE missions_v12 (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
        "product_id INTEGER, category TEXT, brand TEXT, want TEXT NOT NULL DEFAULT '{}', max_price REAL, label TEXT NOT NULL, "
        "created_at REAL NOT NULL, notified TEXT NOT NULL DEFAULT '{}', alert INTEGER NOT NULL DEFAULT 1, seen TEXT, opened_at REAL)",
        "INSERT INTO missions_v12(id, user_id, product_id, category, brand, want, max_price, label, created_at, notified) "
        "SELECT id, user_id, product_id, category, brand, want, max_price, label, created_at, notified FROM missions",
        "DROP TABLE missions",
        "ALTER TABLE missions_v12 RENAME TO missions",
        "CREATE INDEX missions_user ON missions(user_id)",
        "ALTER TABLE login_links ADD COLUMN guest_id INTEGER",
    ],
    13: [  # ingestion par lots (ingest/) : chaque lecture d'une source (flux ou fiches) laisse un lot — quoi, quand, combien,
           # empreinte du fichier, fichier brut gardé — et ses lignes refusées ; une offre dit sa source, son identifiant dans
           # le flux, le lien de suivi du réseau et le dernier lot qui l'a vue ; un prix, le lot qui l'a relevé et la livraison
        "CREATE TABLE batches (id INTEGER PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL, cid TEXT, started_at REAL NOT NULL, "
        "ended_at REAL, status TEXT NOT NULL DEFAULT 'running', received INTEGER NOT NULL DEFAULT 0, "
        "accepted INTEGER NOT NULL DEFAULT 0, changed INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0, "
        "ignored INTEGER NOT NULL DEFAULT 0, checksum TEXT, bytes INTEGER, raw_path TEXT, connector TEXT, replay_of INTEGER, "
        "fetched_at REAL, error TEXT, reasons TEXT)",
        "CREATE INDEX batches_source ON batches(source, id)",
        "CREATE TABLE batch_rejects (batch_id INTEGER NOT NULL, line INTEGER, external_id TEXT, reason TEXT NOT NULL, record TEXT)",
        "CREATE INDEX batch_rejects_batch ON batch_rejects(batch_id)",
        "ALTER TABLE offers ADD COLUMN source TEXT",
        "ALTER TABLE offers ADD COLUMN external_id TEXT",
        "ALTER TABLE offers ADD COLUMN tracking_url TEXT",
        "ALTER TABLE offers ADD COLUMN batch_id INTEGER",
        "ALTER TABLE prices ADD COLUMN batch_id INTEGER",
        "ALTER TABLE prices ADD COLUMN shipping REAL",
    ],
    14: [  # v67 : la fiche montre ce que le flux donne — la photo du produit (si DEALS_PHOTOS l'autorise) et les frais de
           # livraison de l'offre ; ils étaient lus et gardés (products.image, prices.shipping) mais pas publiés
        "ALTER TABLE catalog ADD COLUMN image TEXT",
        "ALTER TABLE catalog ADD COLUMN shipping REAL",
        "ALTER TABLE catalog_offers ADD COLUMN shipping REAL",
    ],
}


def statements(script):
    """Découpe un script SQL en instructions (un « ; » dans un commentaire ou une chaîne ne coupe pas)."""
    out, buf = [], ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            out.append(buf.strip())
            buf = ""
    return [st for st in out if st.strip(" ;\n")]


class Store:
    def __init__(self, path):
        if sqlite3.sqlite_version_info < (3, 35):            # ALTER TABLE … DROP COLUMN (version 7)
            raise RuntimeError(f"SQLite {sqlite3.sqlite_version} : la version 3.35 ou plus récente est nécessaire")
        self.path = str(path)
        self._local = threading.local()
        c = self.conn()
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=OFF")              # une migration peut recopier une table (12) : rien ne cascade
        c.execute("BEGIN IMMEDIATE")
        try:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
                    raise RuntimeError(f"{self.path} : base d'une version antérieure de Promo Central (sans numéro de schéma) ; "
                                       "repartir d'une base neuve")
                for st in statements(SCHEMA):
                    c.execute(st)
                version = 1
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"{self.path} : schéma v{version}, plus récent que ce code (v{SCHEMA_VERSION})")
            while version < SCHEMA_VERSION:
                version += 1
                for st in MIGRATIONS[version]:
                    c.execute(st)
            broken = c.execute("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"{self.path} : références cassées après migration ({len(broken)})")
            c.execute(f"PRAGMA user_version={version}")
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        finally:
            c.execute("PRAGMA foreign_keys=ON")

    def conn(self):
        """Connexion du fil courant (créée à la demande)."""
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=10, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            self._local.conn = c
        return c

    def release(self):
        """Ferme la connexion du fil courant (fin d'une requête HTTP, fin d'un fil de collecte)."""
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    close = release

    def q(self, sql, args=(), one=False):
        rows = [dict(r) for r in self.conn().execute(sql, args).fetchall()]
        return (rows[0] if rows else None) if one else rows

    def x(self, sql, args=()):
        return self.conn().execute(sql, args).lastrowid

    def many(self, sql, rows):
        self.conn().executemany(sql, rows)

    @contextmanager
    def tx(self):
        """Transaction courte (BEGIN IMMEDIATE : le verrou d'écriture est pris d'emblée, jamais en cours de route)."""
        c = self.conn()
        if c.in_transaction:          # imbriquée : rejoint la transaction en cours
            yield c
            return
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        c.execute("COMMIT")
