from datetime import datetime, timedelta, timezone
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
    assert data["claims"]["clearance"] == 1
    assert data["claims"]["aud"] == "employee-portal"


def test_standard_forged_token_rejected_everywhere(client):
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {
            "sub": "user",
            "role": "admin",
            "clearance": 5,
            "iss": "Internal Auth API",
            "aud": "internal-admin",
            "exp": int((now + timedelta(hours=1)).timestamp())
        },
        "wrong-secret-key",
        algorithm="HS256",
        headers={"typ": "JWT"}
    )
    verify_resp = client.get(f"/api/verify?token={forged}")
    assert verify_resp.status_code == 401

    admin_resp = client.get(
        "/api/admin/flag",
        headers={"Authorization": f"Bearer {forged}"}
    )
    assert admin_resp.status_code == 401


def test_employee_token_rejected_by_admin(client):
    token = client.get("/api/token").get_json()["token"]
    response = client.get(
        "/api/admin/flag",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403