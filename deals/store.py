"""Base SQLite : un fichier, le schéma complet ici (source unique du modèle de données), une version.

Concurrence par construction : mode WAL (une lecture ne bloque jamais), une connexion par fil, des transactions
courtes — une par page relue, une par action d'une personne, une pour publier le catalogue. Le serveur web et la passe
de nuit partagent le fichier sans verrou applicatif.

  store = Store("deals.sqlite")
  store.q(sql, args, one=False) → lignes (dict)       store.x(sql, args) → id inséré       store.many(sql, lignes)
  with store.tx(): …                                  écritures groupées, tout ou rien
"""
import sqlite3
import threading
from contextlib import contextmanager

SCHEMA_VERSION = 1
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


class Store:
    def __init__(self, path):
        self.path = str(path)
        self._local = threading.local()
        c = self.conn()
        c.execute("PRAGMA journal_mode=WAL")
        version = c.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            if c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
                raise RuntimeError(f"{self.path} : base d'une version antérieure de DEALS (sans numéro de schéma) ; "
                                   "repartir d'une base neuve")
            c.executescript(SCHEMA + f"\nPRAGMA user_version={SCHEMA_VERSION};")
        elif version > SCHEMA_VERSION:
            raise RuntimeError(f"{self.path} : schéma v{version}, plus récent que ce code (v{SCHEMA_VERSION})")

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
