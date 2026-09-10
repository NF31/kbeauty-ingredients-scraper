# Image du job de scraping (kbeauty-ingredients-scraper), destinee a tourner
# en tache planifiee (Azure Container Apps Jobs) - pas un serveur, le
# conteneur execute `scrapy crawl` une fois puis s'arrete.
FROM python:3.13-slim

WORKDIR /app

# Dependances systeme requises par lxml/cryptography (utilisees par Scrapy
# et le driver Cassandra) - non presentes dans l'image slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Le bundle est necessaire au runtime (CassandraPipeline en mode Astra, voir
# pipelines.py) - normalement gitignore (*.zip, .astra-secrets/), inclus ici
# uniquement dans le contexte de build local envoye a `az acr build`, jamais
# commit dans le repo. Image poussee vers un registre prive (Azure Container
# Registry, acces authentifie uniquement).
# (deja copie par `COPY . .` ci-dessus)

# L'agent APM New Relic est attache via son lanceur `newrelic-admin
# run-program` (installe par le paquet newrelic). Il lit /app/newrelic.ini ;
# la cle de licence et l'activation viennent des variables d'environnement
# NEW_RELIC_LICENSE_KEY / NEW_RELIC_ENVIRONMENT injectees par le Container App
# Job. Sans NEW_RELIC_LICENSE_KEY (run local), le crawl s'execute quand meme :
# l'extension Scrapy se met en veille (NotConfigured) et run-program se
# contente de lancer le programme.
ENV NEW_RELIC_CONFIG_FILE=/app/newrelic.ini

ENTRYPOINT ["newrelic-admin", "run-program", "python", "-m", "ingredients_scraper.run"]
