# kbeauty-ingredients-scraper

Exercice de montée en compétence (préparation Master MIAGE) : un spider [Scrapy](https://scrapy.org) qui collecte des données publiques sur le web, poussées dans [Apache Cassandra](https://cassandra.apache.org) via un pipeline dédié — persistance polyglotte appliquée à un cas concret plutôt qu'en théorie.

Projet indépendant du monolithe Laravel/Inertia Kbeauty (production, dépôt privé), connecté en périphérie à titre pédagogique. Documentation complète (choix de la cible, architecture, mise en place) dans [`10-phase4-scraping-cassandra.md`](https://github.com/NF31/kbeauty-ecosystem/blob/main/docs/montee-competence/10-phase4-scraping-cassandra.md) du dépôt kbeauty-ecosystem.

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
pip install -r requirements.txt

# Cassandra local (docker compose du projet kbeauty-ecosystem)
docker compose up -d cassandra

# Keyspace/tables (une seule fois par instance Cassandra, ex. nouvelle machine) :
docker exec -i kbeauty_cassandra cqlsh < schema.cql

scrapy crawl uniikon_gammes
```

Le pipeline (`ingredients_scraper/pipelines.py`) insère chaque item dans `kbeauty_ingredients.gammes` ou `.products` (Cassandra local, `127.0.0.1:9042`) selon son type. Pour pousser vers Astra à la place, voir `scripts/test_astra_insert.py` (credentials lus depuis une variable d'environnement, jamais en dur). En conteneur, le secure connect bundle doit être monté comme secret et son chemin fourni par `ASTRA_SECURE_CONNECT_BUNDLE`; il n'est jamais copié dans l'image.

Pour tester le parsing sans requête réseau (évite le rate-limit Shopify pendant l'itération) : `PYTHONPATH=. pytest scripts/test_parse_fixture.py`, qui rejoue `fixtures/sample_product.html` et vérifie les champs extraits (identification, prix, disponibilité/note, liste INCI). `python scripts/test_parse_fixture.py` reste utilisable pour inspecter les valeurs à l'œil.

## Scan de secrets (gitleaks)

Garde-fou contre le commit accidentel de clés API / tokens.

```bash
# Une fois par clone :
git config core.hooksPath .githooks
```

Le hook lance `gitleaks git --staged` avant chaque commit et le bloque si un
secret est détecté (`git commit --no-verify` pour forcer ponctuellement).
Même scan en CI sur chaque push / PR (`.github/workflows/gitleaks.yml`), sur
l'historique complet. Config et faux positifs (clés de fournisseurs tiers
présentes dans les pages aspirées de `fixtures/`) dans `.gitleaks.toml`.

## Automatisation (cron)

`scripts/run_crawl.sh` relance le container Cassandra si besoin (utile
après un redémarrage WSL) puis lance `scrapy crawl uniikon_gammes` en
non-interactif, avec un log horodaté dans `logs/`. Installé en cron
utilisateur, une fois par jour à 3h (`crontab -l` pour vérifier) :

```
0 3 * * * ~/projects/kbeauty-ingredients-scraper/scripts/run_crawl.sh >> ~/projects/kbeauty-ingredients-scraper/logs/cron.log 2>&1
```

Réinsertion idempotente : les clés primaires (`name` pour `gammes`, `sku`
pour `products`) font que chaque run quotidien met à jour les lignes
existantes plutôt que d'empiler des doublons.

## Observabilité (New Relic APM)

Le job est instrumenté par l'agent APM New Relic (compte partagé avec
`kbeauty-ai-core-service`, région EU) : il apparaît comme une entité APM
distincte, `kbeauty-ingredients-scraper`, de type *non-web* (chaque run =
une transaction de fond « Scrapy/uniikon_gammes »).

- `newrelic.ini` : configuration de l'agent (nom d'appli, collecteur EU,
  traçage distribué). **Pas** de clé de licence dans le fichier — elle
  vient de la variable d'environnement `NEW_RELIC_LICENSE_KEY`.
- `ingredients_scraper/run.py` : point d'entrée du conteneur. Lance le
  crawl dans une transaction `@background_task` (l'agent n'instrumente pas
  Scrapy tout seul). `ENTRYPOINT` du `Dockerfile` :
  `newrelic-admin run-program python -m ingredients_scraper.run`.
- `ingredients_scraper/newrelic_extension.py` : extension Scrapy qui ajoute
  les compteurs de fin de crawl (items, réponses, erreurs, retries) en
  attributs sur la transaction.

Sans `NEW_RELIC_LICENSE_KEY` dans l'environnement (run local), l'agent est
un no-op : `scrapy crawl uniikon_gammes` fonctionne à l'identique.

Détails et lecture des métriques : [`18-observabilite-newrelic.md`](https://github.com/NF31/kbeauty-ecosystem/blob/main/docs/montee-competence/18-observabilite-newrelic.md)
du dépôt kbeauty-ecosystem.

## Déploiement de l'image (CD)

`.github/workflows/build-image.yml` build et pousse l'image vers une référence
immuable basée sur le SHA du commit (`kbeautyscraperacr2734.azurecr.io/kbeauty-ingredients-scraper:<commit-sha>`) à
chaque push sur `main` touchant le `Dockerfile`, les dépendances ou le code
du scraper (ou manuellement via `workflow_dispatch`). Le job Container App
Azure prend la nouvelle image au run planifié suivant, sans intervention
manuelle.

Authentification au registre par **token ACR scope-map** (`az acr token
create`), restreint en push/pull au seul repo `kbeauty-ingredients-scraper`
— pas de service principal Entra ID (l'enregistrement d'application n'est
pas autorisé sur ce tenant). Secrets GitHub : `ACR_USERNAME`, `ACR_PASSWORD`.

Le bundle Astra (`.astra-secrets/secure-connect-kbeauty-ingredients.zip`,
gitignoré) est uniquement nécessaire en local. En production, il doit être
monté comme secret et référencé par `ASTRA_SECURE_CONNECT_BUNDLE`; le workflow
de build ne le restaure ni ne l'embarque dans l'image.

Avant ce workflow, la seule méthode de build était manuelle (`az acr build`,
puis `docker build` local après découverte que les ACR Tasks sont
désactivées sur cette souscription — voir
[`18-observabilite-newrelic.md`](https://github.com/NF31/kbeauty-ecosystem/blob/main/docs/montee-competence/18-observabilite-newrelic.md)).
