import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


from uuid import uuid4


def test_create_get_user():
    email = f"a-{uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/users", json={"email": email, "full_name": "Alice"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    uid = data["id"]

    resp2 = client.get(f"/api/v1/users/{uid}")
    assert resp2.status_code == 200
    assert resp2.json()["email"] == email


def test_list_users():
    resp = client.get("/api/v1/users")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
