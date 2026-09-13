"""Drop the obsolete index that permanently blocked reissuing accepted task directives."""

from pymongo import MongoClient

from app.core.config import get_settings

INDEX_NAME = "directed_task_once_unique"
COLLECTION_NAME = "department_task_directives"


def main() -> None:
    settings = get_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        collection = client[settings.database_name][COLLECTION_NAME]
        indexes = collection.index_information()
        existing = indexes.get(INDEX_NAME)

        if existing is None:
            print(f"{INDEX_NAME}: already absent")
            return

        if existing.get("key") != [("task_ids", 1)] or not existing.get("unique"):
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
            raise RuntimeError(f"{INDEX_NAME} is still present after migration")

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
