import json

from scrapy.spiders import SitemapSpider

from ingredients_scraper.items import GammeItem, ProductItem


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

        product_item = self._extract_product(response)
        if product_item:
            yield product_item

    def _extract_product(self, response):
        """Chaque page produit embarque un bloc JSON-LD schema.org/Product
        (sku, prix, note Loox) et des onglets "Benefices"/"Ingredients"
        (tab-content-0 / tab-content-2) - plus riche et plus fiable a
        parser que le tableau de gammes, qui lui est duplique sur toutes
        les pages.
        """
        product_data = None
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("@type") == "Product":
                product_data = data
                break

        if not product_data:
            return None

        offer = (product_data.get("offers") or [{}])[0]
        rating = product_data.get("aggregateRating") or {}

        # La page duplique ces blocs (versions desktop/mobile identiques) :
        # on ne garde que la premiere occurrence de chaque onglet.
        benefits_block = response.css(".tab-content-0")[:1]
        benefits = " | ".join(benefits_block.css(".check-item::text").getall()).strip()

        ingredients_block = response.css(".tab-content-2")[:1]
        ingredients_raw = " ".join(ingredients_block.css("::text").getall()).strip()

        return ProductItem(
            sku=offer.get("sku") or product_data.get("sku"),
            source_url=response.url,
            name=product_data.get("name", "").strip(),
            price=offer.get("price"),
            currency=offer.get("priceCurrency"),
            availability=offer.get("availability"),
            rating=rating.get("ratingValue"),
            ratings_count=rating.get("ratingCount"),
            benefits=benefits,
            description=product_data.get("description", "").strip(),
            ingredients_raw=ingredients_raw,
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
