"""Test manuel : pousse les memes 4 items de fixture vers Astra (au lieu du
Cassandra local) pour valider le chemin complet driver -> secure connect
bundle -> insert, avant de brancher le vrai crawl dessus.

Usage :
    export ASTRA_TOKEN="AstraCS:..."
    python scripts/test_astra_insert.py
"""

import os
from datetime import datetime, timezone

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

BUNDLE_PATH = os.path.expanduser(
    "~/projects/kbeauty-ingredients-scraper/.astra-secrets/"
    "secure-connect-kbeauty-ingredients.zip"
)

FIXTURE_ITEMS = [
    {
        "name": "❤️ Gamme The One",
        "source_url": "https://uniikon.com/products/gamme-resistance",
        "ideal_pour": "Tous types de cheveux, normaux à gras",
        "actions_principales": "",
        "actifs_cles": "🌟 Kératine 🌱 Biotine 🥥 Extrait de lait de coco",
    },
    {
        "name": "💚 Gamme Résistance",
        "source_url": "https://uniikon.com/products/gamme-resistance",
        "ideal_pour": "Cheveux abîmés, cassants, traités chimiquement",
        "actions_principales": "",
        "actifs_cles": "🌿 Kératine, 🌱 Biotine, 💧 Acide hyaluronique",
    },
    {
        "name": "💙 Gamme Amla Tanino",
        "source_url": "https://uniikon.com/products/gamme-resistance",
        "ideal_pour": "Cheveux en quête de lissage,",
        "actions_principales": "",
        "actifs_cles": "🍇 Huile d'Amla, 🌱 Biotine, 🍂 Extrait de tanin",
    },
    {
        "name": "💛 Gamme Collagène",
        "source_url": "https://uniikon.com/products/gamme-resistance",
        "ideal_pour": "Cheveux très secs, texturisés",
        "actions_principales": "",
        "actifs_cles": "💪 Collagène, 🌱 Biotine, 🧈 Beurre de karité",
    },
]


def main():
    token = os.environ["ASTRA_TOKEN"]

    cluster = Cluster(
        cloud={"secure_connect_bundle": BUNDLE_PATH},
        auth_provider=PlainTextAuthProvider("token", token),
    )
    session = cluster.connect("default_keyspace")

    insert_stmt = session.prepare(
        """
        INSERT INTO gammes
            (name, source_url, ideal_pour, actions_principales, actifs_cles, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
    )

    for item in FIXTURE_ITEMS:
        session.execute(
            insert_stmt,
            (
                item["name"],
                item["source_url"],
                item["ideal_pour"],
                item["actions_principales"],
                item["actifs_cles"],
                datetime.now(timezone.utc),
            ),
        )

    print("4 items inseres. Verification :")
    for row in session.execute("SELECT name, ideal_pour, actifs_cles FROM gammes"):
        print(row)

    session.shutdown()
    cluster.shutdown()


if __name__ == "__main__":
    main()
