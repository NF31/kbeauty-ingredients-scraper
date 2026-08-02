# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class GammeItem(scrapy.Item):
    name = scrapy.Field()
    source_url = scrapy.Field()
    ideal_pour = scrapy.Field()
    actions_principales = scrapy.Field()
    actifs_cles = scrapy.Field()


class ProductItem(scrapy.Item):
    sku = scrapy.Field()
    source_url = scrapy.Field()
    name = scrapy.Field()
    price = scrapy.Field()
    currency = scrapy.Field()
    availability = scrapy.Field()
    rating = scrapy.Field()
    ratings_count = scrapy.Field()
    benefits = scrapy.Field()
    description = scrapy.Field()
    ingredients_raw = scrapy.Field()
