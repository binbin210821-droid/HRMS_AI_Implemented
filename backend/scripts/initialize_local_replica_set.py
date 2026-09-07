import time

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

direct_client = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000,
)
direct_client.admin.command("ping")

try:
    direct_client.admin.command(
        "replSetInitiate",
        {"_id": "rs0", "members": [{"_id": 0, "host": "127.0.0.1:27017"}]},
    )
except OperationFailure as error:
    if "already initialized" not in str(error).lower():
        raise

replica_client = MongoClient(
    "mongodb://127.0.0.1:27017/?replicaSet=rs0",
    serverSelectionTimeoutMS=5000,
)
for _ in range(20):
    try:
        replica_client.admin.command("ping")
        print("Local MongoDB Replica Set rs0 is ready.")
        break
    except PyMongoError:
        time.sleep(0.5)
else:
    raise RuntimeError("Local MongoDB Replica Set did not become ready")
