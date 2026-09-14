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

# Run the scraper without root privileges. Astra credentials and the secure
# connect bundle are injected by the runtime, never copied into the image.
RUN useradd --create-home --uid 10001 scraper \
    && chown -R scraper:scraper /app
USER scraper

# Le bundle Astra est monte comme secret au runtime et son chemin est fourni
# par ASTRA_SECURE_CONNECT_BUNDLE. Il n'est jamais inclus dans l'image.

# L'agent APM New Relic est attache via son lanceur `newrelic-admin
# run-program` (installe par le paquet newrelic). Il lit /app/newrelic.ini ;
# la cle de licence et l'activation viennent des variables d'environnement
# NEW_RELIC_LICENSE_KEY / NEW_RELIC_ENVIRONMENT injectees par le Container App
# Job. Sans NEW_RELIC_LICENSE_KEY (run local), le crawl s'execute quand meme :
# l'extension Scrapy se met en veille (NotConfigured) et run-program se
# contente de lancer le programme.
ENV NEW_RELIC_CONFIG_FILE=/app/newrelic.ini

ENTRYPOINT ["newrelic-admin", "run-program", "python", "-m", "ingredients_scraper.run"]
