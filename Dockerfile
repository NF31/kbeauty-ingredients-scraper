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

ENTRYPOINT ["scrapy", "crawl", "uniikon_gammes", "-L", "INFO"]
