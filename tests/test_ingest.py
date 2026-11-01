"""Ingestion par flux (lot 2, docs/PRODUCTION.md) : un flux d'enseigne (CSV, XML Google Shopping, JSONL) lu, normalisé,
contrôlé ligne à ligne, écrit par le marché ; chaque lecture est un lot tracé et rejouable ; le même fichier ne crée ni
doublon ni ligne de prix ; un flux tronqué ne supprime rien ; un flux illisible est un échec, pas un catalogue vide."""
import gzip
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from deals import publish as P
from deals import sources
from deals.ingest import batches, contract, feeds, registry
from deals.ingest.collector import Collector
from deals.ingest.pages.crawl import Crawler
from deals.market import Market
from deals.store import Store

DAY = date(2026, 10, 31)
T0 = datetime(2026, 10, 31, 3, 0, tzinfo=timezone.utc).timestamp()


def item(i, title, link, price, sale=None, avail="in_stock", gtin=None, brand=None, ptype=None, extra=""):
    parts = [f"<g:id>{i}</g:id>", f"<title>{title}</title>", f"<link>{link}</link>", f"<g:price>{price}</g:price>",
             f"<g:availability>{avail}</g:availability>"]
    if sale:
        parts.append(f"<g:sale_price>{sale}</g:sale_price>")
    if gtin:
        parts.append(f"<g:gtin>{gtin}</g:gtin>")
    if brand:
        parts.append(f"<g:brand>{brand}</g:brand>")
    if ptype:
        parts.append(f"<g:product_type>{ptype}</g:product_type>")
    return "<item>" + "".join(parts) + extra + "</item>"


def rss(*items):
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>'
            "<title>Flux</title><link>https://alpha.example/</link>" + "".join(items) + "</channel></rss>").encode()


LAVE = item("LL1", "Lave-linge hublot Kessler WM8 8 kg 1400 tr/min classe A", "https://alpha.example/p/ll1?utm_source=aff&amp;color=blanc",
            "699.00 EUR", sale="549.00 EUR", gtin="3000000000014", brand="Kessler", ptype="Électroménager > Lavage > Lave-linge hublot",
            extra="<g:sale_price_effective_date>2026-10-25T00:00+0100/2026-11-08T23:59+0100</g:sale_price_effective_date>"
                  "<g:shipping><g:country>FR</g:country><g:price>0.00 EUR</g:price></g:shipping>"
                  "<g:product_detail><g:attribute_name>Classe énergétique</g:attribute_name><g:attribute_value>A</g:attribute_value>"
                  "</g:product_detail><g:product_detail><g:attribute_name>Capacité</g:attribute_name>"
                  "<g:attribute_value>8 kg</g:attribute_value></g:product_detail>")
TV = item("TV1", "TV OLED Brava 55 pouces 4K", "https://alpha.example/p/tv1", "1299.00 EUR", avail="out of stock",
          gtin="3000000000021", brand="Brava", ptype="TV - Vidéo > Téléviseurs > TV OLED")
USD = item("US1", "Lave-vaisselle Helio 60 cm 13 couverts", "https://alpha.example/p/us1", "499.00 USD", gtin="3000000000038", brand="Helio")
USED = item("RC1", "Réfrigérateur Ostra combiné 60 cm", "https://alpha.example/p/rc1", "399.00 EUR", gtin="3000000000045",
            brand="Ostra", extra="<g:condition>refurbished</g:condition>")
ACC = item("AC1", "Filtre pour aspirateur balai", "https://alpha.example/p/ac1", "19.90 EUR", brand="Zephyr")
NOPRICE = item("NP1", "Four encastrable pyrolyse Brava 71 L", "https://alpha.example/p/np1", "", brand="Brava")


