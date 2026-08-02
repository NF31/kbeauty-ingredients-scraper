"""Test manuel hors-ligne : valide _extract_product() sur la fixture HTML
capturee, sans solliciter le site (evite le rate-limit Shopify).

Usage :
    python scripts/test_parse_fixture.py
"""

from pathlib import Path

from scrapy.http import HtmlResponse

from ingredients_scraper.spiders.uniikon_gammes import UniikonGammesSpider

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_product.html"


def main():
    body = FIXTURE_PATH.read_bytes()
    response = HtmlResponse(
        url="https://uniikon.com/products/gamme-resistance",
        body=body,
        encoding="utf-8",
    )

    spider = UniikonGammesSpider()
    product = spider._extract_product(response)

    print("sku:", product["sku"])
    print("name:", product["name"])
    print("price:", product["price"], product["currency"])
    print("availability:", product["availability"])
    print("rating:", product["rating"], "/ ratings_count:", product["ratings_count"])
    print("benefits:", product["benefits"])
    print("description:", product["description"][:120], "...")
    print("ingredients_raw (first 200 chars):", product["ingredients_raw"][:200])


if __name__ == "__main__":
    main()
