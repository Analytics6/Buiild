def _login(client, email="demo@support.ai", password="demo123"):
    response = client.post("/login", json={"email": email, "password": password})
    return response.json()["token"]


def test_ask_requires_auth(client):
    response = client.post("/ask", json={"question": "billing issue"})
    assert response.status_code == 401


def test_ask_without_openai_key(client):
    token = _login(client)
    response = client.post(
        "/ask",
        json={"question": "customer has a billing issue", "template": "support"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert data["cached"] is False


def test_templates_endpoint(client):
    response = client.get("/templates")
    assert response.status_code == 200
    templates = response.json()["templates"]
    assert "support" in templates
    assert "manager" in templates
    assert "analyst" in templates


def test_ask_invalid_template(client):
    token = _login(client)
    response = client.post(
        "/ask",
        json={"question": "test", "template": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_ask_empty_question(client):
    token = _login(client)
    response = client.post(
        "/ask",
        json={"question": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
