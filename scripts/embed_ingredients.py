"""Premiere brique du pipeline RAG (Phase 4 avancee -> Phase 5) : transforme
les listes INCI scrapees (Cassandra, table products) en embeddings Voyage AI,
pousses dans une table pgvector dediee sur Neon.

Volontairement isole de kbeauty-ai-core-service (Spring Boot) : ce script ne
fait que produire la donnee vectorisee, il ne branche aucun matching/RAG.
Le moteur de matching reel (Phase 5, "le plus incertain, prevoir buffer"
selon la ROADMAP) est un chantier a part.

Modele : voyage-3.5, embeddings 1024 dimensions (defaut du modele, aligne
avec la colonne vector(1024) de uniikon_ingredient_embeddings). Anthropic
n'a pas d'API d'embeddings native - Voyage AI est le partenaire qu'Anthropic
a rachete et recommande officiellement pour cet usage a cote de Claude.

Usage :
    # .env local (gitignore) avec VOYAGE_API_KEY et NEON_DB_URL
    python scripts/embed_ingredients.py
"""

import os
import time

import psycopg2
import voyageai
from cassandra.cluster import Cluster
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()

MODEL = "voyage-3.5"
# Sans moyen de paiement enregistre sur Voyage AI, le compte est limite a
# 3 requetes/minute (cf. RateLimitError rencontree en test) - un batch large
# minimise le nombre d'appels, et la pause entre batches reste une securite
# si le catalogue grossit au point de depasser une seule requete.
BATCH_SIZE = 5
SECONDS_BETWEEN_BATCHES = 25


def fetch_products():
    cluster = Cluster(["127.0.0.1"], port=9042)
    session = cluster.connect("kbeauty_ingredients")
    rows = list(session.execute("SELECT sku, name, ingredients_raw FROM products"))
    session.shutdown()
    cluster.shutdown()
    return [(r.sku, r.name, r.ingredients_raw) for r in rows if r.sku and r.ingredients_raw]


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main():
    products = fetch_products()

    conn = psycopg2.connect(os.environ["NEON_DB_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT sku FROM uniikon_ingredient_embeddings")
        already_done = {row[0] for row in cur.fetchall()}
    products = [p for p in products if p[0] not in already_done]

    print(
        f"{len(products)} produits a vectoriser "
        f"({len(already_done)} deja en base, ignores)"
    )
    if not products:
        conn.close()
        return

    client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    total_inserted = 0
    batches = list(batched(products, BATCH_SIZE))
    with conn.cursor() as cur:
        for i, batch in enumerate(batches):
            if i > 0:
                time.sleep(SECONDS_BETWEEN_BATCHES)
            skus, names, ingredients_texts = zip(*batch)

            result = client.embed(
                texts=list(ingredients_texts),
                model=MODEL,
                input_type="document",
            )

            rows = [
                (sku, name, ingredients, embedding, MODEL)
                for sku, name, ingredients, embedding in zip(
                    skus, names, ingredients_texts, result.embeddings
                )
            ]

            # autocommit=True : chaque batch est persiste independamment,
            # un echec sur un batch ulterieur (ex: rate limit Voyage) ne
            # fait pas perdre le travail deja fait sur les precedents.
            execute_values(
                cur,
                """
                INSERT INTO uniikon_ingredient_embeddings
                    (sku, product_name, ingredients_raw, embedding, embedding_model)
                VALUES %s
                ON CONFLICT (sku) DO UPDATE SET
                    product_name = EXCLUDED.product_name,
                    ingredients_raw = EXCLUDED.ingredients_raw,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    created_at = now()
                """,
                rows,
                template="(%s, %s, %s, %s::vector, %s)",
            )
            total_inserted += len(rows)
            print(f"  {total_inserted}/{len(products)} vectorises")

    conn.close()
    print(f"Termine : {total_inserted} embeddings dans uniikon_ingredient_embeddings.")


if __name__ == "__main__":
    main()
