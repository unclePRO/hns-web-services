import secrets

from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

app = Flask(__name__)

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "blockstar_internal"
COLLECTION_NAME = "builds"

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = mongo_client[DB_NAME]
builds = db[COLLECTION_NAME]

FLAG = "HNS{blockstar_nosql_unreleased_asset_leaked}"


# --------------------------------------------------
# Auto-seed: zero manual setup for lab admins
# --------------------------------------------------

def gen_dev_token():
    # 64-character random developer token
    return secrets.token_hex(32)


def seed_database():
    """Populate blockstar_internal.builds on first run if it's empty."""
    try:
        if builds.count_documents({}) > 0:
            return
    except ServerSelectionTimeoutError:
        print(
            "[blockstar-portal] Could not reach MongoDB at "
            f"{MONGO_URI} — is mongod running? Seeding skipped."
        )
        return

    seed_docs = [
        {
            "game_id": "bar1",
            "name": "Blue Alive Redemption",
            "build": "v1.2.3-dev",
            "platform": "PC / Dev Kit",
            "size_mb": 48210,
            "classified": False,
            "dev_token": gen_dev_token(),
        },
        {
            "game_id": "asv1",
            "name": "Automobile Stealer V",
            "build": "v5.0.1-dev",
            "platform": "PC / Dev Kit",
            "size_mb": 61770,
            "classified": False,
            "dev_token": gen_dev_token(),
        },
        {
            "game_id": "rdos2",
            "name": "Red Dirt Outlaw Simulator 2",
            "build": "v2.0.0-dev",
            "platform": "PC / Dev Kit",
            "size_mb": 73540,
            "classified": False,
            "dev_token": gen_dev_token(),
        },
        {
            "game_id": "mp3",
            "name": "Maximum Pain 3",
            "build": "v3.1.4-dev",
            "platform": "PC / Dev Kit",
            "size_mb": 39680,
            "classified": False,
            "dev_token": gen_dev_token(),
        },
        {
            "game_id": "gta7",
            "name": "Grand Theft Aunty VII",
            "build": "UNRELEASED / INTERNAL-ONLY",
            "platform": "Classified",
            "size_mb": 94210,
            "classified": True,
            "dev_token": gen_dev_token(),
            "flag": FLAG,
        },
    ]

    builds.insert_many(seed_docs)
    print(
        f"[blockstar-portal] Seeded {DB_NAME}.{COLLECTION_NAME} with "
        f"{len(seed_docs)} build records."
    )


# --------------------------------------------------
# Portal UI
# --------------------------------------------------

@app.get("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# Public catalog
#
# Lists every build record for the portal UI. Classified records keep
# their name and details hidden; only the game_id and lock state are
# exposed, matching how an internal portal would tease an in-progress
# project without describing it.
# --------------------------------------------------

@app.get("/api/builds")
def list_builds():
    catalog = []
    for doc in builds.find({}, {"_id": 0, "dev_token": 0, "flag": 0}):
        if doc.get("classified"):
            catalog.append({
                "game_id": doc["game_id"],
                "name": "CLASSIFIED PROJECT",
                "build": "ACCESS RESTRICTED",
                "platform": "—",
                "size_mb": None,
                "classified": True,
            })
        else:
            catalog.append(doc)
    return jsonify({"builds": catalog})


# --------------------------------------------------
# Build download (vulnerable endpoint)
#
# Looks up a build by game_id + dev_token. Both values come straight
# from the request body and are passed into the PyMongo filter as-is.
# --------------------------------------------------

@app.post("/api/download_build")
def download_build():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "error", "message": "Expected a JSON body."}), 400

    game_id = payload.get("game_id")
    dev_token = payload.get("dev_token")

    if game_id is None or dev_token is None:
        return jsonify({
            "status": "error",
            "message": "Both 'game_id' and 'dev_token' are required.",
        }), 400

    try:
        record = builds.find_one({"game_id": game_id, "dev_token": dev_token})
    except PyMongoError:
        return jsonify({"status": "error", "message": "Lookup failed."}), 500

    if not record:
        return jsonify({
            "status": "error",
            "message": "No build found for that game ID / dev token combination.",
        }), 404

    response = {
        "status": "success",
        "message": "Build access granted.",
        "game": record.get("name"),
        "build": record.get("build"),
        "download_url": (
            f"https://cdn.blockstar-internal.local/builds/"
            f"{record.get('game_id')}/package.zip?sig={secrets.token_hex(16)}"
        ),
    }
    if record.get("classified") and "flag" in record:
        response["flag"] = record["flag"]

    return jsonify(response)


# --------------------------------------------------
# Error handling
# --------------------------------------------------

@app.errorhandler(404)
def not_found(_error):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


# --------------------------------------------------
# Run locally
# --------------------------------------------------

seed_database()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)