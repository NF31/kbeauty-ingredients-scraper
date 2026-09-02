"""Synchronise les tables locales (gammes, products) vers Astra DB.

Cree les tables si besoin, TRUNCATE les anciennes donnees de fixture/test,
puis recopie le contenu reel du Cassandra local vers Astra - "prod" recoit
enfin de vraies donnees issues d'un crawl complet, plus des fixtures.

Usage :
    Ajouter ASTRA_TOKEN="AstraCS:..." dans .env (a la racine du repo, deja
    gitignore), ou l'exporter directement dans le shell - les deux marchent.
    python scripts/sync_astra.py
"""

import os

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from dotenv import load_dotenv

load_dotenv()

BUNDLE_PATH = os.path.expanduser(
    "~/projects/kbeauty-ingredients-scraper/.astra-secrets/"
    "secure-connect-kbeauty-ingredients.zip"
)

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
  sku text PRIMARY KEY,
  source_url text,
  name text,
  price decimal,
  currency text,
  availability text,
  rating decimal,
  ratings_count int,
  benefits text,
  description text,
  ingredients_raw text,
  scraped_at timestamp
)
"""


def main():
    token = os.environ["ASTRA_TOKEN"]

    local_cluster = Cluster(["127.0.0.1"], port=9042)
    local_session = local_cluster.connect("kbeauty_ingredients")

    astra_cluster = Cluster(
        cloud={"secure_connect_bundle": BUNDLE_PATH},
        auth_provider=PlainTextAuthProvider("token", token),
    )
    astra_session = astra_cluster.connect("default_keyspace")

    astra_session.execute(CREATE_PRODUCTS_TABLE)

    print("TRUNCATE des anciennes donnees Astra (fixtures de test)...")
    astra_session.execute("TRUNCATE gammes")
    astra_session.execute("TRUNCATE products")

    gammes = list(local_session.execute("SELECT * FROM gammes"))
    products = list(local_session.execute("SELECT * FROM products"))

    insert_gamme = astra_session.prepare(
        """
        INSERT INTO gammes
            (name, source_url, ideal_pour, actions_principales, actifs_cles, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
    )
    for row in gammes:
        astra_session.execute(
            insert_gamme,
            (
                row.name,
                row.source_url,
                row.ideal_pour,
                row.actions_principales,
                row.actifs_cles,
                row.scraped_at,
            ),
        )

    insert_product = astra_session.prepare(
        """
        INSERT INTO products
            (sku, source_url, name, price, currency, availability,
             rating, ratings_count, benefits, description, ingredients_raw, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    for row in products:
        astra_session.execute(
            insert_product,
            (
                row.sku,
                row.source_url,
                row.name,
                row.price,
                row.currency,
                row.availability,
                row.rating,
                row.ratings_count,
                row.benefits,
                row.description,
                row.ingredients_raw,
                row.scraped_at,
            ),
        )

    print(f"{len(gammes)} gammes et {len(products)} products copies vers Astra.")

    print("Verification :")
    print("gammes:", astra_session.execute("SELECT COUNT(*) FROM gammes").one())
    print("products:", astra_session.execute("SELECT COUNT(*) FROM products").one())

    local_session.shutdown()
    local_cluster.shutdown()
    astra_session.shutdown()
    astra_cluster.shutdown()


if __name__ == "__main__":
    main()
