from pymongo import MongoClient

import config

_client = None


def get_db():
    """Return the database handle, creating the client lazily. Never logs the URI."""
    global _client
    if _client is None:
        if not config.MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not configured")
        _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client[config.DATABASE_NAME]
