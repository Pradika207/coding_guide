from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.database.config import settings


@lru_cache
def get_mongodb_client() -> MongoClient | None:
    if not settings.mongodb_url:
        return None
    return MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)


def get_database() -> Database:
    client = get_mongodb_client()
    if client is None:
        raise RuntimeError("MONGODB_URL is not configured")

    database = client[settings.database_name]
    database.users.create_index("email", unique=True)
    client.admin.command("ping")
    return database
