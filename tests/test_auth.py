def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["redis"] == "memory"
    assert data["database"] == "sqlite"


def test_register_and_login(client):
    register = client.post(
        "/register",
        json={
            "email": "newuser@test.com",
            "password": "secret12",
            "full_name": "New User",
            "role": "analyst",
        },
    )
    assert register.status_code == 200
    assert register.json()["user"]["email"] == "newuser@test.com"

    login = client.post("/login", json={"email": "newuser@test.com", "password": "secret12"})
    assert login.status_code == 200
    body = login.json()
    assert "token" in body
    assert "jwt" in body
    assert body["user"]["role"] == "analyst"


def test_demo_user_login(client):
    response = client.post("/login", json={"email": "demo@support.ai", "password": "demo123"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "demo@support.ai"


def test_me_requires_auth(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_me_with_token(client):
    login = client.post("/login", json={"email": "demo@support.ai", "password": "demo123"})
    token = login.json()["token"]
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "demo@support.ai"


def test_logout(client):
    login = client.post("/login", json={"email": "demo@support.ai", "password": "demo123"})
    token = login.json()["token"]
    logout = client.post("/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout.status_code == 200
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


def test_admin_list_users(client):
    admin_login = client.post("/login", json={"email": "admin@support.ai", "password": "admin123"})
    admin_token = admin_login.json()["token"]
    response = client.get("/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert len(response.json()["users"]) >= 2

    demo_login = client.post("/login", json={"email": "demo@support.ai", "password": "demo123"})
    demo_token = demo_login.json()["token"]
    forbidden = client.get("/users", headers={"Authorization": f"Bearer {demo_token}"})
    assert forbidden.status_code == 403
