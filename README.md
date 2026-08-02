# kbeauty-ingredients-scraper

Exercice de montée en compétence (préparation Master MIAGE) : un spider [Scrapy](https://scrapy.org) qui collecte des données publiques sur le web, poussées dans [Apache Cassandra](https://cassandra.apache.org) via un pipeline dédié — persistance polyglotte appliquée à un cas concret plutôt qu'en théorie.

Projet indépendant du monolithe Laravel/Inertia [Kbeauty](https://github.com/NF31/kbeauty-shop) (production), connecté en périphérie à titre pédagogique. Documentation complète (choix de la cible, architecture, mise en place) dans [`10-phase4-scraping-cassandra.md`](https://github.com/NF31/kbeauty-shop/blob/main/docs/montee-competence/10-phase4-scraping-cassandra.md) du repo Kbeauty.

## Cible

[uniikon.com](https://uniikon.com), retenu après vérification de son `robots.txt` (autorise explicitement le crawl, contrairement aux catalogues d'ingrédients cosmétiques envisagés au départ, qui bloquent tous Scrapy/les agents IA).

## Stack

- **Scrapy** (`SitemapSpider`) pour le crawl et le parsing.
- **Cassandra** en local (Docker) pour le dev, **DataStax Astra DB** comme équivalent "prod" managé.
- **DBeaver** (driver JDBC tiers, [`ing-bank/cassandra-jdbc-wrapper`](https://github.com/ing-bank/cassandra-jdbc-wrapper)) pour l'inspection visuelle des deux bases.

## Données extraites

Chaque page produit alimente deux tables Cassandra, reliées par `source_url` :

- **`gammes`** — le tableau comparatif de gammes affiché sur chaque fiche produit (public cible, actions, actifs clés). Ce tableau est identique sur les 78 pages du catalogue, donc peu de lignes uniques une fois dédupliqué par la clé primaire (`name`).
- **`products`** — la fiche produit elle-même, une ligne par SKU : nom, prix, disponibilité, note et nombre d'avis (widget Loox), bénéfices, description, et la liste **INCI complète** des ingrédients. Extrait principalement depuis le bloc JSON-LD `schema.org/Product` que Shopify injecte sur chaque page (plus fiable que du parsing HTML classique) + deux onglets HTML (`Bénéfices`, `Ingrédients`).

## Utilisation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install scrapy cassandra-driver

# Cassandra local (docker compose du projet kbeauty-ecosystem)
docker compose up -d cassandra

scrapy crawl uniikon_gammes
```

Le pipeline (`ingredients_scraper/pipelines.py`) insère chaque item dans `kbeauty_ingredients.gammes` ou `.products` (Cassandra local, `127.0.0.1:9042`) selon son type. Pour pousser vers Astra à la place, voir `scripts/test_astra_insert.py` (credentials lus depuis une variable d'environnement, jamais en dur).

Pour tester le parsing sans requête réseau (évite le rate-limit Shopify pendant l'itération) : `PYTHONPATH=. python scripts/test_parse_fixture.py`, qui rejoue `fixtures/sample_product.html`.
