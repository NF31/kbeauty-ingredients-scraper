# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from itemadapter import ItemAdapter

from ingredients_scraper.items import GammeItem, ProductItem

# Chemin par defaut du secure connect bundle, relatif au repertoire courant
# (racine du repo en local comme en conteneur - `scrapy crawl` s'execute
# toujours depuis la racine, WORKDIR /app dans le Dockerfile). Surchargeable
# via ASTRA_SECURE_CONNECT_BUNDLE si le bundle vit ailleurs.
DEFAULT_ASTRA_BUNDLE_PATH = os.path.join(
    ".astra-secrets", "secure-connect-kbeauty-ingredients.zip"
)


class CassandraPipeline:
    """Pousse chaque item dans Cassandra (gammes ou products selon le type
    d'item).

    Connexion ouverte une seule fois pour tout le run du spider
    (open_spider/close_spider), pas par item - c'est le driver Cassandra
    lui-meme qui gere le pool de connexions au cluster.

    Deux modes, selon la presence de ASTRA_TOKEN dans l'environnement :
    - Astra DB (prod/conteneur) : connexion cloud via le secure connect
      bundle, keyspace "default_keyspace" (seul keyspace disponible sur le
      tier Astra Serverless gratuit - impossible d'y creer
      "kbeauty_ingredients" comme en local).
    - Cassandra local (dev, `docker compose up -d cassandra` du repo
      kbeauty-ecosystem) : 127.0.0.1:9042, keyspace "kbeauty_ingredients"
      (cree par schema.cql). C'est le mode par defaut si ASTRA_TOKEN est
      absent, pour ne rien casser du usage local existant.
    """

    def open_spider(self, spider):
        astra_token = os.environ.get("ASTRA_TOKEN")

        if astra_token:
            bundle_path = os.environ.get(
                "ASTRA_SECURE_CONNECT_BUNDLE", DEFAULT_ASTRA_BUNDLE_PATH
            )
            self.cluster = Cluster(
                cloud={"secure_connect_bundle": bundle_path},
                auth_provider=PlainTextAuthProvider("token", astra_token),
            )
            self.session = self.cluster.connect("default_keyspace")
        else:
            self.cluster = Cluster(["127.0.0.1"], port=9042)
            self.session = self.cluster.connect("kbeauty_ingredients")
        self.insert_gamme_stmt = self.session.prepare(
            """
            INSERT INTO gammes
                (name, source_url, ideal_pour, actions_principales, actifs_cles, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """
        )
        self.insert_product_stmt = self.session.prepare(
            """
            INSERT INTO products
                (sku, source_url, name, price, currency, availability,
                 rating, ratings_count, benefits, description, ingredients_raw, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )

    def close_spider(self, spider):
        self.session.shutdown()
        self.cluster.shutdown()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if isinstance(item, GammeItem):
            self.session.execute(
                self.insert_gamme_stmt,
                (
                    adapter.get("name"),
                    adapter.get("source_url"),
                    adapter.get("ideal_pour"),
                    adapter.get("actions_principales"),
                    adapter.get("actifs_cles"),
                    datetime.now(timezone.utc),
                ),
            )
        elif isinstance(item, ProductItem):
            self.session.execute(
                self.insert_product_stmt,
                (
                    adapter.get("sku"),
                    adapter.get("source_url"),
                    adapter.get("name"),
                    self._to_decimal(adapter.get("price")),
                    adapter.get("currency"),
                    adapter.get("availability"),
                    self._to_decimal(adapter.get("rating")),
                    self._to_int(adapter.get("ratings_count")),
                    adapter.get("benefits"),
                    adapter.get("description"),
                    adapter.get("ingredients_raw"),
                    datetime.now(timezone.utc),
                ),
            )

        return item

    @staticmethod
    def _to_decimal(value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None

    @staticmethod
    def _to_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
