"""Point d'entree du conteneur : lance le crawl uniikon_gammes en le
rattachant a une transaction de fond New Relic.

Pourquoi ce lanceur plutot qu'un simple `scrapy crawl` : l'agent Python
n'instrumente pas Scrapy (reacteur Twisted). Une transaction ouverte depuis
une extension Scrapy, a cheval sur deux signaux (spider_opened /
spider_closed), s'est averee fragile ("no active trace" a la fermeture).
Ici, tout le crawl s'execute a l'interieur d'un seul appel de fonction
decore `@background_task` : la transaction reste active du debut a la fin,
sur le meme thread que le reacteur.

L'enrichissement (nombre d'items, d'erreurs, raison d'arret) est ajoute par
NewRelicJobExtension sur la transaction courante.

Sans NEW_RELIC_LICENSE_KEY dans l'environnement (run local), `background_task`
et `register_application` sont des no-op : le crawl se deroule normalement.
"""

import os

import newrelic.agent
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from ingredients_scraper.spiders.uniikon_gammes import UniikonGammesSpider


@newrelic.agent.background_task(name="uniikon_gammes", group="Scrapy")
def _crawl():
    process = CrawlerProcess(get_project_settings())
    process.crawl(UniikonGammesSpider)
    process.start()  # bloque jusqu'a la fin du crawl


def main():
    if os.environ.get("NEW_RELIC_LICENSE_KEY"):
        # Attendre que l'appli soit enregistree aupres du collecteur : sinon,
        # sur un job de quelques minutes, la transaction demarre avant que la
        # connexion soit prete et n'est jamais rattachee.
        newrelic.agent.register_application(timeout=25.0)

    try:
        _crawl()
    finally:
        # Flush synchrone avant la fin du process (job court : sans ca, on
        # sort avant l'envoi "harvest" et rien ne remonte).
        newrelic.agent.shutdown_agent(timeout=15.0)


if __name__ == "__main__":
    main()
