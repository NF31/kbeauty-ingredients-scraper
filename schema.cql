-- Schema Cassandra attendu par ingredients_scraper/pipelines.py (CassandraPipeline).
-- Jamais capture nulle part avant ce fichier - cree a la main via cqlsh sur la
-- machine de dev d'origine, decouvert manquant en reinstallant sur une nouvelle
-- machine (le pipeline se connecte au keyspace mais ne le cree jamais lui-meme).
--
-- Usage : docker exec -i kbeauty_cassandra cqlsh < schema.cql
-- (necessite le conteneur cassandra du docker-compose kbeauty-ecosystem demarre)

CREATE KEYSPACE IF NOT EXISTS kbeauty_ingredients
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

-- Cle primaire = name : le tableau comparatif de gammes est identique sur les
-- 78 pages du catalogue, deduplique par nom de gamme (voir README.md).
CREATE TABLE IF NOT EXISTS kbeauty_ingredients.gammes (
    name text PRIMARY KEY,
    source_url text,
    ideal_pour text,
    actions_principales text,
    actifs_cles text,
    scraped_at timestamp
);

-- Cle primaire = sku : une ligne par produit, re-insertion idempotente a
-- chaque run quotidien du cron (voir README.md).
CREATE TABLE IF NOT EXISTS kbeauty_ingredients.products (
    sku text PRIMARY KEY,
    source_url text,
    name text,
    price decimal,
    currency text,
    availability text,
    rating decimal,
    ratings_count int,
    benefits text,
    description text,
    ingredients_raw text,
    scraped_at timestamp
);
