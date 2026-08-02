from scrapy.spiders import SitemapSpider

from ingredients_scraper.items import GammeItem


class UniikonGammesSpider(SitemapSpider):
    """Spider pedagogique (Phase 4, montee en competence MIAGE).

    Cible choisie apres verification du robots.txt : uniikon.com (Shopify)
    autorise explicitement le crawl public ("User-agent: * / Allow: /") sur
    /products, contrairement aux catalogues d'ingredients cosmetiques
    testes en premier (CosDNA, INCI Beauty, Open Beauty Facts), qui
    bloquent tous explicitement Scrapy et les agents IA/Claude.

    Chaque fiche produit affiche un tableau comparatif de "gammes" (une
    gamme = une ligne de produits capillaires) avec pour chacune : le
    public cible, les actions principales et les actifs cles - assez
    proche dans l'esprit d'un catalogue d'ingredients pour servir de
    donnee d'exemple au pipeline Cassandra.
    """

    name = "uniikon_gammes"
    allowed_domains = ["uniikon.com"]
    sitemap_urls = ["https://uniikon.com/sitemap.xml"]
    # On ignore les sitemaps traduits (/es/...) : une seule langue suffit
    # pour l'exercice, inutile de scraper les doublons.
    sitemap_rules = [(r"^https://uniikon\.com/products/", "parse_product")]

    custom_settings = {
        "USER_AGENT": (
            "kbeauty-montee-competence-bot/1.0 "
            "(projet pedagogique MIAGE, usage non-commercial, "
            "contact: jeaneudes.woto31@gmail.com)"
        ),
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    LABELS = ("Idéal Pour", "Actions Principales", "Actifs Clés")

    def parse_product(self, response):
        for card in response.css("div.card-comparaison div.card-info"):
            name = card.css("b::text").get(default="").strip()
            if not name:
                continue

            values = self._extract_labelled_values(card.css("p"))

            yield GammeItem(
                name=name,
                source_url=response.url,
                ideal_pour=values["Idéal Pour"],
                actions_principales=values["Actions Principales"],
                actifs_cles=values["Actifs Clés"],
            )

    def _extract_labelled_values(self, paragraphs):
        """Chaque bloc commence par un <p> contenant le label en <strong>,
        suivi soit d'un texte inline (meme <p>), soit d'un ou plusieurs
        <p> de contenu jusqu'au label suivant.
        """
        values = {label: "" for label in self.LABELS}
        current_label = None

        for p in paragraphs:
            strong_text = " ".join(p.css("strong::text").getall()).strip()
            matched_label = next(
                (label for label in self.LABELS if label in strong_text), None
            )

            if matched_label:
                current_label = matched_label
                inline_value = " ".join(
                    p.xpath("./strong/following-sibling::text()").getall()
                ).strip()
                if inline_value:
                    values[current_label] = inline_value
            elif current_label:
                value = " ".join(p.css("::text").getall()).strip()
                if value:
                    existing = values[current_label]
                    values[current_label] = f"{existing} {value}".strip()

        return values