class Formats(unittest.TestCase):
    def mapping(self, **kw):
        return feeds.Mapping.load({"preset": "google_shopping", **kw})

    def test_google_shopping_item_is_read_as_the_page_would_say_it(self):
        (_, raw), = list(feeds.records(rss(LAVE), self.mapping()))
        r = feeds.normalize(raw, self.mapping(), "xml")
        self.assertEqual((r["price"], r["list_price"], r["currency"]), (549.0, 699.0, "EUR"))      # promo : prix et prix barré
        self.assertEqual(r["url"], "https://alpha.example/p/ll1?color=blanc")                     # utm retiré, le reste gardé
        self.assertEqual((r["valid_until"], r["shipping"], r["availability"]), ("2026-11-08", 0.0, "in_stock"))
        self.assertEqual(r["gtin"], "3000000000014")
        self.assertEqual(r["properties"], {"classe énergétique": "A", "capacité": "8 kg"})
        self.assertEqual(r["category"], "Électroménager > Lavage > Lave-linge hublot")

    def test_french_csv_in_windows_1252_with_decimal_commas(self):
        csv = ("id_produit;nom;marque;ean;prix;prix_barre;disponibilite;url_produit;categorie;caracteristiques\n"
               "A1;Lave-vaisselle Helio 60 cm 13 couverts 44 dB classe C;Helio;3000000000038;1 249,90;1 499,00;En stock;"
               "https://beta.example/p/a1;Cuisine|Lave-vaisselle;Classe énergétique: C | Couverts: 13\n").encode("cp1252")
        m = feeds.Mapping.load({"format": "csv", "encoding": "cp1252", "category_separator": "|",
                                "fields": {"external_id": "id_produit", "title": "nom", "brand": "marque", "gtin": "ean",
                                           "price": "prix", "list_price": "prix_barre", "availability": "disponibilite",
                                           "url": "url_produit", "category": "categorie", "properties": "caracteristiques"}})
        (_, raw), = list(feeds.records(csv, m))
        r = feeds.normalize(raw, m, "csv")
        self.assertEqual((r["price"], r["list_price"], r["availability"]), (1249.9, 1499.0, "in_stock"))
        self.assertEqual(r["category"], "Cuisine > Lave-vaisselle")
        self.assertEqual(r["properties"], {"classe énergétique": "C", "couverts": "13"})

    def test_jsonl_gzip_and_nested_fields(self):
        lines = [{"sku": "J1", "name": "TV QLED Brava 65 pouces", "url": "https://gamma.example/j1", "price": {"amount": "899.99"},
                  "stock": 0, "ean": "3000000000052"}]
        raw = gzip.compress("\n".join(json.dumps(x) for x in lines * 2).encode())
        m = feeds.Mapping.load({"fields": {"external_id": "sku", "title": "name", "url": "url", "price": "price.amount",
                                           "availability": "stock", "gtin": "ean"}})
        rows = list(feeds.records(raw, m))
        self.assertEqual(len(rows), 2)
        r = feeds.normalize(rows[0][1], m, "jsonl")
        self.assertEqual((r["price"], r["availability"], r["gtin"]), (899.99, "out_of_stock", "3000000000052"))

    def test_values_are_read_without_guessing(self):
        self.assertEqual(feeds.money("1 299,99 €"), (1299.99, "EUR"))
        self.assertEqual(feeds.money("EUR 549"), (549.0, "EUR"))
        self.assertEqual(feeds.money("499.00 USD"), (499.0, "USD"))
        self.assertEqual(feeds.availability("Rupture de stock"), "out_of_stock")
        self.assertEqual(feeds.availability("12"), "in_stock")
        self.assertEqual(feeds.availability("à voir en magasin"), "unknown")             # rien de deviné
        self.assertEqual(feeds.end_date("30/11/2026"), "2026-11-30")
        self.assertIsNone(feeds.normalize({"title": "x", "url": "u", "price": "1", "gtin": "3000000000018"},
                                          feeds.Mapping.load({"fields": {"title": "title", "url": "url", "price": "price",
                                                                         "gtin": "gtin"}}))["gtin"])   # clé de contrôle fausse
        self.assertIsNone(feeds.clean_url("javascript:alert(1)"))

    def test_a_mapping_says_what_is_wrong(self):
        with self.assertRaisesRegex(feeds.FeedError, "option inconnue"):
            feeds.Mapping.load({"fields": {"title": "t", "url": "u", "price": "p"}, "sep": ";"})
        with self.assertRaisesRegex(feeds.FeedError, "champ inconnu"):
            feeds.Mapping.load({"fields": {"title": "t", "url": "u", "price": "p", "prix_fou": "x"}})
        with self.assertRaisesRegex(feeds.FeedError, "obligatoire"):
            feeds.Mapping.load({"fields": {"title": "t", "url": "u"}})
        with self.assertRaisesRegex(feeds.FeedError, "préréglage inconnu"):
            feeds.Mapping.load({"preset": "awin_magique"})
        with self.assertRaisesRegex(feeds.FeedError, "disponibilité"):
            feeds.Mapping.load({"fields": {"title": "t", "url": "u", "price": "p"}, "availability": {"oui": "peut-être"}})

    def test_probe_recognizes_google_shopping_and_proposes_a_csv_mapping(self):
        self.assertEqual(feeds.probe(rss(LAVE, TV))["proposed"], {"preset": "google_shopping"})
        info = feeds.probe("ID;Nom;Marque;EAN;Prix TTC;Prix barré;Lien produit;Catégorie\n1;Lave-linge X;Kessler;3000000000014;"
                           "549;699;https://b.example/1;Lavage\n".encode())
        self.assertEqual(info["delimiter"], ";")
        self.assertEqual(info["proposed"]["fields"], {"external_id": "ID", "title": "Nom", "url": "Lien produit", "price": "Prix TTC",
                                                       "list_price": "Prix barré", "gtin": "EAN", "brand": "Marque",
                                                       "category": "Catégorie"})

    def test_probe_prefers_the_usual_product_element_to_a_richer_part_of_it(self):
        ship = ("<g:shipping><g:country>FR</g:country><g:region>IDF</g:region><g:postal_code>75*</g:postal_code>"
                "<g:service>Standard</g:service><g:price>0 EUR</g:price><g:min_handling_time>1</g:min_handling_time></g:shipping>")
        xml = ('<rss xmlns:g="http://base.google.com/ns/1.0"><channel>' + "".join(
            f"<item><title>T{n}</title><link>https://a.example/{n}</link><g:price>10 EUR</g:price>{ship}</item>" for n in range(2))
            + "</channel></rss>").encode()
        self.assertEqual(feeds.probe(xml)["item"], "item")                        # pas « shipping », plus fourni

    def test_broken_files_are_errors(self):
        m = self.mapping()
        with self.assertRaisesRegex(feeds.FeedError, "XML illisible"):
            list(feeds.records(b"<rss><channel><item><title>x</title>", m))
        with self.assertRaisesRegex(feeds.FeedError, "aucun élément produit"):
            list(feeds.records(b"<rss><channel></channel></rss>", m))


