from pathlib import Path

import yaml

compose = yaml.safe_load(
    Path(__file__).resolve().parents[2].joinpath("docker-compose.yml").read_text()
)
mongodb = compose["services"]["mongodb"]

assert "--replSet" in mongodb["command"]
assert mongodb["command"][mongodb["command"].index("--replSet") + 1] == "rs0"
assert "mongodb-init" in compose["services"]
assert (
    compose["services"]["mongodb-init"]["depends_on"]["mongodb"]["condition"] == "service_healthy"
)
print("MongoDB Replica Set compose configuration is valid.")
