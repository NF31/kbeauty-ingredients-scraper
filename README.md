# kbeauty-ingredients-scraper

Exercice de montée en compétence (préparation Master MIAGE) : un spider [Scrapy](https://scrapy.org) qui collecte des données publiques sur le web, poussées dans [Apache Cassandra](https://cassandra.apache.org) via un pipeline dédié — persistance polyglotte appliquée à un cas concret plutôt qu'en théorie.

Projet indépendant du monolithe Laravel/Inertia [Kbeauty](https://github.com/NF31/kbeauty-shop) (production), connecté en périphérie à titre pédagogique. Documentation complète (choix de la cible, architecture, mise en place) dans [`10-phase4-scraping-cassandra.md`](https://github.com/NF31/kbeauty-shop/blob/main/docs/montee-competence/10-phase4-scraping-cassandra.md) du repo Kbeauty.

## Cible

[uniikon.com](https://uniikon.com), retenu après vérification de son `robots.txt` (autorise explicitement le crawl, contrairement aux catalogues d'ingrédients cosmétiques envisagés au départ, qui bloquent tous Scrapy/les agents IA).

## Stack

- **Scrapy** (`SitemapSpider`) pour le crawl et le parsing.
- **Cassandra** en local (Docker) pour le dev, **DataStax Astra DB** comme équivalent "prod" managé.
- **DBeaver** (driver JDBC tiers, [`ing-bank/cassandra-jdbc-wrapper`](https://github.com/ing-bank/cassandra-jdbc-wrapper)) pour l'inspection visuelle des deux bases.

## Utilisation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install scrapy cassandra-driver

# Cassandra local (docker compose du projet kbeauty-ecosystem)
docker compose up -d cassandra

scrapy crawl uniikon_gammes
```

Le pipeline (`ingredients_scraper/pipelines.py`) insère chaque item dans `kbeauty_ingredients.gammes` (Cassandra local, `127.0.0.1:9042`). Pour pousser vers Astra à la place, voir `scripts/test_astra_insert.py` (credentials lus depuis une variable d'environnement, jamais en dur).