class Contract(unittest.TestCase):
    def test_check_refuses_with_a_reason_and_keeps_what_it_can(self):
        base = {"url": "https://a.example/p", "title": "Lave-linge", "price": 500.0, "currency": "EUR", "availability": "in_stock"}
        self.assertEqual(contract.check({**base, "currency": "USD"})[1], "devise USD refusée")
        self.assertEqual(contract.check({**base, "price": None})[1], "prix manquant")
        self.assertEqual(contract.check({**base, "condition": "used"})[1], "occasion ou reconditionné")
        rec, why = contract.check({**base, "list_price": 5000.0})                  # −90 % : prix barré écarté, offre gardée
        self.assertIsNone(why)
        self.assertEqual((rec["list_price"], rec["notes"]), (None, ["prix barré invraisemblable écarté"]))


class Registry(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "feeds").mkdir()
        (self.dir / "feeds" / "boulanger.json").write_text(json.dumps({"preset": "google_shopping"}), encoding="utf-8")

    def write(self, data):
        f = self.dir / "sources.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        return str(f)

    def test_a_feed_replaces_the_pages_and_its_secret_comes_from_the_environment(self):
        path = self.write({"boulanger": {"kind": "feed", "network": "kwanko", "url": "https://flux.example/b?key=${DEALS_FEED_B}",
                                         "mapping": "feeds/boulanger.json"}})
        specs = registry.load(path, env={"DEALS_FEED_B": "s3cr3t"})
        b = specs["boulanger"]
        self.assertEqual((b["kind"], b["name"], b["url"]), ("feed", "Boulanger", "https://flux.example/b?key=s3cr3t"))
        self.assertNotIn("url", registry.public(b))
        self.assertEqual(specs["ikea"]["kind"], "site")                            # les autres restent celles du code
        self.assertNotIn("boulanger", registry.sites(specs))

    def test_invalid_sources_stop_with_their_name(self):
        with self.assertRaisesRegex(ValueError, "boulanger : variable d'environnement DEALS_FEED_B absente"):
            registry.load(self.write({"boulanger": {"kind": "feed", "url": "https://f/${DEALS_FEED_B}", "mapping": "feeds/boulanger.json"}}),
                          env={})
        with self.assertRaisesRegex(ValueError, "fnac : name manquant"):
            registry.load(self.write({"fnac": {"kind": "feed", "url": "x", "mapping": {"preset": "google_shopping"}}}), env={})
        with self.assertRaisesRegex(ValueError, "kind 'api'"):
            registry.load(self.write({"darty": {"kind": "api"}}), env={})
        disabled = registry.load(self.write({"fnac": {"kind": "feed", "name": "Fnac", "enabled": False, "url": "https://f/${X}",
                                                      "mapping": {"preset": "google_shopping"}}}), env={})
        self.assertFalse(disabled["fnac"]["enabled"])                              # désactivée : rien à résoudre

    def test_probe_reads_a_sample_at_the_source_address_without_ever_showing_it(self):
        """deploy/README.md : l'échantillon d'un flux se lit par sa source, même désactivée (on écrit sa correspondance
        avant de l'activer) ; l'adresse, qui porte les identifiants du réseau, ne passe ni par la ligne de commande ni
        par l'historique du shell, et n'apparaît dans aucun message, même d'erreur."""
        import io
        import os
        from contextlib import redirect_stdout
        from unittest import mock

        from deals import cli
        secret = self.dir / "jeton-s3cr3t"
        secret.mkdir()
        (secret / "flux.xml").write_bytes(rss(LAVE, TV))
        path = self.write({"fnac": {"kind": "feed", "name": "Fnac", "enabled": False, "url": "${DEALS_FEED_FNAC}/flux.xml",
                                    "mapping": "feeds/fnac.json"}})              # la correspondance n'existe pas encore

        def run(env):
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"DEALS_SOURCES": path, **env}), redirect_stdout(out):
                try:
                    cli.main(["--db", str(self.dir / "p.sqlite"), "probe", "--source", "fnac"])
                    return 0, out.getvalue()
                except SystemExit as e:
                    return e.code, out.getvalue()
        code, out = run({"DEALS_FEED_FNAC": str(secret)})
        self.assertEqual(code, 0, out)
        self.assertIn('"preset": "google_shopping"', out)
        self.assertNotIn("s3cr3t", out)
        code, out = run({"DEALS_FEED_FNAC": str(self.dir / "autre-s3cr3t")})   # introuvable : l'erreur ne le dit pas
        self.assertIn("${DEALS_FEED_FNAC}", str(code))
        self.assertNotIn("s3cr3t", str(code) + out)
        code, _ = run({})
        self.assertIn("variable d'environnement DEALS_FEED_FNAC absente", str(code))
        with mock.patch.dict(os.environ, {"DEALS_SOURCES": path}), self.assertRaises(SystemExit) as e:
            cli.main(["--db", str(self.dir / "p.sqlite"), "probe", "--source", "ikea"])   # une source « site »
        self.assertIn("n'est pas une source « feed »", str(e.exception.code))


