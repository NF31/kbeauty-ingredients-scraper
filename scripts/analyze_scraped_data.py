"""Exploitation des donnees scrapees (Phase 4 avancee, montee en competence
MIAGE) : plutot que de laisser les 67 fiches produit uniikon.com dormir dans
Cassandra, on en tire deux analyses concretes, croisees avec le catalogue
kbeauty-shop (Neon) :

1. Frequence des ingredients INCI chez uniikon.com - quels actifs reviennent
   le plus souvent dans un catalogue capillaire concurrent.
2. Recouvrement : parmi ces ingredients frequents, lesquels sont deja
   presents dans le catalogue kbeauty-shop (products.ingredients_inci) et
   lesquels n'y sont pas du tout - un vrai signal "gap catalogue", pas
   juste une statistique isolee.
3. Positionnement prix (EUR) : uniikon vs kbeauty-shop, sur les produits
   publies uniquement.

Usage :
    export NEON_DB_URL="postgresql://...neon.tech/neondb?sslmode=require"
    python scripts/analyze_scraped_data.py
"""

import os
import re
from collections import Counter

import psycopg2
from cassandra.cluster import Cluster

TOP_N = 15

# Termes generiques de formulation (solvants, emulsifiants de base,
# conservateurs universels) qui reviennent dans presque tout produit
# cosmetique et n'apportent aucun signal "actif differenciant" - exclus
# pour que le top ingredients reflete de vrais choix de formulation.
NOISE_INGREDIENTS = {
    "aqua",
    "water",
    "aqua (water)",
    "parfum",
    "fragrance",
    "alcohol denat.",
    "citric acid",
    "sodium benzoate",
    "potassium sorbate",
    "benzyl alcohol",
    "propylene glycol",
    "glycerin",
    "limonene",
    "linalool",
    "citronellol",
    "geraniol",
    "hexyl cinnamal",
    "cinnamal",
}


def fetch_uniikon_products():
    cluster = Cluster(["127.0.0.1"], port=9042)
    session = cluster.connect("kbeauty_ingredients")
    rows = list(session.execute("SELECT name, price, ingredients_raw FROM products"))
    session.shutdown()
    cluster.shutdown()
    return rows


def fetch_kbeauty_shop_catalog():
    db_url = os.environ["NEON_DB_URL"]
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.name, p.ingredients_inci, v.price_cents
            FROM products p
            JOIN product_variants v ON v.product_id = p.id AND v.is_default = true
            WHERE p.status = 'published'
            """
        )
        rows = cur.fetchall()
    conn.close()
    return rows


def split_inci(raw):
    """Une liste INCI est une chaine separee par des virgules, avec parfois
    des sauts de ligne / retours chariot injectes par le parsing HTML
    (cf. pipelines.py) - normalisee en minuscules pour le comptage.
    """
    if not raw:
        return []
    parts = re.split(r"[,\n]", raw)
    return [p.strip().lower() for p in parts if p.strip()]


def main():
    uniikon_products = fetch_uniikon_products()
    print(f"uniikon.com : {len(uniikon_products)} produits scrapes\n")

    ingredient_counts = Counter()
    for row in uniikon_products:
        for ingredient in split_inci(row.ingredients_raw):
            if ingredient not in NOISE_INGREDIENTS:
                ingredient_counts[ingredient] += 1

    print(f"=== Top {TOP_N} ingredients INCI (hors formulation generique) ===")
    top_ingredients = ingredient_counts.most_common(TOP_N)
    for ingredient, count in top_ingredients:
        print(f"  {count:>3}  {ingredient}")

    try:
        kbeauty_catalog = fetch_kbeauty_shop_catalog()
    except KeyError:
        print(
            "\n(NEON_DB_URL non definie - analyse de recouvrement et prix "
            "sautee, seul le top ingredients ci-dessus est disponible)"
        )
        return

    print(f"\nkbeauty-shop : {len(kbeauty_catalog)} produits publies\n")

    kbeauty_ingredients = set()
    for _, ingredients_inci, _ in kbeauty_catalog:
        kbeauty_ingredients.update(split_inci(ingredients_inci))

    print(f"=== Recouvrement top {TOP_N} uniikon vs catalogue kbeauty-shop ===")
    for ingredient, count in top_ingredients:
        present = "deja au catalogue" if ingredient in kbeauty_ingredients else "ABSENT du catalogue"
        print(f"  {count:>3}  {ingredient:<30} -> {present}")

    uniikon_prices = [float(row.price) for row in uniikon_products if row.price is not None]
    kbeauty_prices = [cents / 100 for _, _, cents in kbeauty_catalog if cents is not None]

    def stats(prices):
        if not prices:
            return "aucun prix"
        return (
            f"moyenne {sum(prices) / len(prices):.2f}EUR, "
            f"min {min(prices):.2f}EUR, max {max(prices):.2f}EUR "
            f"(n={len(prices)})"
        )

    print("\n=== Positionnement prix (EUR) ===")
    print(f"  uniikon.com   : {stats(uniikon_prices)}")
    print(f"  kbeauty-shop  : {stats(kbeauty_prices)}")


if __name__ == "__main__":
    main()
