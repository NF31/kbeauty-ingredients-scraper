"""Extension Scrapy qui enrichit la transaction New Relic du run.

Le cycle de vie de la transaction est gere par le lanceur
`ingredients_scraper.run` (decorateur `@background_task`). Cette extension se
contente d'ajouter, en fin de crawl, quelques compteurs de `crawler.stats`
en attributs personnalises sur la transaction courante, et de marquer la
transaction en erreur si le crawl s'est arrete anormalement.

Ne s'active que si NEW_RELIC_LICENSE_KEY est present dans l'environnement
(cas conteneur cloud). En local (`scrapy crawl` sans cette variable) elle
leve NotConfigured et le crawl se deroule normalement, sans agent.
"""

import os

from scrapy import signals
from scrapy.exceptions import NotConfigured

try:
    import newrelic.agent
except ImportError:  # dependance absente d'un venv de dev minimal
    newrelic = None


class NewRelicJobExtension:
    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        if newrelic is None or not os.environ.get("NEW_RELIC_LICENSE_KEY"):
            raise NotConfigured("New Relic desactive (NEW_RELIC_LICENSE_KEY absent)")

        ext = cls(crawler.stats)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_closed(self, spider, reason):
        newrelic.agent.add_custom_attributes(
            [
                ("scrapy.finish_reason", reason),
                ("scrapy.items_scraped", self.stats.get_value("item_scraped_count", 0)),
                ("scrapy.responses", self.stats.get_value("response_received_count", 0)),
                ("scrapy.errors", self.stats.get_value("log_count/ERROR", 0)),
                ("scrapy.retries", self.stats.get_value("retry/count", 0)),
            ]
        )
        # reason != "finished" => arret anormal (shutdown, exception fatale) :
        # la transaction ressort dans "Errors".
        if reason != "finished":
            newrelic.agent.notice_error()