class Ingestion(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.store = Store(str(self.dir / "t.sqlite"))
        self.addCleanup(self.store.close)
        self.now = T0
        self.market = Market(self.store, clock=lambda: self.now)
        self.files = {"alpha": rss(LAVE, TV, USD, USED, ACC, NOPRICE)}
        self.specs = {"alpha": {"key": "alpha", "name": "Alpha", "kind": "feed", "enabled": True, "families": [],
                                "url": "https://flux.example/alpha?token=SECRET", "url_template": "https://flux.example/alpha?token=${T}",
                                "mapping": feeds.Mapping.load({"preset": "google_shopping"})}}
        crawler = Crawler(self.market, None, {}, clock=lambda: self.now)
        self.c = Collector(self.store, self.market, crawler, self.specs, raw_dir=str(self.dir / "raw"),
                           transport=self.fetch, clock=lambda: self.now)

    def fetch(self, spec):
        f = self.files[spec["key"]]
        if isinstance(f, Exception):
            raise f
        return f

    def count(self, table):
        return self.store.q(f"SELECT COUNT(*) n FROM {table}", one=True)["n"]

    def test_a_feed_becomes_offers_with_their_trace(self):
        stat, results = self.c.ingest("alpha", cid="nuit-1")
        self.assertEqual((stat["received"], stat["accepted"], stat["rejected"], stat["ignored"]), (6, 2, 3, 1))
        self.assertEqual(stat["reasons"], {"devise USD refusée": 1, "occasion ou reconditionné": 1, "prix manquant": 1, "accessoire": 1})
        self.assertFalse(stat["broken"])
        b = batches.get(self.store, stat["batch"])
        self.assertEqual((b["status"], b["accepted"], b["rejected"], b["ignored"]), ("partial", 2, 3, 1))   # 60 % refusés
        self.assertTrue(Path(b["raw_path"]).exists())
        self.assertEqual(batches.read_raw(b["raw_path"]), self.files["alpha"])
        self.assertEqual(b["checksum"], batches.checksum(self.files["alpha"]))
        self.assertEqual(self.count("batch_rejects"), 3)
        o = self.store.q("SELECT * FROM offers WHERE external_id='LL1'", one=True)
        self.assertEqual((o["url"], o["source"], o["batch_id"], o["status"]), ("https://alpha.example/p/ll1?color=blanc", "alpha", b["id"], "active"))
        p = self.store.q("SELECT * FROM prices WHERE offer_id=?", (o["id"],), one=True)
        self.assertEqual((p["price"], p["was"], p["shipping"], p["batch_id"], p["source"], p["valid_until"]),
                         (549.0, 699.0, 0.0, b["id"], "feed:xml", "2026-11-08"))
        tv = self.store.q("SELECT availability FROM prices p JOIN offers o ON o.id=p.offer_id WHERE o.external_id='TV1'", one=True)
        self.assertEqual(tv["availability"], "out_of_stock")
        attrs = json.loads(self.store.q("SELECT attributes FROM products WHERE gtin='3000000000014'", one=True)["attributes"])
        self.assertEqual(attrs.get("energy_class"), "A")                           # la caractéristique déclarée nourrit l'ontologie

    def test_the_same_file_again_writes_no_new_price(self):
        self.c.ingest("alpha")
        rows = self.count("prices")
        self.now += 86400
        stat, _ = self.c.ingest("alpha")
        self.assertEqual((self.count("prices"), stat["changed"]), (rows, 0))
        self.assertEqual(self.store.q("SELECT MAX(last_seen) t FROM prices", one=True)["t"], self.now)   # reconfirmé

    def test_a_price_change_is_one_new_row(self):
        self.c.ingest("alpha")
        rows = self.count("prices")
        self.now += 86400
        self.files["alpha"] = rss(LAVE.replace("549.00 EUR", "529.00 EUR"), TV)
        stat, _ = self.c.ingest("alpha")
        self.assertEqual((self.count("prices"), stat["changed"]), (rows + 1, 1))

    def test_a_truncated_feed_deletes_nothing(self):
        self.c.ingest("alpha")
        self.files["alpha"] = rss(LAVE)                                           # le téléviseur manque ce soir
        self.now += 86400
        self.c.ingest("alpha")
        P.publish(self.store, DAY.fromordinal(DAY.toordinal() + 1), self.now)
        self.assertEqual(self.count("catalog"), 2)                                # toujours publié : il vieillit, rien de plus
        self.assertEqual(self.store.q("SELECT status FROM offers WHERE external_id='TV1'", one=True)["status"], "active")

    def test_an_unreadable_feed_is_a_failure_not_an_empty_catalog(self):
        self.c.ingest("alpha")
        P.publish(self.store, DAY, self.now)
        self.files["alpha"] = b"<html>502 Bad Gateway"
        stat, results = self.c.ingest("alpha")
        self.assertEqual((stat["broken"], results), (True, []))
        self.assertIs(sources.failed(stat), True)
        self.assertEqual(batches.get(self.store, stat["batch"])["status"], "failed")
        self.files["alpha"] = OSError("https://flux.example/alpha?token=SECRET injoignable")
        stat, _ = self.c.ingest("alpha")
        self.assertNotIn("SECRET", stat["error"])                                 # l'identifiant du réseau ne fuit pas
        self.assertEqual(self.count("catalog"), 2)

    def test_dry_run_reads_and_checks_without_writing(self):
        stat, _ = self.c.ingest("alpha", dry_run=True)
        self.assertEqual((stat["accepted"], stat["rejected"]), (2, 3))
        self.assertEqual((self.count("offers"), self.count("prices"), self.count("batch_rejects")), (0, 0, 0))
        self.assertEqual(batches.listing(self.store)[0]["status"], "dry_run")

    def test_replay_rereads_the_kept_file_of_the_last_batch_only(self):
        first, _ = self.c.ingest("alpha")
        rows = self.count("prices")
        stat, _ = self.c.replay("alpha")
        self.assertEqual((self.count("prices"), stat["accepted"]), (rows, 2))      # idempotent
        self.assertEqual(batches.get(self.store, stat["batch"])["replay_of"], first["batch"])
        self.now += 86400
        self.c.ingest("alpha")
        self.store.x("UPDATE batches SET status='failed' WHERE id=(SELECT MAX(id) FROM batches)")   # le dernier lot raté
        self.store.x("INSERT INTO batches(source, kind, started_at, status) VALUES ('alpha', 'feed', ?, 'succeeded')", (self.now,))
        with self.assertRaisesRegex(ValueError, "aucun lot récent"):
            self.c.replay("alpha")

    def test_replay_writes_at_the_time_the_file_was_read(self):
        self.c.ingest("alpha")
        self.now += 86400                                                         # le lendemain, sans nouveau flux
        self.c.replay("alpha")
        self.assertEqual(self.store.q("SELECT MAX(last_seen) t FROM prices", one=True)["t"], T0)   # pas « frais » d'aujourd'hui

    def test_replay_rereads_the_latest_batch_not_an_older_one(self):
        self.c.ingest("alpha")
        self.now += 86400
        self.files["alpha"] = rss(LAVE.replace("549.00 EUR", "529.00 EUR"), TV)
        self.c.ingest("alpha")
        rows = self.count("prices")
        stat, _ = self.c.replay("alpha")
        self.assertEqual((self.count("prices"), stat["changed"]), (rows, 0))      # le dernier fichier : rien ne revient en arrière
        last = self.store.q("SELECT price FROM prices p JOIN offers o ON o.id=p.offer_id WHERE o.external_id='LL1' "
                            "ORDER BY p.first_seen DESC LIMIT 1", one=True)
        self.assertEqual(last["price"], 529.0)

    def test_a_readable_feed_without_any_offer_is_a_failure(self):
        self.files["alpha"] = rss(USD, USED, ACC)                                 # lisible, mais rien à retenir
        stat, _ = self.c.ingest("alpha")
        self.assertEqual((stat["accepted"], stat["broken"]), (0, True))
        self.assertIs(sources.failed(stat), True)
        self.assertEqual(batches.get(self.store, stat["batch"])["status"], "partial")

    def test_variants_of_one_page_keep_the_available_cheapest(self):
        a = item("V1", "Lave-linge hublot Kessler WM8 8 kg", "https://alpha.example/p/v", "499.00 EUR", avail="out of stock",
                 gtin="3000000000069", brand="Kessler", ptype="Lave-linge")
        b = item("V2", "Lave-linge hublot Kessler WM8 8 kg", "https://alpha.example/p/v", "529.00 EUR", gtin="3000000000069",
                 brand="Kessler", ptype="Lave-linge")
        self.files["alpha"] = rss(a, b)
        stat, _ = self.c.ingest("alpha")
        self.assertEqual((stat["accepted"], stat["ignored"]), (1, 1))
        self.assertEqual(self.store.q("SELECT price FROM prices", one=True)["price"], 529.0)

    def test_a_feed_and_the_pages_meet_on_the_same_offer(self):
        with self.store.tx():
            oid = self.market.track("https://alpha.example/p/ll1?color=blanc", "alpha", "Alpha")
        self.c.ingest("alpha")
        self.assertEqual(self.store.q("SELECT id FROM offers WHERE external_id='LL1'", one=True)["id"], oid)

    def test_many_refusals_are_all_counted_and_200_kept_as_samples(self):
        bad = [item(f"X{n}", "Lave-linge hublot Kessler WM8 8 kg", f"https://alpha.example/p/x{n}", "") for n in range(250)]
        self.files["alpha"] = rss(LAVE, *bad)
        stat, _ = self.c.ingest("alpha")
        self.assertEqual((stat["accepted"], stat["rejected"], stat["reasons"]["prix manquant"]), (1, 250, 250))
        self.assertEqual(self.count("batch_rejects"), batches.MAX_REJECTS)
        self.assertEqual(batches.get(self.store, stat["batch"])["rejected"], 250)

    def test_a_feed_broken_halfway_writes_nothing(self):
        self.files["alpha"] = rss(LAVE, TV)[:-40]                                 # coupé en plein milieu
        stat, results = self.c.ingest("alpha")
        self.assertEqual((stat["broken"], results, self.count("prices")), (True, [], 0))
        self.assertEqual(batches.get(self.store, stat["batch"])["status"], "failed")

    def test_a_disabled_source_is_refused_by_name(self):
        self.specs["beta"] = {"key": "beta", "name": "Beta", "kind": "feed", "enabled": False, "mapping": None}
        with self.assertRaisesRegex(ValueError, "beta : source désactivée"):
            self.c.ingest("beta")

    def test_nightly_merges_feed_stats_for_the_night_and_the_agent(self):
        stats = self.c.nightly(["alpha"], cid="nuit-1")
        st = stats["retailers"]["alpha"]
        self.assertEqual((st["kind"], st["accepted"], st["name"]), ("feed", 2, "Alpha"))
        self.assertIs(sources.failed(st), False)
        self.assertEqual(stats["offers"], 2)
        self.assertTrue(stats.get("run"))


if __name__ == "__main__":
    unittest.main()


class FeedNights(unittest.TestCase):
    """Un flux injoignable, de bout en bout dans la vraie nuit : relancé une fois, compté, mis de côté au bout de trois
    nuits ratées, sans jamais vider le catalogue ; quand il répond de nouveau, l'agent propose de le reprendre."""

    def test_an_unreachable_feed_is_retried_counted_set_aside_then_proposed_again(self):
        from datetime import timedelta

        from deals import config, demo, night
        from deals.accounts import Outbox
        start = date(2025, 10, 1)
        s = Store(str(Path(tempfile.mkdtemp()) / "n.sqlite"))
        self.addCleanup(s.close)
        w = demo.world(s, start, mode="feed")
        base, down = w.collector.transport, {"on": False}

        def transport(spec):
            if down["on"] and spec["key"] == "rapido":
                raise OSError("connexion refusée")
            return base(spec)
        w.collector.transport = transport
        settings, box = config.load({}, public_url="https://deals.test"), Outbox()

        def night_(k):
            w.clock.set(start + timedelta(days=k))
            return night.run(s, settings, w.collector, box, w.retailers, set(demo.RULES), clock=w.clock)

        for k in range(6):
            night_(k)
        before = s.q("SELECT COUNT(*) n FROM catalog", one=True)["n"]
        down["on"] = True
        out = night_(6)
        self.assertIs(out["crawl"]["retailers"]["rapido"]["broken"], True)
        retry = s.q("SELECT status FROM actions WHERE action='retry_source' AND entity='rapido'", one=True)
        self.assertEqual(retry["status"], "unverified")                              # relancé une fois, sans effet
        self.assertEqual(s.q("SELECT status, failures FROM sources WHERE key='rapido'", one=True), {"status": "degraded", "failures": 1})
        night_(7)
        night_(8)
        self.assertEqual(s.q("SELECT status FROM sources WHERE key='rapido'", one=True)["status"], "disabled")
        self.assertGreater(s.q("SELECT COUNT(*) n FROM catalog", one=True)["n"], 0.9 * before)   # les autres enseignes restent
        down["on"] = False
        for k in range(9, 13):
            night_(k)
        proposed = s.q("SELECT status, policy FROM actions WHERE action='enable_source' AND entity='rapido'", one=True)
        self.assertEqual(proposed, {"status": "proposed", "policy": "approval"})      # reprendre : une décision humaine


class FeedHealthAndReport(unittest.TestCase):
    def snap(self, **feed):
        stat = {"name": "Alpha", "kind": "feed", "pages": 100, "accepted": 70, "rejected": 30, "reject_share": 0.3,
                "reasons": {"prix manquant": 30}, "broken": False, "previous_accepted": 80, **feed}
        return {"sources": {"alpha": {**stat, "status": "active", "failures": 0}}, "quarantine": {}, "publish": {}, "missions": {},
                "errors": [], "catalog": {"products": 0, "offers": {}, "reference": {}},
                "freshness": {"products": 0, "fresh": 0, "stale_by_source": {}}, "clicks": {"last_day": 0, "median_7d": 0}}

    def test_rejected_lines_and_a_collapse_are_findings_with_their_runbook(self):
        from deals import health
        kinds = {f["kind"]: f for f in health.findings(self.snap(accepted=30))}
        self.assertEqual(kinds["feed_rejects"]["runbook"], "flux-lignes-refusees")
        self.assertEqual(kinds["feed_collapse"]["evidence"], {"accepted": 30, "before": 80})
        self.assertNotIn("source_failing", kinds)                               # des refus ne sont pas un échec
        calm = {f["kind"] for f in health.findings(self.snap(rejected=5, reject_share=0.05, accepted=79))}
        self.assertEqual(calm & {"feed_rejects", "feed_collapse"}, set())

    def test_the_morning_report_has_a_feed_table_and_says_when_it_fails(self):
        from deals.ingest import report
        d = tempfile.mkdtemp()
        stats = {"day": "2026-10-31", "offers": 2, "products": 2, "to_review": 0, "price_drops": [], "retailers": {
            "alpha": {"name": "Alpha", "kind": "feed", "batch": 7, "received": 6, "accepted": 2, "changed": 1, "rejected": 3,
                      "ignored": 1, "alert": True, "broken": False, "reject_share": 0.6, "reasons": {"prix manquant": 3}},
            "beta": {"name": "Beta", "kind": "feed", "batch": 8, "broken": True, "error": "OSError : connexion refusée", "alert": True}}}
        name = report.write(stats, d)
        text = Path(d, f"{name}.md").read_text(encoding="utf-8")
        self.assertIn("| ⚠ Alpha | 6 | 2 | 1 | 3 | 1 | 7 |", text)
        self.assertIn("⚠ Beta : flux en échec (OSError : connexion refusée)", text)
        self.assertIn("⚠ Alpha : 3 lignes refusées (60 %) : prix manquant (3).", text)
