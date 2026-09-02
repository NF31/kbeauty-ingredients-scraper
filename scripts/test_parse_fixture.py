"""Test hors-ligne : valide _extract_product() sur la fixture HTML capturee,
sans solliciter le site (evite le rate-limit Shopify pendant l'iteration).

Usage :
    pytest scripts/test_parse_fixture.py
    # ou, pour rejouer/inspecter manuellement les valeurs extraites :
    python scripts/test_parse_fixture.py
"""

from pathlib import Path

import pytest
from scrapy.http import HtmlResponse

from ingredients_scraper.spiders.uniikon_gammes import UniikonGammesSpider

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_product.html"


@pytest.fixture
def product():
    body = FIXTURE_PATH.read_bytes()
    response = HtmlResponse(
        url="https://uniikon.com/products/gamme-resistance",
        body=body,
        encoding="utf-8",
    )
    spider = UniikonGammesSpider()
    return spider._extract_product(response)


def test_extrait_les_champs_didentification(product):
    # Valeurs figees de fixtures/sample_product.html - si elles bougent,
    # soit la fixture a change, soit le parsing JSON-LD s'est casse.
    assert product["sku"] == "RESISTANCE-KIT COMPLET"
    assert product["name"] == "Gamme Résistance - Kit Complet - Shampooing, masque et sérum"


def test_extrait_le_prix_en_euros(product):
    assert product["price"] == 49.99
    assert product["currency"] == "EUR"


def test_extrait_la_disponibilite_et_la_note(product):
    # rating/ratings_count restent des str a ce stade (Shopify les encode
    # en chaines dans le JSON-LD, contrairement a price qui est un nombre
    # JSON brut) - c'est le pipeline (_to_decimal/_to_int) qui les convertit
    # avant l'insertion Cassandra, pas _extract_product().
    assert product["availability"] == "http://schema.org/InStock"
    assert product["rating"] == "4.9"
    assert product["ratings_count"] == "698"


def test_extrait_la_liste_inci_complete(product):
    # Le parsing des ingredients doit couvrir les deux onglets HTML
    # (Masque + Serum sur cette fixture), pas seulement le premier trouve.
    assert "Aqua (Water)" in product["ingredients_raw"]
    assert "Serum" in product["ingredients_raw"] or "Sérum" in product["ingredients_raw"]


def main():
    body = FIXTURE_PATH.read_bytes()
    response = HtmlResponse(
        url="https://uniikon.com/products/gamme-resistance",
        body=body,
        encoding="utf-8",
    )

    spider = UniikonGammesSpider()
    result = spider._extract_product(response)

    print("sku:", result["sku"])
    print("name:", result["name"])
    print("price:", result["price"], result["currency"])
    print("availability:", result["availability"])
    print("rating:", result["rating"], "/ ratings_count:", result["ratings_count"])
    print("benefits:", result["benefits"])
    print("description:", result["description"][:120], "...")
    print("ingredients_raw (first 200 chars):", result["ingredients_raw"][:200])


if __name__ == "__main__":
    main()
