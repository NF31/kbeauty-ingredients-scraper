# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from cassandra.cluster import Cluster
from itemadapter import ItemAdapter

from ingredients_scraper.items import GammeItem, ProductItem


class CassandraPipeline:
    """Pousse chaque item dans Cassandra (kbeauty_ingredients.gammes ou
    .products selon le type d'item).

    Connexion ouverte une seule fois pour tout le run du spider
    (open_spider/close_spider), pas par item - c'est le driver Cassandra
    lui-meme qui gere le pool de connexions au cluster.
    """

    def open_spider(self, spider):
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
