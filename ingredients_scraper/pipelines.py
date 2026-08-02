# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from datetime import datetime, timezone

from cassandra.cluster import Cluster
from itemadapter import ItemAdapter


class CassandraPipeline:
    """Pousse chaque item dans Cassandra (kbeauty_ingredients.gammes).

    Connexion ouverte une seule fois pour tout le run du spider
    (open_spider/close_spider), pas par item - c'est le driver Cassandra
    lui-meme qui gere le pool de connexions au cluster.
    """

    def open_spider(self, spider):
        self.cluster = Cluster(["127.0.0.1"], port=9042)
        self.session = self.cluster.connect("kbeauty_ingredients")
        self.insert_stmt = self.session.prepare(
            """
            INSERT INTO gammes
                (name, source_url, ideal_pour, actions_principales, actifs_cles, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """
        )

    def close_spider(self, spider):
        self.session.shutdown()
        self.cluster.shutdown()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        self.session.execute(
            self.insert_stmt,
            (
                adapter.get("name"),
                adapter.get("source_url"),
                adapter.get("ideal_pour"),
                adapter.get("actions_principales"),
                adapter.get("actifs_cles"),
                datetime.now(timezone.utc),
            ),
        )
        return item
