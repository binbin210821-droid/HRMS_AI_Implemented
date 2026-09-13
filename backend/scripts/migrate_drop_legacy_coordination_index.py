"""Drop the obsolete unique index left by the removed personal coordination flow."""

from pymongo import MongoClient

from app.core.config import get_settings

INDEX_NAME = "alert_id_1"
COLLECTION_NAME = "coordination_directives"


def main() -> None:
    settings = get_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        database = client[settings.database_name]
        collection = database[COLLECTION_NAME]
        indexes = collection.index_information()
        existing = indexes.get(INDEX_NAME)

        if existing is None:
            print(f"{INDEX_NAME}: already absent")
            return

        if existing.get("key") != [("alert_id", 1)] or not existing.get("unique"):
            raise RuntimeError(
                f"Refusing to drop unexpected index {INDEX_NAME}: {existing!r}"
            )

        document_count_before = collection.count_documents({})
        collection.drop_index(INDEX_NAME)
        document_count_after = collection.count_documents({})
        remaining_indexes = sorted(collection.index_information())

        if document_count_before != document_count_after:
            raise RuntimeError("Index migration unexpectedly changed document count")
        if INDEX_NAME in remaining_indexes:
            raise RuntimeError(f"Index {INDEX_NAME} is still present after migration")

        print(
            {
                "collection": COLLECTION_NAME,
                "dropped_index": INDEX_NAME,
                "document_count_before": document_count_before,
                "document_count_after": document_count_after,
                "remaining_indexes": remaining_indexes,
            }
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
